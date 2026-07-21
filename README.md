# RAID — Rapid Asset & Infrastructure Discovery

A multi-threaded network reconnaissance tool built in Python. RAID performs
TCP connect scans or SYN "stealth" scans, identifies running services via
banner grabbing and port mapping, and exports results to JSON for use in
reporting pipelines.

## Features

- **Multi-threaded TCP connect scan** — fast, no root required
- **SYN stealth scan** (via Scapy) — sends raw SYN packets, avoids completing
  the TCP handshake, harder to log on the target side
- **Service detection** — identifies services from banners and a built-in
  port/service mapping (FTP, SSH, HTTP, SMB, RDP, MySQL, etc.)
- **OS detection (best-effort)** — TTL-based fingerprinting to guess the
  target's OS family
- **Banner grabbing** — captures service banners on open ports
- **JSON export** — structured output for use in reports or other tooling
- **Colorized CLI output** for readability during live scans

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/your-repo-name.git
cd your-repo-name/RAID          # adjust path if nested differently

# 2. (Recommended) create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
```

Note: `scapy` is only required for `--stealth` and `--os` modes. Standard
TCP connect scans work with zero external dependencies — just the Python
standard library.

**Optional — install as a global command** (so you can run `raid` instead
of `python3 raid.py` from anywhere):
```bash
chmod +x raid.py
sudo cp raid.py /usr/local/bin/raid
```
If you do this, also install scapy outside the venv so `sudo raid` can find
it: `pip install scapy --break-system-packages`.

## How it works — with examples

### 1. Port scanning
RAID checks whether a port is open by attempting a connection to it.
- **TCP connect mode** completes a full handshake using Python sockets.
- **Stealth mode** sends a raw SYN packet and checks for a SYN-ACK, without
  completing the handshake.

Either way, the output looks like this:

```
$ raid -p 20-25 192.168.1.50

[+] Port 22     OPEN   SSH          SSH-2.0-OpenSSH_8.9p1
[+] Port 25     OPEN   SMTP         220 mail.local ESMTP Postfix
-------------------------------------------------------
Scan complete. 2 open port(s) found in 0.84s
```
Ports 20, 21, 23, 24 aren't shown because they're closed/filtered — RAID
only prints ports that respond as open.

### 2. Service detection
This is **not** the same as OS detection (see note below). Service detection
means: "what application is running on this open port?" RAID figures this
out two ways, in order:
1. **Banner parsing** — if the service sends text when connected to (many
   do, like SSH or FTP), RAID reads it and looks for keywords (`ssh`,
   `ftp`, `http`, `smtp`).
2. **Port mapping fallback** — if no useful banner is received (common for
   HTTPS, databases, or services that don't send data first), RAID falls
   back to a static dictionary of well-known ports, e.g. `443 → HTTPS`,
   `3306 → MySQL`, `3389 → RDP`.

Example — a service that sends a banner vs. one that doesn't:
```
[+] Port 22     OPEN   SSH          SSH-2.0-OpenSSH_8.9p1     <- from banner
[+] Port 443    OPEN   HTTPS                                  <- from port map, no banner
```

### 3. OS detection (TTL fingerprinting)
RAID can take a best-effort guess at the target's operating system using
**TTL (Time To Live) fingerprinting** — the same first-pass heuristic real
tools like Nmap use before deeper stack analysis. Different OS families ship
with different default TTL values, and TTL decreases by 1 with every network
hop. By comparing the TTL we receive against the nearest common default, we
can estimate both the likely OS family and roughly how many hops away the
target is.

| Received TTL near... | Likely OS |
|---|---|
| 64  | Linux / Unix / macOS |
| 128 | Windows |
| 255 | Cisco devices / older Unix / Solaris |

Usage:
```
$ raid -p 20-25 192.168.1.50 --os

