#!/usr/bin/env python3
import requests
import re
import subprocess
import os
import tempfile
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
from colored import fg, attr

def display_banner():
    banner = r"""
 __          __         _                _    _      _     _            
 \ \        / /        | |              | |  | |    (_)   | |           
  \ \  /\  / /_ _ _   _| |__   __ _  ___| | _| |     _ ___| |_ ___ _ __ 
   \ \/  \/ / _` | | | | '_ \ / _` |/ __| |/ / |    | / __| __/ _ \ '__|
    \  /\  / (_| | |_| | |_) | (_| | (__|   <| |____| \__ \ ||  __/ |   
     \/  \/ \__,_|\__, |_.__/ \__,_|\___|_|\_\______|_|___/\__\___|_|   
                   __/ |                                                
                  |___/                                                    

    
  _______   _                _                        __  __           _ _ ______
 |__   __| | |              | |                      |  \/  |         | ( )___  /
    | |_ __| |__   __ _  ___| | ___ __   ___  _ __   | \  / | ___   __| |/   / / 
    | | '__| '_ \ / _` |/ __| |/ / '_ \ / _ \| '_ \  | |\/| |/ _ \ / _` |   / /  
    | | |  | | | | (_| | (__|   <| | | | (_) | | | | | |  | | (_) | (_| |  / /__ 
    |_|_|  |_| |_|\__,_|\___|_|\_\_| |_|\___/|_| |_| |_|  |_|\___/ \__,_| /_____|
                                                                                 
                                                                                 
                   WaybackLister v2.0 by FR13ND0x7F
    """
    print(banner)

def fetch_wayback_urls(domain):
    print(f"[+] Querying Wayback Machine for {domain}...")
    wayback_url = (f"https://web.archive.org/cdx/search/cdx?url=*.{domain}/*"
                   "&output=txt&fl=original&collapse=urlkey&page=/")
    headers = {'User-Agent': 'WaybackLister/2.0'}

    try:
        with requests.get(wayback_url, stream=True, headers=headers, timeout=10) as resp:
            resp.raise_for_status()
            tmp = tempfile.NamedTemporaryFile(delete=False, mode="w+", encoding="utf-8")
            for line in resp.iter_lines(decode_unicode=True):
                if line.strip():
                    tmp.write(line.strip() + "\n")
            tmp.flush()
            return tmp.name
    except requests.RequestException as e:
        print(f"[-] Error fetching Wayback data: {e}")
        return None

def extract_paths_for_domain(temp_path, target_domain):
    unique = set()
    with open(temp_path, "r", encoding="utf-8") as f:
        for line in f:
            url = line.strip()
            p = urlparse(url)
            if p.hostname == target_domain:
                if p.path and p.path != "/":
                    unique.add(p.path)
    return sorted(unique)

def extract_subdomains_wayback(temp_path, domain):
    subs = set()
    parts = domain.split(".")
    suffix = "." + ".".join(parts[-2:])
    with open(temp_path, "r", encoding="utf-8") as f:
        for line in f:
            p = urlparse(line.strip())
            h = p.hostname
            if h and h.endswith(suffix) and h != domain:
                subs.add(h)
    return sorted(subs)

def get_subevil_subdomains(domain, port_scan=None):
    print(f"[+] Running SubEvil on {domain}...")
    cmd = ["python3", "SubEvil.py", "-d", domain, "-ra"]
    if port_scan:
        cmd += ["-p", ",".join(str(p) for p in port_scan)]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        subs = set()
        for line in res.stdout.splitlines():
            line = line.strip()
            if re.match(rf"^[a-zA-Z0-9\.-]+\.{re.escape(domain)}$", line) and line != domain:
                subs.add(line)
        return sorted(subs)
    except Exception as e:
        print(f"[-] SubEvil error: {e}")
        return []

