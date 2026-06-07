# Website Necromancer

A unified Python toolkit to download, resurrect, and locally host websites from the Internet Archive's Wayback Machine. This project provides an asynchronous Python rewrite of the original Ruby `wayback-machine-downloader`, along with an **automated post-processing pipeline** that automatically scrubs aggressive redirects, rewrites absolute links to local relative paths, and tags broken missing links so you can browse the archived website completely offline.

## Getting Started

**Prerequisites:** Python 3.10+

1. Install dependencies:
   ```bash
   pip3 install -r requirements.txt
   ```
2. Set the `GEMINI_API_KEY` in `.env.local` to your Gemini API key (if applicable).

## Workflow & Usage

The entire resurrection workflow is now handled automatically by the main script. All downloaded files are stored in a `websites/<domain>` directory.

### 1. Download & Process the Website

Run the main script to fetch the site from the Wayback Machine. Once the download finishes, the script will **automatically** run the internal cleaning, link-rewriting, and link-marking phases so the site is immediately ready for offline viewing.

```bash
python3 website_necromancer.py http://example.com -c 10
```

**Options:**
```text
usage: website_necromancer.py [-h] [-d DIRECTORY] [-s] [-f FROM_TIMESTAMP] [-t TO_TIMESTAMP] [-e] [-o ONLY_FILTER] [-x EXCLUDE_FILTER] [-a] [-c THREADS_COUNT] [-p MAXIMUM_PAGES] [-l] [-v] [--log-file LOG_FILE] [base_url]

options:
  -c THREADS_COUNT      Number of concurrent files to download at a time. Default is 10.
  -d DIRECTORY          Directory to save the downloaded files into. Default is ./websites/ plus the domain name
  -f FROM_TIMESTAMP     Only files on or after timestamp supplied (ie. 20060716231334)
  -t TO_TIMESTAMP       Only files on or before timestamp supplied (ie. 20100916231334)
  -v, --verbose         Enable verbose DEBUG logging
  --log-file            File to write logs to (e.g., necromancer.log)
  ... (run with -h for all options)
```

### 2. Browse Locally

Simply navigate to `websites/example.com/index.html` and open it in your browser!

---

## Configuration

You can customize default logging settings in `necromancer_settings.json`:
```json
{
    "logging": {
        "console": true,
        "file": true,
        "log_file_path": "necromancer.log",
        "level": "INFO"
    }
}
```

---

## Automated Tests

This project includes a robust test suite using `pytest` and `respx` to mock network unreliability (503s and timeouts) without spamming the Internet Archive.

Run the tests:
```bash
python3 -m pytest tests/
```

## Scripts Included in the Unified Pipeline

The following scripts were originally standalone but are now automatically executed sequentially at the end of the `website_necromancer.py` run:
- `clean_html.py`: Strips out `<script>` tags that force `https://` redirects, which breaks local viewing.
- `rewrite_links.py`: Scans all HTML/CSS files and converts absolute domain links (e.g., `http://example.com/about`) into local relative paths (e.g., `./about/index.html`).
- `mark_missing_links.py`: Scans the final local directory for missing `.html` files and appends `[Not Archived]` to any broken links.