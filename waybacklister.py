import requests
import re
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import os
import tempfile

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
    Fetch all available URLs for a given domain from the Wayback Machine and store them in a temporary file.
    """
    print(f"[+] Querying Wayback Machine for {domain}...")
    wayback_url = f"https://web.archive.org/cdx/search/cdx?url=*.{domain}/*&output=txt&fl=original&collapse=urlkey&page=/"
    
    try:
        # Create a temporary file to store the response
        temp_file = tempfile.NamedTemporaryFile(delete=False, mode="w+", encoding="utf-8")
        response = requests.get(wayback_url, stream=True)
        response.raise_for_status()
        
        # Write the response to the temporary file line by line
        for line in response.iter_lines(decode_unicode=True):
            if line:
                temp_file.write(line + "\n")
        
        temp_file.close()
        return temp_file.name  # Return the path to the temporary file
    except requests.exceptions.RequestException as e:
        print(f"[-] Error fetching data from Wayback Machine for {domain}: {e}")
        return None

def extract_unique_paths(temp_file_path):
    """
    Extract unique paths from the stored data in the temporary file.
    """
    unique_paths = set()
    with open(temp_file_path, "r", encoding="utf-8") as temp_file:
        for line in temp_file:
            url = line.strip()
            parsed_url = urlparse(url)
            path = parsed_url.path
            if path and path != "/":
                unique_paths.add(path)
    return sorted(unique_paths)

def extract_subdomains(temp_file_path, domain):
    """
    Extract unique subdomains from the stored data in the temporary file.
    """
    subdomains = set()
    domain_parts = domain.split(".")
    domain_suffix = "." + ".".join(domain_parts[-2:])  # e.g., ".example.com"
    
    with open(temp_file_path, "r", encoding="utf-8") as temp_file:
        for line in temp_file:
            url = line.strip()
            parsed_url = urlparse(url)
            hostname = parsed_url.hostname
            
            if hostname and hostname.endswith(domain_suffix) and hostname != domain:
                # Extract the subdomain part (everything before the main domain)
                subdomain = hostname[: -len(domain_suffix)].rstrip(".")
                if subdomain:
                    subdomains.add(subdomain + domain_suffix)
    
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

def process_domain(domain, threads, temp_file_path):
    """
    Process a single domain for directory listing detection using the stored data.
    """
    print(f"[+] Processing domain: {domain}")
    
    unique_paths = extract_unique_paths(temp_file_path)
    
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

def auto_discover_and_process(domain, threads):
    """
    Automatically discover subdomains for a domain and process them using the stored data.
    Also include the provided domain in the processing.
    """
    print(f"[+] Auto-discovering subdomains for {domain}...")
    temp_file_path = fetch_wayback_urls(domain)
    
    if not temp_file_path:
        print(f"[-] No archived URLs found for {domain}. Skipping.")
        return
    
    subdomains = extract_subdomains(temp_file_path, domain)
    
    # Always include the provided domain in the list of domains to process
    domains_to_process = [domain]
    if subdomains:
        print(f"[+] Found {len(subdomains)} subdomains for {domain}:")
        for subdomain in subdomains:
            print(f"  - {subdomain}")
        domains_to_process.extend(subdomains)
    else:
        print(f"[-] No subdomains found for {domain}. Processing the provided domain only.")
    
    # Process all domains (including the provided domain)
    for target_domain in domains_to_process:
        process_domain(target_domain, threads, temp_file_path)
    
    # Clean up the temporary file after processing
    os.unlink(temp_file_path)

def process_domains_from_file(file_path, threads):
    """
    Process a list of domains from a file.
    """
    try:
        with open(file_path, "r") as file:
            domains = [line.strip() for line in file if line.strip()]
        
        for domain in domains:
            print(f"\n[+] Processing domain from file: {domain}")
            # Validate domain format
            if not re.match(r"^(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$", domain):
                print(f"[-] Invalid domain format for {domain}. Skipping.")
                continue
            
            temp_file_path = fetch_wayback_urls(domain)
            if temp_file_path:
                process_domain(domain, threads, temp_file_path)
                os.unlink(temp_file_path)  # Clean up the temporary file
    except FileNotFoundError:
        print(f"[-] File not found: {file_path}")

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
        temp_file_path = fetch_wayback_urls(args.domain)
        if temp_file_path:
            process_domain(args.domain, args.threads, temp_file_path)
            os.unlink(temp_file_path)  # Clean up the temporary file
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
