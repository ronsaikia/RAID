# RAID — Rapid Asset & Infrastructure Discovery

A multi-threaded network reconnaissance tool built in Python. RAID performs
TCP connect scans or SYN "stealth" scans, identifies running services via
banner grabbing and port mapping, and exports results to JSON for use in
reporting pipelines.

## Contents

- [Features](#features)
- [Installation](#installation)
- [How it works — with examples](#how-it-works--with-examples)
- [Usage](#usage)
- [Running it as a global `raid` command](#running-it-as-a-global-raid-command)
- [Arguments](#arguments)
- [Troubleshooting](#troubleshooting)
- [Legal / Ethical Use](#legal--ethical-use)
- [Why I built this](#why-i-built-this)
- [Roadmap](#roadmap--ideas-for-future-versions)

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
sudo cp raid.py /usr/bin/raid
```
If you do this, also install scapy outside the venv so `sudo raid` can find
it: `pip install scapy --break-system-packages`.

> **Why `/usr/bin` and not `/usr/local/bin`?** On many Kali/Debian
> systems, `sudo`'s PATH (`secure_path`) excludes `/usr/local/bin`, which
> makes `sudo raid` fail with `command not found` even though `raid`
> (without sudo) works fine. Since `--stealth` and `--os` both need root,
> installing to `/usr/bin` from the start avoids this entirely. See
> **Troubleshooting** below if you hit this or a similar issue.

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
$ sudo raid -p 20-25 scanme.nmap.org --os

[*] OS Guess : Linux/Unix/macOS (TTL=42, ~22 hop(s) from nearest default 64)
```
(Verified against `scanme.nmap.org`, Nmap's official public test host, which
runs Ubuntu Linux — the guess above is correct. `--os` requires `sudo`
since raw ICMP sockets need root privileges.)

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

## Troubleshooting

Common issues and their fixes, based on real problems hit while building
and testing this tool.

### `sudo raid` says "command not found" but `raid` works fine without sudo
This happens when RAID is installed to `/usr/local/bin`, which many
Kali/Debian systems exclude from `sudo`'s PATH (`secure_path`) for
security reasons. Since `--stealth` and `--os` both require root, this
matters in practice.

**Fix:** install to `/usr/bin` instead, which is always in `sudo`'s PATH:
```bash
sudo cp raid.py /usr/bin/raid
```
Check where `sudo` is actually looking, if you want to confirm:
```bash
sudo env | grep ^PATH
```

### After updating `raid.py`, the old banner / old behavior still shows up
This means the global `raid` command isn't reading your updated file.
Two common causes:

1. **You forgot to re-copy the file.** The global install is a separate
   copy on disk, not a live link to your project folder — editing
   `raid.py` locally does nothing to `/usr/bin/raid` until you re-run:
   ```bash
   sudo cp raid.py /usr/bin/raid
   ```

2. **You have two conflicting installs.** If you installed to
   `/usr/local/bin/raid` at some point and later switched to
   `/usr/bin/raid`, your shell may still be resolving `raid` to the old
   one (since `/usr/local/bin` is usually earlier in a normal user's
   PATH). Check which one is actually running:
   ```bash
   which raid
   ```
   If it points to `/usr/local/bin/raid`, remove the stale copy so
   there's only one source of truth:
   ```bash
   sudo rm /usr/local/bin/raid
   hash -r          # clear bash's cached command location
   which raid        # should now show /usr/bin/raid
   ```

**Going forward:** every time you edit `raid.py`, re-run
`sudo cp raid.py /usr/bin/raid` before testing the global `raid` command,
or you'll be testing stale code.

### `--os` fails with "OS detection failed"
RAID already prints likely reasons when this happens, but in short:
- You didn't run it with `sudo` — raw ICMP sockets require root.
- The target doesn't respond to ICMP (common behind firewalls).
- `scapy` isn't installed in the environment you're actually running from
  (remember: a global `sudo raid` install may not see packages installed
  inside a venv — see the scapy note in Installation above).

### Scan results are inconsistent between runs against the same real host (e.g. `scanme.nmap.org`)
This is expected, not a bug. Scanning a real host over the public internet
introduces network latency, thread contention, and occasional rate-limiting
that a local lab VM won't have — a port that's genuinely open can still be
missed if its response doesn't arrive within the timeout window, especially
under high thread counts. To get steadier results:
```bash
raid scanme.nmap.org --timeout 2.0 -t 30
```
Lower thread count and a longer timeout trade speed for reliability. This
same inherent variability is why real scanners like Nmap support retry
logic (`--max-retries`) — a good idea documented in the Roadmap below.

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
