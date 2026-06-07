#!/usr/bin/env python3

import argparse
import asyncio
import re
import os
import json
import urllib.parse
from datetime import datetime
import httpx
import aiofiles
import logging

from settings import load_settings, save_settings
import clean_html
import rewrite_links
import mark_missing_links

VERSION = "3.0.0"

logger = logging.getLogger(__name__)

class WebsiteNecromancer:
    def __init__(self, **kwargs):
        self.base_url = kwargs.get('base_url')
        self.exact_url = kwargs.get('exact_url', False)
        self.directory = kwargs.get('directory')
        self.all_timestamps = kwargs.get('all_timestamps', False)
        self.from_timestamp = int(kwargs['from_timestamp']) if kwargs.get('from_timestamp') else None
        self.to_timestamp = int(kwargs['to_timestamp']) if kwargs.get('to_timestamp') else None
        self.only_filter = kwargs.get('only_filter')
        self.exclude_filter = kwargs.get('exclude_filter')
        self.all = kwargs.get('all', False)
        self.maximum_pages = kwargs.get('maximum_pages', 100)
        self.threads_count = kwargs.get('threads_count', 10)
        self.list = kwargs.get('list', False)
        
        self.processed_file_count = 0
        self.total_files = 0
        self.semaphore = asyncio.BoundedSemaphore(self.threads_count)
        self.client = None # Setup in async context
        
        # Compile regexes once
        self.only_regex = None
        if self.only_filter and self.only_filter.startswith('//') and self.only_filter.endswith('//'):
            self.only_regex = re.compile(self.only_filter[2:-2])
            
        self.exclude_regex = None
        if self.exclude_filter and self.exclude_filter.startswith('//') and self.exclude_filter.endswith('//'):
            self.exclude_regex = re.compile(self.exclude_filter[2:-2])

    @property
    def backup_name(self):
        if '//' in self.base_url:
            return self.base_url.split('/')[2]
        return self.base_url

    @property
    def backup_path(self):
        if self.directory:
            return self.directory if self.directory.endswith('/') else self.directory + '/'
        return f'websites/{self.backup_name}/'

    def match_filter(self, filter_text, file_url, compiled_regex):
        if not filter_text:
            return False
        if compiled_regex:
            return bool(compiled_regex.search(file_url))
        return filter_text.lower() in file_url.lower()

    def match_only_filter(self, file_url):
        if self.only_filter is None:
            return True
        return self.match_filter(self.only_filter, file_url, self.only_regex)

    def match_exclude_filter(self, file_url):
        if self.exclude_filter is None:
            return False
        return self.match_filter(self.exclude_filter, file_url, self.exclude_regex)

    async def get_raw_list_from_api(self, client, url, page_index=None):
        request_url = "https://web.archive.org/cdx/search/xd"
        params = [("output", "json"), ("url", url), ("fl", "timestamp,original"), ("collapse", "digest"), ("gzip", "false")]
        
        if not self.all:
            params.append(("filter", "statuscode:200"))
        if self.from_timestamp:
            params.append(("from", str(self.from_timestamp)))
        if self.to_timestamp:
            params.append(("to", str(self.to_timestamp)))
        if page_index is not None:
            params.append(("page", str(page_index)))

        retries = 3
        for attempt in range(retries):
            try:
                response = await client.get(request_url, params=params, timeout=30.0)
                response.raise_for_status()
                data = response.json()
                if not data:
                    return []
                if data[0] == ["timestamp", "original"]:
                    data.pop(0)
                return data
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (502, 503, 504):
                    logger.warning(f"API HTTP {e.response.status_code} for {url} page={page_index}. Retrying {attempt+1}/{retries}...")
                    if attempt < retries - 1:
                        await asyncio.sleep(2 ** attempt)
                        continue
                if e.response.status_code != 400:
                    logger.error(f"Error fetching API listing for {url} page={page_index}: {e}")
                return []
            except httpx.ReadTimeout as e:
                logger.warning(f"API Timeout for {url} page={page_index}. Retrying {attempt+1}/{retries}...")
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                logger.error(f"Timeout Error fetching API listing for {url}: {e}")
                return []
            except Exception as e:
                logger.error(f"Error fetching API listing for {url} page={page_index}: {repr(e)}")
                return []
        return []

    async def get_all_snapshots_to_consider(self, client):
        logger.info("Getting snapshot pages...")
        snapshot_list_to_consider = []
        
        initial_list = await self.get_raw_list_from_api(client, self.base_url)
        snapshot_list_to_consider.extend(initial_list)
        
        if not self.exact_url:
            wildcard_url = self.base_url + "*" if self.base_url.endswith('/') else self.base_url + "/*"
            for page_index in range(self.maximum_pages):
                snapshot_list = await self.get_raw_list_from_api(client, wildcard_url, page_index)
                if not snapshot_list:
                    break
                snapshot_list_to_consider.extend(snapshot_list)
                if page_index % 10 == 0:
                    logger.debug(f"Fetched {page_index+1} snapshot pages...")
        
        logger.info(f"Found {len(snapshot_list_to_consider)} snapshots to consider.")
        return snapshot_list_to_consider

    async def get_file_list_curated(self, client):
        file_list_curated = {}
        snapshots = await self.get_all_snapshots_to_consider(client)
        
        for file_timestamp, file_url in snapshots:
            if '/' not in file_url:
                continue
            
            parts = file_url.split('/')
            if len(parts) >= 4:
                file_id = '/'.join(parts[3:])
                file_id = urllib.parse.unquote(file_id)
                
                if not file_id and file_id != "":
                    logger.debug(f"Malformed file url, ignoring: {file_url}")
                    continue
                
                if self.match_exclude_filter(file_url):
                    logger.debug(f"File url matches exclude filter, ignoring: {file_url}")
                elif not self.match_only_filter(file_url):
                    logger.debug(f"File url doesn't match only filter, ignoring: {file_url}")
                elif file_id in file_list_curated:
                    if not (file_list_curated[file_id]['timestamp'] > file_timestamp):
                        file_list_curated[file_id] = {'file_url': file_url, 'timestamp': file_timestamp}
                else:
                    file_list_curated[file_id] = {'file_url': file_url, 'timestamp': file_timestamp}

        return file_list_curated

    async def get_file_list_all_timestamps(self, client):
        file_list_curated = {}
        snapshots = await self.get_all_snapshots_to_consider(client)
        
        for file_timestamp, file_url in snapshots:
            if '/' not in file_url:
                continue
            
            parts = file_url.split('/')
            if len(parts) >= 4:
                file_id = '/'.join(parts[3:])
                file_id_and_timestamp = f"{file_timestamp}/{file_id}"
                file_id_and_timestamp = urllib.parse.unquote(file_id_and_timestamp)
                
                if self.match_exclude_filter(file_url):
                    pass
                elif not self.match_only_filter(file_url):
                    pass
                elif file_id_and_timestamp not in file_list_curated:
                    file_list_curated[file_id_and_timestamp] = {'file_url': file_url, 'timestamp': file_timestamp}
                    
        return file_list_curated

    async def get_file_list_by_timestamp(self, client):
        if self.all_timestamps:
            curated = await self.get_file_list_all_timestamps(client)
        else:
            curated = await self.get_file_list_curated(client)
            
        sorted_curated = sorted(curated.items(), key=lambda item: item[1]['timestamp'], reverse=True)
        result = []
        for k, v in sorted_curated:
            v['file_id'] = k
            result.append(v)
        return result

    async def structure_dir_path(self, dir_path):
        def _make_dirs():
            import shutil
            try:
                os.makedirs(dir_path, exist_ok=True)
            except OSError as e:
                if e.errno == 17: # FileExistsError - File exists
                    if os.path.isfile(dir_path):
                        temp_path = dir_path + '.temp'
                        perm_path = os.path.join(dir_path, 'index.html')
                        shutil.move(dir_path, temp_path)
                        os.makedirs(dir_path, exist_ok=True)
                        shutil.move(temp_path, perm_path)
        await asyncio.to_thread(_make_dirs)

    async def download_file(self, file_remote_info):
        file_url = file_remote_info['file_url']
        file_id = file_remote_info['file_id']
        file_timestamp = file_remote_info['timestamp']
        
        file_path_elements = file_id.split('/')
        if file_id == "":
            dir_path = self.backup_path
            file_path = os.path.join(self.backup_path, 'index.html')
        elif file_url.endswith('/') or '.' not in file_path_elements[-1]:
            dir_path = os.path.join(self.backup_path, *file_path_elements)
            file_path = os.path.join(dir_path, 'index.html')
        else:
            dir_path = os.path.join(self.backup_path, *file_path_elements[:-1]) if len(file_path_elements) > 1 else self.backup_path
            file_path = os.path.join(self.backup_path, *file_path_elements)
            
        if os.name == 'nt':
            dir_path = re.sub(r'[:*?&=<>\\|]', lambda m: '%' + hex(ord(m.group(0)))[2:], dir_path)
            file_path = re.sub(r'[:*?&=<>\\|]', lambda m: '%' + hex(ord(m.group(0)))[2:], file_path)
            
        if not os.path.exists(file_path):
            await self.structure_dir_path(dir_path)
            
            try:
                archive_url = f"https://web.archive.org/web/{file_timestamp}id_/{file_url}"
                headers = {"Accept-Encoding": "plain"}
                
                async with self.semaphore:
                    retries = 3
                    for attempt in range(retries):
                        try:
                            async with self.client.stream('GET', archive_url, headers=headers, follow_redirects=True, timeout=30.0) as response:
                                response.raise_for_status()
                                async with aiofiles.open(file_path, 'wb') as f:
                                    async for chunk in response.aiter_bytes():
                                        await f.write(chunk)
                            break # success
                        except httpx.HTTPStatusError as e:
                            if e.response.status_code in (502, 503, 504):
                                if attempt < retries - 1:
                                    await asyncio.sleep(2 ** attempt)
                                    continue
                            logger.error(f"Download Error {e.response.status_code} for {file_url}")
                            if self.all:
                                async with aiofiles.open(file_path, 'wb') as f:
                                    await f.write(e.response.content)
                                logger.info(f"{file_path} saved anyway.")
                            break
                        except httpx.RequestError as e:
                            if attempt < retries - 1:
                                await asyncio.sleep(2 ** attempt)
                                continue
                            logger.error(f"Download Request Error for {file_url}: {e}")
                            break
                        
            except Exception as e:
                logger.error(f"Unexpected error for {file_url}: {e}")
            finally:
                if not self.all and os.path.exists(file_path) and os.path.getsize(file_path) == 0:
                    os.remove(file_path)
                    logger.debug(f"{file_path} was empty and was removed.")
                    
            self.processed_file_count += 1
            logger.info(f"{file_url} -> {file_path} ({self.processed_file_count}/{self.total_files})")
        else:
            self.processed_file_count += 1
            logger.debug(f"{file_url} # {file_path} already exists. ({self.processed_file_count}/{self.total_files})")


    async def run(self):
        async with httpx.AsyncClient(timeout=30.0) as client:
            self.client = client
            file_list = await self.get_file_list_by_timestamp(client)
            
            if self.list:
                print("[")
                for i, file_info in enumerate(file_list):
                    print(json.dumps(file_info) + ("," if i < len(file_list) - 1 else ""))
                print("]")
                return

            self.total_files = len(file_list)
            
            start_time = datetime.now()
            logger.info(f"Downloading {self.base_url} to {self.backup_path} from Wayback Machine archives.")
            
            if self.total_files == 0:
                logger.warning("No files to download.")
                return
                
            logger.info(f"{self.total_files} files to download:")
            
            tasks = [self.download_file(file_remote_info) for file_remote_info in file_list]
            await asyncio.gather(*tasks)
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            logger.info(f"Download completed in {duration:.2f}s, saved in {self.backup_path} ({self.total_files} files)")

        # Run Post-Processing Pipeline
        logger.info("\n--- Beginning Post-Processing Pipeline ---")
        try:
            clean_html.clean_html_files(self.backup_path)
            rewrite_links.rewrite_links(self.backup_path, self.backup_name)
            mark_missing_links.mark_missing_links(self.backup_path)
            logger.info("--- Post-Processing Complete ---")
            logger.info(f"Your resurrected site is ready at {self.backup_path}index.html")
        except Exception as e:
            logger.error(f"Post-processing pipeline failed: {e}")

