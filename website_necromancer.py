#!/usr/bin/env python3

import argparse
import asyncio
import re
import os
import json
import urllib.parse
from datetime import datetime
import httpx

VERSION = "2.3.1"

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
        self.threads_count = kwargs.get('threads_count', 1)
        self.list = kwargs.get('list', False)
        
        self.processed_file_count = 0
        self.total_files = 0
        self.semaphore = asyncio.BoundedSemaphore(self.threads_count)
        self.client = None # Setup in async context

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

    def match_filter(self, filter_text, file_url):
        if not filter_text:
            return False
        if filter_text.startswith('//') and filter_text.endswith('//'):
            regex = re.compile(filter_text[2:-2])
            return bool(regex.search(file_url))
        return filter_text.lower() in file_url.lower()

    def match_only_filter(self, file_url):
        if self.only_filter is None:
            return True
        return self.match_filter(self.only_filter, file_url)

    def match_exclude_filter(self, file_url):
        if self.exclude_filter is None:
            return False
        return self.match_filter(self.exclude_filter, file_url)

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
                    if attempt < retries - 1:
                        await asyncio.sleep(2 ** attempt)
                        continue
                if e.response.status_code != 400:
                    print(f"Error fetching API listing for {url} page={page_index}: {e}")
                return []
            except httpx.ReadTimeout as e:
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                print(f"Error fetching API listing for {url} page={page_index}: {e}")
                return []
            except Exception as e:
                print(f"Error fetching API listing for {url} page={page_index}: {repr(e)}")
                return []
        return []

    async def get_all_snapshots_to_consider(self, client):
        print("Getting snapshot pages", end="", flush=True)
        snapshot_list_to_consider = []
        
        initial_list = await self.get_raw_list_from_api(client, self.base_url)
        snapshot_list_to_consider.extend(initial_list)
        print(".", end="", flush=True)
        
        if not self.exact_url:
            wildcard_url = self.base_url + "*" if self.base_url.endswith('/') else self.base_url + "/*"
            for page_index in range(self.maximum_pages):
                snapshot_list = await self.get_raw_list_from_api(client, wildcard_url, page_index)
                if not snapshot_list:
                    break
                snapshot_list_to_consider.extend(snapshot_list)
                print(".", end="", flush=True)
        
        print(f" found {len(snapshot_list_to_consider)} snapshots to consider.")
        print()
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
                # Tidy bytes logic omitted for simplicity unless requested. Python 3 handles utf-8 natively better.
                if not file_id and file_id != "":
                    print(f"Malformed file url, ignoring: {file_url}")
                    continue
                
                if self.match_exclude_filter(file_url):
                    print(f"File url matches exclude filter, ignoring: {file_url}")
                elif not self.match_only_filter(file_url):
                    print(f"File url doesn't match only filter, ignoring: {file_url}")
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
                    print(f"File url matches exclude filter, ignoring: {file_url}")
                elif not self.match_only_filter(file_url):
                    print(f"File url doesn't match only filter, ignoring: {file_url}")
                elif file_id_and_timestamp in file_list_curated:
                    pass # ignore duplicate
                else:
                    file_list_curated[file_id_and_timestamp] = {'file_url': file_url, 'timestamp': file_timestamp}
                    
        print(f"file_list_curated: {len(file_list_curated)}")
        return file_list_curated

    async def get_file_list_by_timestamp(self, client):
        if self.all_timestamps:
            curated = await self.get_file_list_all_timestamps(client)
            result = []
            for k, v in curated.items():
                v['file_id'] = k
                result.append(v)
            return result
        else:
            curated = await self.get_file_list_curated(client)
            # Sort by timestamp descending
            sorted_curated = sorted(curated.items(), key=lambda item: item[1]['timestamp'], reverse=True)
            result = []
            for k, v in sorted_curated:
                v['file_id'] = k
                result.append(v)
            return result

    def structure_dir_path(self, dir_path):
        import shutil
        try:
            os.makedirs(dir_path, exist_ok=True)
        except OSError as e:
            if e.errno == 17: # FileExistsError - File exists
                # Check if it exists as a file instead of a directory
                if os.path.isfile(dir_path):
                    temp_path = dir_path + '.temp'
                    perm_path = os.path.join(dir_path, 'index.html')
                    shutil.move(dir_path, temp_path)
                    os.makedirs(dir_path, exist_ok=True)
                    shutil.move(temp_path, perm_path)
                    print(f"{dir_path} -> {perm_path}")

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
            self.structure_dir_path(dir_path)
            
            try:
                archive_url = f"https://web.archive.org/web/{file_timestamp}id_/{file_url}"
                headers = {"Accept-Encoding": "plain"}
                
                async with self.semaphore:
                    try:
                        response = await self.client.get(archive_url, headers=headers, follow_redirects=True)
                        response.raise_for_status()
                        with open(file_path, 'wb') as f:
                            f.write(response.content)
                    except httpx.HTTPStatusError as e:
                        print(f"{file_url} # {e}")
                        if self.all:
                            with open(file_path, 'wb') as f:
                                f.write(e.response.content)
                            print(f"{file_path} saved anyway.")
                    except Exception as e:
                        print(f"{file_url} # {e}")
                        
            except Exception as e:
                print(f"{file_url} # {e}")
            finally:
                if not self.all and os.path.exists(file_path) and os.path.getsize(file_path) == 0:
                    os.remove(file_path)
                    print(f"{file_path} was empty and was removed.")
                    
            self.processed_file_count += 1
            print(f"{file_url} -> {file_path} ({self.processed_file_count}/{self.total_files})")
        else:
            self.processed_file_count += 1
            print(f"{file_url} # {file_path} already exists. ({self.processed_file_count}/{self.total_files})")


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
            print(f"Downloading {self.base_url} to {self.backup_path} from Wayback Machine archives.")
            print()
            
            if self.total_files == 0:
                print("No files to download.")
                print("Possible reasons:")
                print("\t* Site is not in Wayback Machine Archive.")
                if self.from_timestamp: print("\t* From timestamp too much in the future.")
                if self.to_timestamp: print("\t* To timestamp too much in the past.")
                if self.only_filter: print(f"\t* Only filter too restrictive ({self.only_filter})")
                if self.exclude_filter: print(f"\t* Exclude filter too wide ({self.exclude_filter})")
                return
                
            print(f"{self.total_files} files to download:")
            
            tasks = [self.download_file(file_remote_info) for file_remote_info in file_list]
            await asyncio.gather(*tasks)
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            print()
            print(f"Download completed in {duration:.2f}s, saved in {self.backup_path} ({self.total_files} files)")

