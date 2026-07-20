#!/usr/bin/env python3
"""
RAID - Rapid Asset & Infrastructure Discovery
A multi-threaded TCP/SYN port scanner with service detection,
banner grabbing, and JSON export.

Author: Chiranjib Saikia (Chiron)
For educational / authorized use only.
"""

import socket
import argparse
import threading
import json
import sys
from queue import Queue
from datetime import datetime

# ---------- Colors (ANSI, no external deps) ----------
class C:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

BANNER = f"""{C.RED}{C.BOLD}
 ███████████     █████████   █████ ██████████
░░███░░░░░███   ███░░░░░███ ░░███ ░░███░░░░███
 ░███    ░███  ░███    ░███  ░███  ░███   ░░███
 ░██████████   ░███████████  ░███  ░███    ░███
 ░███░░░░░███  ░███░░░░░███  ░███  ░███    ░███
 ░███    ░███  ░███    ░███  ░███  ░███    ███
 █████   █████ █████   █████ █████ ██████████
░░░░░   ░░░░░ ░░░░░   ░░░░░ ░░░░░ ░░░░░░░░░░
{C.RESET}{C.RED}      RAID — Rapid Asset & Infrastructure Discovery
{C.WHITE}      by Chiron{C.RESET}
"""

# ---------- Common ports -> service names ----------
COMMON_SERVICES = {
    21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS",
    80: "HTTP", 110: "POP3", 111: "RPCBind", 135: "MSRPC",
    139: "NetBIOS-SSN", 143: "IMAP", 443: "HTTPS", 445: "SMB",
    993: "IMAPS", 995: "POP3S", 1723: "PPTP", 3306: "MySQL",
    3389: "RDP", 5432: "PostgreSQL", 5900: "VNC", 6379: "Redis",
    8080: "HTTP-Proxy", 8443: "HTTPS-Alt", 27017: "MongoDB",
}

print_lock = threading.Lock()
results = []  # holds dicts: {port, service, banner, state}


# ---------- Banner grabbing ----------
def grab_banner(sock):
    try:
        sock.settimeout(1)
        banner = sock.recv(1024).decode(errors="ignore").strip()
        return banner if banner else ""
    except Exception:
        return ""


def identify_service(port, banner):
    if banner:
        b = banner.lower()
        if "ssh" in b:
            return "SSH"
        if "ftp" in b:
            return "FTP"
        if "http" in b or "server:" in b:
            return "HTTP"
        if "smtp" in b:
            return "SMTP"
    return COMMON_SERVICES.get(port, "unknown")


# ---------- TCP Connect Scan ----------
def tcp_scan_port(target, port, timeout):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((target, port))
        if result == 0:
            banner = grab_banner(sock)
            service = identify_service(port, banner)
            with print_lock:
                print(f"{C.GREEN}[+] Port {port:<6}{C.RESET} OPEN   "
                      f"{C.CYAN}{service:<12}{C.RESET} {banner[:40]}")
                results.append({
                    "port": port,
                    "state": "open",
                    "service": service,
                    "banner": banner
                })
        sock.close()
    except Exception:
        pass


def tcp_worker(target, timeout, q):
    while not q.empty():
        port = q.get()
        tcp_scan_port(target, port, timeout)
        q.task_done()