[*] OS Guess : Linux/Unix/macOS (TTL=61, ~3 hop(s) from nearest default 64)
```

**Important honesty note:** this is a *guess*, not a certainty. TTL values
can be spoofed, altered by firewalls/proxies, or coincidentally match a
different OS. Nmap's real OS detection (`-O`) is far more accurate because
it analyzes dozens of signals — TCP window size, options ordering, ISN
sampling, and more — not just one header field. RAID's `--os` flag is meant
as a lightweight, educational first signal, not a replacement for proper
fingerprinting tools. Requires `scapy` and a target that responds to ICMP
(some firewalls block this, in which case `--os` will report failure).

### 4. JSON export
Useful for saving a scan for later or feeding it into another script/report.
```
$ raid -p 20-25 192.168.1.50 -o scan.json
```
Produces:
```json
{
    "target": "192.168.1.50",
    "resolved_ip": "192.168.1.50",
    "scan_mode": "tcp_connect",
    "port_range": "20-25",
    "scan_time": "2026-07-20 17:03:11.204552",
    "duration_seconds": 0.84,
    "os_detection": {"ttl": 61, "guessed_default": 64, "estimated_hops": 3, "os_guess": "Linux/Unix/macOS"},
    "open_ports_count": 2,
    "results": [
        {"port": 22, "state": "open", "service": "SSH", "banner": "SSH-2.0-OpenSSH_8.9p1"},
        {"port": 25, "state": "open", "service": "SMTP", "banner": "220 mail.local ESMTP Postfix"}
    ]
}
```

## Usage

```bash
# Basic TCP connect scan
python3 raid.py 192.168.1.10 -p 1-1024

# Single port (nmap-style, attached flag works too)
python3 raid.py 192.168.1.10 -p23
raid -p23 192.168.1.10          # after global install, see below

# Comma-separated port list
python3 raid.py 192.168.1.10 -p 22,80,443

# Faster scan with more threads
python3 raid.py 192.168.1.10 -p 1-65535 -t 300

# SYN stealth scan (requires root)
sudo python3 raid.py 192.168.1.10 -p 1-1024 --stealth

# Export results to JSON
python3 raid.py 192.168.1.10 -p 1-1024 -o results.json

# With OS detection (best-effort, requires scapy)
python3 raid.py 192.168.1.10 -p 1-1024 --os
```

## Running it as a global `raid` command

Once installed as described above, you can run it as just `raid`:
```bash
raid -p23 127.0.0.1
raid -p 22,80,443 127.0.0.1
sudo raid -p 1-1024 127.0.0.1 --stealth
sudo raid -p 1-1024 127.0.0.1 --os
```

## Arguments

| Flag | Description | Default |
|---|---|---|
| `target` | Target IP or hostname | required |
| `-p, --ports` | Ports: single (`23`), range (`1-1024`), or list (`22,80,443`) | `1-1024` |
| `-t, --threads` | Number of threads (TCP mode only) | `100` |
| `--timeout` | Socket timeout in seconds | `1.0` |
| `--stealth` | Use SYN scan instead of TCP connect | off |
| `--os` | Attempt OS detection via ICMP TTL fingerprinting | off |
| `-o, --output` | Export results to a JSON file | none |

## Legal / Ethical Use

This tool is intended strictly for authorized security testing — your own
lab environments, machines you own, or targets you have explicit written
permission to test (e.g. HackTheBox, TryHackMe, CTF infrastructure).
Scanning systems without authorization is illegal in most jurisdictions.

## Why I built this

Built while preparing for the CPTS certification, to go beyond basic
tutorial-level port scanners and demonstrate a working understanding of
TCP/IP internals, raw packet crafting, and multi-threaded network
programming in Python.

## Roadmap / Ideas for future versions

- [ ] UDP scanning support
- [ ] More advanced OS fingerprinting (TCP window size, options ordering, ISN analysis)
- [ ] HTML report generation
- [ ] Rate limiting / scan throttling for stealthier operation
