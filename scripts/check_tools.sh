#!/bin/bash
# Verifies every CLI tool the fenrir recon/web belt expects is on PATH inside
# the WSL Kali environment. Run: wsl -d kali-linux -u root -- bash /mnt/c/.../fenrir/scripts/check_tools.sh
export PATH="$PATH:/root/.local/bin"
for t in nmap sqlmap gobuster ffuf nikto dnsenum masscan whatweb wafw00f amass subfinder nuclei httpx katana dalfox naabu gau waybackurls arjun paramspider feroxbuster dirsearch; do
  command -v "$t" >/dev/null 2>&1 && echo "$t OK" || echo "$t MISSING"
done
