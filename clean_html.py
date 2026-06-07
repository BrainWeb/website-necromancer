import os
import re

def clean_html_files(directory):
    """
    Recursively scans the directory for HTTP/HTML files and removes
    aggressive client-side scripts that force HTTPS redirects,
    which break local file:// viewing.
    """
    # Regex to match the known aggressive redirect script:
    # <script>if (document.location.protocol != "https:") {document.location = document.URL.replace(/^http:/i, "https:");}</script>
    redirect_pattern = re.compile(
        r'<script[^>]*>\s*if\s*\(\s*document\.location\.protocol\s*!=\s*"https:"\s*\)\s*\{\s*document\.location\s*=\s*document\.URL\.replace\(\/\^http:\/i,\s*"https:"\);\s*\}\s*</script>',
        re.IGNORECASE | re.DOTALL
    )

    cleaned_count = 0
    total_files = 0

    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.html') or file.endswith('.htm'):
                total_files += 1
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    # Check and replace
                    new_content, num_subs = redirect_pattern.subn('', content)
                    
                    if num_subs > 0:
                        with open(filepath, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                        cleaned_count += 1
                        print(f"Cleaned: {filepath}")
                except Exception as e:
                    print(f"Error processing {filepath}: {e}")

    print(f"\nScan complete. Scanned {total_files} HTML files. Cleaned {cleaned_count} files containing the redirect script.")

if __name__ == "__main__":
    target_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'websites')
    if os.path.exists(target_dir):
        print(f"Starting cleanup in {target_dir}...")
        clean_html_files(target_dir)
    else:
        print(f"Directory {target_dir} not found. Have you downloaded any websites yet?")
