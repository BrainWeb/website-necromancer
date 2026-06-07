import os
import re
import sys

def mark_missing_links(directory):
    html_exts = ('.html', '.htm')
    
    # regex to find <a ... href="TARGET" ...>TEXT</a>
    link_pattern = re.compile(r'(<a\s+[^>]*href=[\'"]([^\'"]+)[\'"][^>]*>)(.*?)(</a>)', re.IGNORECASE | re.DOTALL)
    
    marked_files_count = 0
    total_marked_links = 0
    
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(html_exts):
                filepath = os.path.join(root, file)
                
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    
                def process_link(match):
                    nonlocal total_marked_links
                    start_tag = match.group(1)
                    url = match.group(2)
                    text = match.group(3)
                    end_tag = match.group(4)
                    
                    # only care about relative links
                    if url.startswith(('http:', 'https:', '//', 'mailto:', 'tel:', 'javascript:', '#', 'data:')):
                        return match.group(0)
                        
                    clean_url = url.split('#')[0].split('?')[0]
                    if not clean_url:
                        return match.group(0)
                        
                    # Handle paths starting with '/' safely (which shouldn't happen much post-rewrite)
                    if clean_url.startswith('/'):
                        target_path = os.path.normpath(os.path.join(directory, clean_url.lstrip('/')))
                    else:
                        target_path = os.path.normpath(os.path.join(root, clean_url))
                    
                    if not os.path.exists(target_path):
                        # don't mark if it's already marked or if inner text is empty/just tags like images
                        # Wait, what if text contains HTML? We just append before the closing </a>.
                        if '[Not Archieved]' not in text:
                            total_marked_links += 1
                            return f"{start_tag}{text} [Not Archieved]{end_tag}"
                            
                    return match.group(0)

                new_content, num_subs = link_pattern.subn(process_link, content)
                
                if new_content != content:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    marked_files_count += 1
                    
    print(f"Marking complete. Marked {total_marked_links} dead links across {marked_files_count} files.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 mark_missing_links.py <domain_folder>")
        sys.exit(1)
    
    domain = sys.argv[1]
    directory = os.path.join('websites', domain)
    
    if not os.path.exists(directory):
        print(f"Directory {directory} does not exist.")
        sys.exit(1)
        
    mark_missing_links(directory)
