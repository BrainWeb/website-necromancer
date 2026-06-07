import os
import re
import sys
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

def get_domain_replacer_regex(domain):
    # Regex to catch raw http, https, www, and JSON escaped variants
    # For example: http://example.com/, https://www.example.com/, https:\/\/example.com\/
    escaped_domain = re.escape(domain)
    pattern = r'(https?:)?(\\/\\/|//)(?:www\.)?' + escaped_domain + r'(\\/|/)'
    return re.compile(pattern, re.IGNORECASE)

def process_url(url, is_href, prefix, domain_pattern):
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

    # Avoid variables from JS templates that might have leaked into HTML
    if '+' in path or '{' in path: 
        return url

    if domain_match or (url.startswith('/') and not url.startswith('//')):
        if path == '' or path == '/':
            path = prefix + 'index.html'
        else:
            path = prefix + path.lstrip('/')
            
    # Append index.html for local offline viewing ONLY for href
    if is_href:
        parsed = urlparse(path)
        clean_path = parsed.path
        
        if clean_path.endswith('/'):
            path = path.replace(clean_path, clean_path + 'index.html', 1)
        elif not os.path.splitext(clean_path)[1] and clean_path not in ('.', '..', ''):
            path = path.replace(clean_path, clean_path + '/index.html', 1)

    return path

def rewrite_links(directory, domain):
    logger.info(f"Starting link rewrite in {directory} for domain {domain}...")
    
    domain_pattern = re.compile(
        r'^(https?:)?//(?:www\.)?' + re.escape(domain) + r'(?::\d+)?(.*)$',
        re.IGNORECASE
    )
    
    domain_replace_pattern = get_domain_replacer_regex(domain)

    cleaned_count = 0
    total_files = 0
    extensions = ('.html', '.htm', '.css', '.js', '.json')

    link_pattern = re.compile(r'\b(href|src|action|data-image-src)=([\'"])(.*?)\2', re.IGNORECASE)
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
                    
                    if file.endswith(('.html', '.htm', '.css')):
                        def replace_link(match):
                            attr = match.group(1)
                            quote = match.group(2)
                            url = match.group(3)
                            is_href = attr.lower() == 'href'
                            new_url = process_url(url, is_href, prefix, domain_pattern)
                            return f"{attr}={quote}{new_url}{quote}"

                        def replace_css_url(match):
                            keyword = match.group(1)
                            quote = match.group(2)
                            url = match.group(3)
                            if url.startswith('data:'):
                                return match.group(0)
                            new_url = process_url(url, False, prefix, domain_pattern)
                            return f"{keyword}({quote}{new_url}{quote})"

                        new_content, _ = link_pattern.subn(replace_link, new_content)
                        new_content, _ = css_url_pattern.subn(replace_css_url, new_content)
                    
                    # Single regex replacement for JS variables and string domains
                    def domain_replacer(match):
                        # match.group(2) is the slashes // or \/\/
                        slashes = match.group(2)
                        return prefix if slashes == '//' else prefix.replace('/', '\\/')
                        
                    new_content = domain_replace_pattern.sub(domain_replacer, new_content)
                    
                    if content != new_content:
                        with open(filepath, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                        cleaned_count += 1
                        logger.debug(f"Rewrote links in: {filepath}")
                        
                except Exception as e:
                    logger.error(f"Error processing {filepath}: {e}")

    logger.info(f"Scan complete. Scanned {total_files} files. Rewrote links in {cleaned_count} files.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    domain = sys.argv[1] if len(sys.argv) > 1 else "abcqualitymanagement.com"
    target_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'websites', domain)
    if os.path.exists(target_dir):
        rewrite_links(target_dir, domain)
    else:
        logger.error(f"Directory {target_dir} not found.")
