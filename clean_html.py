import os
import re
import logging

logger = logging.getLogger(__name__)

def clean_html_files(directory):
    """
    Recursively scans the directory for HTTP/HTML files and removes
    aggressive client-side scripts that force HTTPS redirects,
    which break local file:// viewing.
    """
    # Regex to match the known aggressive redirect script
    redirect_pattern = re.compile(
        r'<script[^>]*>\s*if\s*\(\s*document\.location\.protocol\s*!=\s*"https:"\s*\)\s*\{\s*document\.location\s*=\s*document\.URL\.replace\(\/\^http:\/i,\s*"https:"\);\s*\}\s*</script>',
        re.IGNORECASE | re.DOTALL
    )

    cleaned_count = 0
    total_files = 0

    logger.info(f"Starting HTML cleanup in {directory}...")

    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(('.html', '.htm')):
                total_files += 1
                filepath = os.path.join(root, file)
                
                content = None
                encodings_to_try = ['utf-8', 'latin-1', 'cp1252']
                
                for encoding in encodings_to_try:
                    try:
                        with open(filepath, 'r', encoding=encoding) as f:
                            content = f.read()
                        break # Successfully read
                    except UnicodeDecodeError:
                        continue
                    except Exception as e:
                        logger.error(f"Error reading {filepath}: {e}")
                        break
                        
                if content is None:
                    logger.warning(f"Failed to decode {filepath} with any standard encoding. Skipping.")
                    continue
                    
                # Check and replace
                new_content, num_subs = redirect_pattern.subn('', content)
                
                if num_subs > 0:
                    try:
                        with open(filepath, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                        cleaned_count += 1
                        logger.debug(f"Cleaned redirect script from: {filepath}")
                    except Exception as e:
                        logger.error(f"Error writing to {filepath}: {e}")

    logger.info(f"Scan complete. Scanned {total_files} HTML files. Cleaned {cleaned_count} files containing the redirect script.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import sys
    target_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), 'websites')
    if os.path.exists(target_dir):
        clean_html_files(target_dir)
    else:
        logger.error(f"Directory {target_dir} not found.")
