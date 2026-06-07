import os
import re
import sys
import logging

logger = logging.getLogger(__name__)

def mark_missing_links(directory):
    logger.info(f"Starting missing links check in {directory}...")
    
    html_exts = ('.html', '.htm')
    link_pattern = re.compile(r'(<a\s+[^>]*href=[\'"]([^\'"]+)[\'"][^>]*>)(.*?)(</a>)', re.IGNORECASE | re.DOTALL)
    
    # Pre-compute all existing files to avoid hitting the physical disk millions of times
    existing_files = set()
    for root, _, files in os.walk(directory):
        for file in files:
            existing_files.add(os.path.normpath(os.path.join(root, file)))
            
    marked_files_count = 0
    total_marked_links = 0
    
    # We walk again just to read the HTML files, but our file lookups will be O(1) in RAM
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(html_exts):
                filepath = os.path.join(root, file)
                
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        
                    def process_link(match):
                        nonlocal total_marked_links
                        start_tag = match.group(1)
                        url = match.group(2)
                        text = match.group(3)
                        end_tag = match.group(4)
                        
                        if url.startswith(('http:', 'https:', '//', 'mailto:', 'tel:', 'javascript:', '#', 'data:')):
                            return match.group(0)
                            
                        clean_url = url.split('#')[0].split('?')[0]
                        if not clean_url:
                            return match.group(0)
                            
                        if clean_url.startswith('/'):
                            target_path = os.path.normpath(os.path.join(directory, clean_url.lstrip('/')))
                        else:
                            target_path = os.path.normpath(os.path.join(root, clean_url))
                        
                        # O(1) memory lookup instead of os.path.exists
                        if target_path not in existing_files:
                            if '[Not Archived]' not in text:
                                total_marked_links += 1
                                return f"{start_tag}{text} [Not Archived]{end_tag}"
                                
                        return match.group(0)

                    new_content, _ = link_pattern.subn(process_link, content)
                    
                    if new_content != content:
                        with open(filepath, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                        marked_files_count += 1
                        logger.debug(f"Marked missing links in: {filepath}")
                except Exception as e:
                    logger.error(f"Error processing {filepath}: {e}")
                    
    logger.info(f"Marking complete. Marked {total_marked_links} dead links across {marked_files_count} files.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) < 2:
        logger.error("Usage: python3 mark_missing_links.py <domain_folder>")
        sys.exit(1)
    
    domain = sys.argv[1]
    directory = os.path.join('websites', domain)
    
    if not os.path.exists(directory):
        logger.error(f"Directory {directory} does not exist.")
        sys.exit(1)
        
    mark_missing_links(directory)
