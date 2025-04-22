import requests
import re
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse

def display_banner():
    """
    Display the tool banner.
    """
    banner = r"""
 __          __         _                _    _      _     _            
 \ \        / /        | |              | |  | |    (_)   | |           
  \ \  /\  / /_ _ _   _| |__   __ _  ___| | _| |     _ ___| |_ ___ _ __ 
   \ \/  \/ / _` | | | | '_ \ / _` |/ __| |/ / |    | / __| __/ _ \ '__|
    \  /\  / (_| | |_| | |_) | (_| | (__|   <| |____| \__ \ ||  __/ |   
     \/  \/ \__,_|\__, |_.__/ \__,_|\___|_|\_\______|_|___/\__\___|_|   
                   __/ |                                                
                  |___/                                                    
                                             
                   WaybackLister v1.0 by FR13ND0x7F
           Detect Directory Listings Using Wayback Machine
    """
    print(banner)

def fetch_wayback_urls(domain):
    """
    Fetch all available URLs for a given domain from the Wayback Machine.
    """
    print(f"[+] Querying Wayback Machine for {domain}...")
    wayback_url = f"http://web.archive.org/cdx/search/cdx?url={domain}/*&output=json&collapse=urlkey&fl=original"
    
    try:
        response = requests.get(wayback_url)
        response.raise_for_status()
        data = response.json()
        
        # Extract URLs from the JSON response (skip the header)
        if len(data) > 1:
            return [entry[0] for entry in data[1:]]
        else:
            print(f"[-] No archived URLs found for {domain}.")
            return []
    except requests.exceptions.RequestException as e:
        print(f"[-] Error fetching data from Wayback Machine for {domain}: {e}")
        return []

def extract_unique_paths(urls):
    """
    Extract unique paths from a list of URLs.
    """
    unique_paths = set()
    for url in urls:
        parsed_url = urlparse(url)
        path = parsed_url.path
        if path and path != "/":
            unique_paths.add(path)
    return sorted(unique_paths)

def extract_subdomains(urls, domain):
    """
    Extract unique subdomains from a list of URLs.
    """
    subdomains = set()
    pattern = re.compile(rf"^https?://([a-zA-Z0-9.-]+)?\.{re.escape(domain)}")
    for url in urls:
        match = pattern.match(url)
        if match:
            subdomains.add(match.group(1) + "." + domain)
    return sorted(subdomains)

def check_directory_listing(domain, path):
    """
    Check if a specific path has directory listing enabled.
    """
    url = f"http://{domain}{path}"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200 and "Index of /" in response.text:
            return url
    except requests.exceptions.RequestException:
        pass
    return None

def process_domain(domain, threads):
    """
    Process a single domain for directory listing detection.
    """
    print(f"[+] Processing domain: {domain}")
    archived_urls = fetch_wayback_urls(domain)
    
    if not archived_urls:
        print(f"[-] No data to process for {domain}. Skipping.")
        return
    
    unique_paths = extract_unique_paths(archived_urls)
    
    if not unique_paths:
        print(f"[-] No unique paths found for {domain}.")
        return
    
    print(f"[+] Found {len(unique_paths)} unique paths for {domain}. Checking for directory listings...")
    
    # Use multithreading to check paths concurrently
    directory_listings = []
    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = [executor.submit(check_directory_listing, domain, path) for path in unique_paths]
        for future in as_completed(futures):
            result = future.result()
            if result:
                directory_listings.append(result)
                print(f"[+] Directory Listing Found: {result}")
    
    if directory_listings:
        print(f"\n[+] Summary of Directory Listings for {domain}:")
        for listing in directory_listings:
            print(listing)
    else:
        print(f"[-] No directory listings found for {domain}.")

def process_domains_from_file(file_path, threads):
    """
    Process a list of domains from a file.
    """
    try:
        with open(file_path, "r") as file:
            domains = [line.strip() for line in file if line.strip()]
        
        for domain in domains:
            process_domain(domain, threads)
    except FileNotFoundError:
        print(f"[-] File not found: {file_path}")

def auto_discover_and_process(domain, threads):
    """
    Automatically discover subdomains for a domain and process them.
    """
    print(f"[+] Auto-discovering subdomains for {domain}...")
    archived_urls = fetch_wayback_urls(domain)
    
    if not archived_urls:
        print(f"[-] No archived URLs found for {domain}. Skipping.")
        return
    
    subdomains = extract_subdomains(archived_urls, domain)
    
    if not subdomains:
        print(f"[-] No subdomains found for {domain}.")
        return
    
    print(f"[+] Found {len(subdomains)} subdomains for {domain}:")
    for subdomain in subdomains:
        print(f"  - {subdomain}")
    
    for subdomain in subdomains:
        process_domain(subdomain, threads)

def main():
    # Display the banner
    display_banner()

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="WaybackLister - Detect Directory Listings Using Wayback Machine.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-d", "--domain", help="Single target domain to scan (e.g., example.com)")
    group.add_argument("-f", "--file", help="File containing a list of domains to scan (one per line)")
    group.add_argument("-auto", help="Automatically discover and scan subdomains for the given domain")
    parser.add_argument("-t", "--threads", type=int, default=10, help="Number of threads to use for active checks (default: 10)")
    args = parser.parse_args()

    if args.domain:
        # Validate domain format
        if not re.match(r"^(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$", args.domain):
            print("[-] Invalid domain format. Please enter a valid domain (e.g., example.com).")
            return
        process_domain(args.domain, args.threads)
    elif args.file:
        process_domains_from_file(args.file, args.threads)
    elif args.auto:
        # Validate domain format
        if not re.match(r"^(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$", args.auto):
            print("[-] Invalid domain format. Please enter a valid domain (e.g., example.com).")
            return
        auto_discover_and_process(args.auto, args.threads)

if __name__ == "__main__":
    main()