def setup_logging(settings_override, verbose=False):
    settings = load_settings()
    log_settings = settings.get('logging', {})
    
    # Overrides
    if verbose:
        log_settings['level'] = "DEBUG"
    if settings_override.get('log_file'):
        log_settings['file'] = True
        log_settings['log_file_path'] = settings_override['log_file']

    handlers = []
    if log_settings.get('console'):
        handlers.append(logging.StreamHandler(sys.stdout))
    if log_settings.get('file'):
        handlers.append(logging.FileHandler(log_settings.get('log_file_path', 'necromancer.log')))

    logging.basicConfig(
        level=getattr(logging, log_settings.get('level', 'INFO').upper()),
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=handlers
    )

def main():
    parser = argparse.ArgumentParser(
        description="Download an entire website from the Wayback Machine and prepare it for local viewing.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument("base_url", nargs="?", help="Website to backup (e.g., http://example.com)")
    parser.add_argument("-d", "--directory", dest="directory", help="Directory to save the downloaded files into. Default is ./websites/ plus the domain name")
    parser.add_argument("-s", "--all-timestamps", dest="all_timestamps", action="store_true", help="Download all snapshots/timestamps for a given website")
    parser.add_argument("-f", "--from", dest="from_timestamp", type=int, help="Only files on or after timestamp supplied")
    parser.add_argument("-t", "--to", dest="to_timestamp", type=int, help="Only files on or before timestamp supplied")
    parser.add_argument("-e", "--exact-url", dest="exact_url", action="store_true", help="Download only the url provied and not the full site")
    parser.add_argument("-o", "--only", dest="only_filter", help="Restrict downloading to urls that match this filter")
    parser.add_argument("-x", "--exclude", dest="exclude_filter", help="Skip downloading of urls that match this filter")
    parser.add_argument("-a", "--all", dest="all", action="store_true", help="Expand downloading to error files (40x and 50x) and redirections (30x)")
    parser.add_argument("-c", "--concurrency", dest="threads_count", type=int, default=10, help="Number of multiple files to download at a time.")
    parser.add_argument("-p", "--maximum-snapshot", dest="maximum_pages", type=int, default=100, help="Maximum snapshot pages to consider")
    parser.add_argument("-l", "--list", dest="list", action="store_true", help="Only list file urls in a JSON format")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose DEBUG logging")
    parser.add_argument("--log-file", dest="log_file", help="File to write logs to (e.g., necromancer.log)")
    parser.add_argument("--version", action="version", version=VERSION, help="Display version")
    
    args = parser.parse_args()
    
    setup_logging({'log_file': args.log_file}, verbose=args.verbose)
    
    if args.base_url:
        downloader = WebsiteNecromancer(**vars(args))
        asyncio.run(downloader.run())
    else:
        logger.error("You need to specify a website to backup. (e.g., http://example.com)")
        logger.error("Run `website_necromancer.py --help` for more help.")

if __name__ == "__main__":
    import sys
    main()
