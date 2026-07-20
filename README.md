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
- **Banner grabbing** — captures service banners on open ports
- **JSON export** — structured output for use in reports or other tooling
- **Colorized CLI output** for readability during live scans

## Requirements

```bash
pip install scapy --break-system-packages   # only needed for --stealth mode
```

No external dependencies are needed for standard TCP connect scans — only
the Python standard library.

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
```

## Installing as a global command

To call it as `raid` from anywhere, instead of `python3 raid.py`:

```bash
chmod +x raid.py
sudo cp raid.py /usr/local/bin/raid
```

Then simply:
```bash
raid -p23 127.0.0.1
raid -p 22,80,443 127.0.0.1
sudo raid -p 1-1024 127.0.0.1 --stealth
```

Note: if using `--stealth` after a global install, make sure `scapy` is
installed outside your venv too (`pip install scapy --break-system-packages`),
since `sudo raid` runs outside any activated virtual environment.

## Arguments

| Flag | Description | Default |
|---|---|---|
| `target` | Target IP or hostname | required |
| `-p, --ports` | Ports: single (`23`), range (`1-1024`), or list (`22,80,443`) | `1-1024` |
| `-t, --threads` | Number of threads (TCP mode only) | `100` |
| `--timeout` | Socket timeout in seconds | `1.0` |
| `--stealth` | Use SYN scan instead of TCP connect | off |
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
- [ ] OS fingerprinting via TTL/window size analysis
- [ ] HTML report generation
- [ ] Rate limiting / scan throttling for stealthier operation