def check_directory_listing(domain, path):
    patterns = [
        "Index of", "Directory Listing", "<title>Index of",
        "Parent Directory", "Name", "Size"
    ]
    headers = {'User-Agent': 'WaybackLister/2.0'}
    for proto in ("http", "https"):
        url = f"{proto}://{domain}{path}"
        try:
            r = requests.get(url, headers=headers, timeout=7, allow_redirects=True)
            if r.status_code == 200 and any(p.lower() in r.text.lower() for p in patterns):
                return url
        except requests.RequestException:
            continue
    return None

def process_domain(domain, paths, threads):
    print(f"{fg('cyan')}[+] Processing {domain}, {len(paths)} paths{attr('reset')}")
    if not paths:
        print(f"{fg('yellow')}[-] No paths to check for {domain}{attr('reset')}")
        return
    found = []
    with ThreadPoolExecutor(max_workers=threads) as exe:
        futures = [exe.submit(check_directory_listing, domain, p) for p in paths]
        for f in as_completed(futures):
            r = f.result()
            if r:
                print(f"{fg('green')}[+] Dir listing: {r}{attr('reset')}")
                found.append(r)
    if found:
        print(f"{fg('magenta')}Summary for {domain}:{attr('reset')}")
        for u in found:
            print("  -", u)
    else:
        print(f"{fg('yellow')}[-] No listings found for {domain}{attr('reset')}")

def auto_discover_and_process(domain, threads, use_subevil=False,
                             ports=None, out_file=None):
    print(f"[+] Auto mode on {domain}")
    tmp = fetch_wayback_urls(domain)
    if not tmp:
        return
    try:
        if use_subevil:
            subs = get_subevil_subdomains(domain, port_scan=ports)
        else:
            subs = extract_subdomains_wayback(tmp, domain)
        targets = [domain] + subs
        if out_file:
            with open(out_file, "w") as of:
                of.write("\n".join(targets) + "\n")
            print(f"[+] Subdomains saved to {out_file}")
        print(f"[+] Targets: {len(targets)} ->", ", ".join(targets))
        for tgt in targets:
            paths = extract_paths_for_domain(tmp, tgt)
            process_domain(tgt, paths, threads)
    finally:
        os.unlink(tmp)

def process_domains_from_file(fname, threads):
    try:
        with open(fname) as f:
            doms = [l.strip() for l in f if l.strip()]
        for d in doms:
            if not re.match(r"^(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}$", d):
                print(f"[-] Skip invalid domain {d}")
                continue
            print(f"\n[+] File target: {d}")
            tmp = fetch_wayback_urls(d)
            if not tmp:
                continue
            try:
                paths = extract_paths_for_domain(tmp, d)
                process_domain(d, paths, threads)
            finally:
                os.unlink(tmp)
    except FileNotFoundError:
        print(f"[-] File not found: {fname}")

def main():
    display_banner()
    p = argparse.ArgumentParser()
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("-d", "--domain", help="Domain to scan")
    group.add_argument("-f", "--file", help="File with domains")
    group.add_argument("-auto", help="Auto mode: discover subdomains")
    p.add_argument("-t", "--threads", type=int, default=10)
    p.add_argument("--use-subevil", action="store_true",
                   help="Use SubEvil for subdomains")
    p.add_argument("--ports", help="Port scan list for SubEvil, e.g. 80,443")
    p.add_argument("--out-sub", help="Save discovered subdomains to file")
    args = p.parse_args()

    if args.domain:
        tmp = fetch_wayback_urls(args.domain)
        if tmp:
            try:
                paths = extract_paths_for_domain(tmp, args.domain)
                process_domain(args.domain, paths, args.threads)
            finally:
                os.unlink(tmp)

    elif args.file:
        process_domains_from_file(args.file, args.threads)

    elif args.auto:
        ports = [int(p) for p in args.ports.split(",")] if args.ports else None
        auto_discover_and_process(
            args.auto, args.threads,
            use_subevil=args.use_subevil,
            ports=ports,
            out_file=args.out_sub
        )

if __name__ == "__main__":
    main()
