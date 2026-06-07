import os
import re
import sys
from urllib.parse import urlparse

def rewrite_links(directory, domain):
    domain_pattern = re.compile(
        r'^(https?:)?//(?:www\.)?' + re.escape(domain) + r'(?::\d+)?(.*)$',
        re.IGNORECASE
    )

    cleaned_count = 0
    total_files = 0
    extensions = ('.html', '.htm', '.css', '.js', '.json')

    # Regex to extract href/src/action
    link_pattern = re.compile(r'\b(href|src|action|data-image-src)=([\'"])(.*?)\2', re.IGNORECASE)
    # Regex to extract CSS url(...) using word boundary to avoid matching toDataURL()
    css_url_pattern = re.compile(r'\b(url)\(([\'"]?)(.*?)\2\)', re.IGNORECASE)

    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(extensions):
                total_files += 1
                filepath = os.path.join(root, file)
                
                rel_dir = os.path.relpath(directory, root)
                prefix = rel_dir + '/' if rel_dir != '.' else './'
                
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()

                    new_content = content
                    
                    # We will only apply the regex pattern match to HTML and CSS files, because JS string concatenation breaks easily
                    if file.endswith(('.html', '.htm', '.css')):
                        def process_url(url, is_href=False):
                            if url.startswith('//') and not domain_pattern.match(url):
                                return 'https:' + url
                                
                            domain_match = domain_pattern.match(url)
                            if domain_match:
                                path = domain_match.group(2)
                            elif url.startswith('/') and not url.startswith('//'):
                                path = url
                            elif not url.startswith('http') and not url.startswith('//') and not url.startswith('javascript:') and not url.startswith('data:') and not url.startswith('#'):
                                path = url
                            else:
                                return url

                            # Avoid variables from JS templates that might have leaked into HTML (e.g. +a+)
                            if '+' in path or '{' in path: 
                                return url

                            if domain_match or (url.startswith('/') and not url.startswith('//')):
                                if path == '' or path == '/':
                                    path = prefix + 'index.html'
                                else:
                                    path = prefix + path.lstrip('/')
                                    
                            # Append index.html for local offline viewing ONLY for href (navigation links)
                            if is_href:
                                parsed = urlparse(path)
                                clean_path = parsed.path
                                
                                if clean_path.endswith('/'):
                                    path = path.replace(clean_path, clean_path + 'index.html', 1)
                                elif not os.path.splitext(clean_path)[1] and clean_path not in ('.', '..', ''):
                                    path = path.replace(clean_path, clean_path + '/index.html', 1)

                            return path

                        def replace_link(match):
                            attr = match.group(1)
                            quote = match.group(2)
                            url = match.group(3)
                            is_href = attr.lower() == 'href'
                            new_url = process_url(url, is_href=is_href)
                            return f"{attr}={quote}{new_url}{quote}"

                        def replace_css_url(match):
                            keyword = match.group(1) # preserves 'url' vs 'URL' formatting
                            quote = match.group(2)
                            url = match.group(3)
                            if url.startswith('data:'):
                                return match.group(0)
                            new_url = process_url(url, is_href=False)
                            return f"{keyword}({quote}{new_url}{quote})"

                        new_content, num_subs1 = link_pattern.subn(replace_link, new_content)
                        new_content, num_subs2 = css_url_pattern.subn(replace_css_url, new_content)
                    
                    # String replacement for JS variables tracking absolute domain (apply to all files)
                    raw_http = f"http://{domain}/"
                    raw_https = f"https://{domain}/"
                    raw_www_http = f"http://www.{domain}/"
                    raw_www_https = f"https://www.{domain}/"
                    
                    new_content = new_content.replace(raw_https, prefix)
                    new_content = new_content.replace(raw_http, prefix)
                    new_content = new_content.replace(raw_www_https, prefix)
                    new_content = new_content.replace(raw_www_http, prefix)
                    
                    # JSON escaped slashes
                    escaped_https = f"https:\\/\\/{domain}\\/"
                    escaped_http = f"http:\\/\\/{domain}\\/"
                    new_content = new_content.replace(escaped_https, prefix.replace('/', '\\/'))
                    new_content = new_content.replace(escaped_http, prefix.replace('/', '\\/'))
                    
                    if content != new_content:
                        with open(filepath, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                        cleaned_count += 1
                        
                except Exception as e:
                    print(f"Error processing {filepath}: {e}")

    print(f"\nScan complete. Scanned {total_files} files. Rewrote links in {cleaned_count} files.")

if __name__ == "__main__":
    domain = sys.argv[1] if len(sys.argv) > 1 else "abcqualitymanagement.com"
    target_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'websites', domain)
    if os.path.exists(target_dir):
        print(f"Starting link rewrite in {target_dir} for domain {domain}...")
        rewrite_links(target_dir, domain)
    else:
        print(f"Directory {target_dir} not found.")