# ---------- SYN "Stealth" Scan (requires root + scapy) ----------
def syn_scan(target, ports, timeout):
    try:
        from scapy.all import IP, TCP, sr1, conf
        conf.verb = 0
    except ImportError:
        print(f"{C.RED}[-] scapy not installed. Run: "
              f"pip install scapy --break-system-packages{C.RESET}")
        sys.exit(1)

    print(f"{C.MAGENTA}[*] Running SYN stealth scan "
          f"(requires root privileges){C.RESET}")

    for port in ports:
        pkt = IP(dst=target) / TCP(dport=port, flags="S")
        resp = sr1(pkt, timeout=timeout)
        if resp is not None and resp.haslayer(TCP):
            flags = resp.getlayer(TCP).flags
            if flags == 0x12:  # SYN-ACK -> open
                service = COMMON_SERVICES.get(port, "unknown")
                with print_lock:
                    print(f"{C.GREEN}[+] Port {port:<6}{C.RESET} OPEN   "
                          f"{C.CYAN}{service}{C.RESET}")
                    results.append({
                        "port": port,
                        "state": "open",
                        "service": service,
                        "banner": ""
                    })
                # send RST to avoid completing handshake (stealthier)
                rst = IP(dst=target) / TCP(dport=port, flags="R")
                sr1(rst, timeout=timeout)


# ---------- Port spec parser (nmap-style: 23 | 20-100 | 22,80,443) ----------
def parse_ports(spec):
    ports = set()
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if "-" in chunk:
            start, end = chunk.split("-")
            ports.update(range(int(start), int(end) + 1))
        else:
            ports.add(int(chunk))
    return sorted(ports)


# ---------- Main ----------
def main():
    print(BANNER)

    parser = argparse.ArgumentParser(
        description="RAID - Rapid Asset & Infrastructure Discovery")
    parser.add_argument("target", help="Target IP or hostname")
    parser.add_argument("-p", "--ports", default="1-1024",
                         help="Ports to scan: single (23), range (1-1024), "
                              "or list (22,80,443). Default: 1-1024")
    parser.add_argument("-t", "--threads", type=int, default=100,
                         help="Number of threads for TCP scan (default: 100)")
    parser.add_argument("--timeout", type=float, default=1.0,
                         help="Socket timeout in seconds (default: 1.0)")
    parser.add_argument("--stealth", action="store_true",
                         help="Use SYN stealth scan instead of full TCP connect "
                              "(requires root)")
    parser.add_argument("-o", "--output", help="Export results to JSON file")
    args = parser.parse_args()

    try:
        target_ip = socket.gethostbyname(args.target)
    except socket.gaierror:
        print(f"{C.RED}[-] Could not resolve target hostname.{C.RESET}")
        return

    port_list = parse_ports(args.ports)

    print(f"{C.WHITE}{'-'*55}")
    print(f"Target      : {args.target} ({target_ip})")
    print(f"Ports       : {args.ports}  ({len(port_list)} total)")
    print(f"Mode        : {'SYN Stealth' if args.stealth else 'TCP Connect'}")
    print(f"Started at  : {datetime.now()}")
    print(f"{'-'*55}{C.RESET}")

    start_time = datetime.now()

    if args.stealth:
        syn_scan(target_ip, port_list, args.timeout)
    else:
        q = Queue()
        for port in port_list:
            q.put(port)

        threads = []
        for _ in range(args.threads):
            t = threading.Thread(target=tcp_worker,
                                  args=(target_ip, args.timeout, q))
            t.daemon = True
            t.start()
            threads.append(t)
        q.join()

    elapsed = (datetime.now() - start_time).total_seconds()

    print(f"{C.WHITE}{'-'*55}")
    print(f"Scan complete. {C.GREEN}{len(results)}{C.WHITE} open port(s) found "
          f"in {elapsed:.2f}s")
    print(f"{'-'*55}{C.RESET}")

    if args.output:
        report = {
            "target": args.target,
            "resolved_ip": target_ip,
            "scan_mode": "syn_stealth" if args.stealth else "tcp_connect",
            "port_range": args.ports,
            "scan_time": str(datetime.now()),
            "duration_seconds": elapsed,
            "open_ports_count": len(results),
            "results": sorted(results, key=lambda r: r["port"])
        }
        with open(args.output, "w") as f:
            json.dump(report, f, indent=4)
        print(f"{C.YELLOW}[*] Results exported to {args.output}{C.RESET}")


if __name__ == "__main__":
    main()
