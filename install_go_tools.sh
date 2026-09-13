#!/bin/bash
# ProjectDiscovery + misc Go-based recon/web tools for the HexStrike belt.
# Run inside WSL (kali-linux): wsl -d kali-linux -u root -- bash /mnt/c/.../fenrir/install_go_tools.sh
set -e
export PATH=$PATH:/usr/lib/go-1.26/bin
export GOBIN=/usr/local/bin

go install github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest
echo "subfinder done"
go install github.com/projectdiscovery/httpx/cmd/httpx@latest
echo "httpx done"
go install github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest
echo "nuclei done"
go install github.com/projectdiscovery/katana/cmd/katana@latest
echo "katana done"
go install github.com/projectdiscovery/naabu/v2/cmd/naabu@latest
echo "naabu done"
go install github.com/hahwul/dalfox/v2@latest
echo "dalfox done"
go install github.com/lc/gau/v2/cmd/gau@latest
echo "gau done"
go install github.com/tomnomnom/waybackurls@latest
echo "waybackurls done"
echo "ALL GO TOOLS DONE"
