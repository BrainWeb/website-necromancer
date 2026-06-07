import pytest
import os
import shutil
import clean_html
import rewrite_links
import mark_missing_links

@pytest.fixture
def test_dir():
    dir_name = "test_websites"
    os.makedirs(dir_name, exist_ok=True)
    yield dir_name
    shutil.rmtree(dir_name)

def test_clean_html_removes_redirects(test_dir):
    file_path = os.path.join(test_dir, "test.html")
    bad_html = '<html><head><script>if (document.location.protocol != "https:") {document.location = document.URL.replace(/^http:/i, "https:");}</script></head><body>Hello</body></html>'
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(bad_html)
        
    clean_html.clean_html_files(test_dir)
    
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    assert "<script>" not in content
    assert "Hello" in content

def test_clean_html_handles_bad_encoding(test_dir):
    file_path = os.path.join(test_dir, "bad_encoding.html")
    # Write some invalid utf-8 bytes
    with open(file_path, "wb") as f:
        f.write(b'<html><body>\xff\xfeHello</body></html>')
        
    # Should not crash
    clean_html.clean_html_files(test_dir)

def test_rewrite_links(test_dir):
    file_path = os.path.join(test_dir, "index.html")
    html = '<html><body><a href="http://example.com/about">About</a> <img src="https://www.example.com/img.png"></body></html>'
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html)
        
    rewrite_links.rewrite_links(test_dir, "example.com")
    
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    assert 'href="./about/index.html"' in content
    assert 'src="./img.png"' in content

def test_mark_missing_links(test_dir):
    # Setup test file
    file_path = os.path.join(test_dir, "index.html")
    html = '<html><body><a href="missing.html">Click Here</a></body></html>'
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html)
        
    # Missing.html does NOT exist, so it should be marked
    mark_missing_links.mark_missing_links(test_dir)
    
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    assert 'Click Here [Not Archived]' in content
