# Website Necromancer

A suite of Python scripts to download, resurrect, and locally host websites from the Internet Archive's Wayback Machine. This project provides an asynchronous Python rewrite of the original Ruby `wayback-machine-downloader` (now called Website Necromancer), along with post-processing tools to ensure the downloaded websites work perfectly offline.

## Features

- **`website_necromancer.py`**: Fast, asynchronous downloading of an entire website from the Wayback Machine.
- **`rewrite_links.py`**: Converts absolute URLs to relative paths and appends `index.html` where necessary, enabling seamless offline browsing via the `file://` protocol.
- **`clean_html.py`**: Removes aggressive JavaScript redirects that force HTTPS, preventing local viewing from breaking.
- **`mark_missing_links.py`**: Scans the downloaded site and visually tags broken links with `[Not Archieved]`, so you know exactly which pages couldn't be recovered.

## Installation

Requires Python 3.7+.

1. Clone the repository and navigate into it.
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Workflow & Usage

A typical resurrection workflow consists of downloading the site and then running the post-processing scripts. All downloaded files are stored in a `websites/<domain>` directory.

### 1. Download the Website

Use the main downloader script to fetch the site from the Wayback Machine.

```bash
python website_necromancer.py http://example.com -c 10
```

**Options:**
```text
usage: website_necromancer.py [-h] [-d DIRECTORY] [-s] [-f FROM_TIMESTAMP] [-t TO_TIMESTAMP] [-e] [-o ONLY_FILTER] [-x EXCLUDE_FILTER] [-a] [-c THREADS_COUNT] [-p MAXIMUM_PAGES] [-l] [-v] [base_url]

options:
  -c THREADS_COUNT      Number of multiple files to download at a time. Default is one file at a time (ie. 20)
  -d DIRECTORY          Directory to save the downloaded files into. Default is ./websites/ plus the domain name
  -f FROM_TIMESTAMP     Only files on or after timestamp supplied (ie. 20060716231334)
  -t TO_TIMESTAMP       Only files on or before timestamp supplied (ie. 20100916231334)
  -o ONLY_FILTER        Restrict downloading to urls that match this filter
  -x EXCLUDE_FILTER     Skip downloading of urls that match this filter
  -a, --all             Expand downloading to error files (40x and 50x) and redirections (30x)
  ... (run with -h for all options)
```

### 2. Clean Aggressive Redirects

Some older sites contain scripts that force `https://` redirects, which will break local viewing. Clean them out:

```bash
python clean_html.py
```
*(This automatically scans the `websites/` folder).*

### 3. Rewrite Links for Offline Browsing

To browse the site locally without a web server, absolute URLs need to be made relative, and directory links need `index.html` appended to them.

```bash
python rewrite_links.py example.com
```

### 4. Mark Missing Links (Optional)

Identify which parts of the site were not successfully archived by marking dead links:

```bash
python mark_missing_links.py example.com
```
*(This will append `[Not Archieved]` to links pointing to missing local files).*

## License

MIT License (or as specified by the original tool authors).

---

Built and maintained by BrainWeb, a web design studio in Norfolk, UK