def main():
    parser = argparse.ArgumentParser(
        description="Download an entire website from the Wayback Machine.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Wayback Machine by Internet Archive (archive.org) is an awesome tool to view any website at any point of time but lacks an export feature. Website Necromancer brings exactly this."
    )
    
    parser.add_argument("base_url", nargs="?", help="Website to backup (e.g., http://example.com)")
    parser.add_argument("-d", "--directory", dest="directory", help="Directory to save the downloaded files into. Default is ./websites/ plus the domain name")
    parser.add_argument("-s", "--all-timestamps", dest="all_timestamps", action="store_true", help="Download all snapshots/timestamps for a given website")
    parser.add_argument("-f", "--from", dest="from_timestamp", type=int, help="Only files on or after timestamp supplied (ie. 20060716231334)")
    parser.add_argument("-t", "--to", dest="to_timestamp", type=int, help="Only files on or before timestamp supplied (ie. 20100916231334)")
    parser.add_argument("-e", "--exact-url", dest="exact_url", action="store_true", help="Download only the url provied and not the full site")
    parser.add_argument("-o", "--only", dest="only_filter", help="Restrict downloading to urls that match this filter (use // notation for the filter to be treated as a regex)")
    parser.add_argument("-x", "--exclude", dest="exclude_filter", help="Skip downloading of urls that match this filter (use // notation for the filter to be treated as a regex)")
    parser.add_argument("-a", "--all", dest="all", action="store_true", help="Expand downloading to error files (40x and 50x) and redirections (30x)")
    parser.add_argument("-c", "--concurrency", dest="threads_count", type=int, default=1, help="Number of multiple files to download at a time. Default is one file at a time (ie. 20)")
    parser.add_argument("-p", "--maximum-snapshot", dest="maximum_pages", type=int, default=100, help="Maximum snapshot pages to consider (Default is 100). Count an average of 150,000 snapshots per page")
    parser.add_argument("-l", "--list", dest="list", action="store_true", help="Only list file urls in a JSON format with the archived timestamps, won't download anything")
    parser.add_argument("-v", "--version", action="version", version=VERSION, help="Display version")
    
    args = parser.parse_args()
    
    if args.base_url:
        downloader = WebsiteNecromancer(**vars(args))
        asyncio.run(downloader.run())
    else:
        print("You need to specify a website to backup. (e.g., http://example.com)")
        print("Run `website_necromancer.py --help` for more help.")

if __name__ == "__main__":
    main()
