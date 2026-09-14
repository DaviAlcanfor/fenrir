# HexStrike AI server, containerized so it doesn't need WSL on Windows.
# Build context is the sibling ../hexstrike-ai checkout (see docker-compose.yml).
#
# Installs the same tool subset scripts/check_tools.sh verifies for the WSL
# setup — not all 150+ tools HexStrike supports, just what fenrir's
# recon/web agents actually call.
FROM kalilinux/kali-rolling

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-venv python3-pip golang-go pipx \
    nmap sqlmap gobuster ffuf nikto dnsenum masscan whatweb wafw00f amass \
    feroxbuster dirsearch \
    && rm -rf /var/lib/apt/lists/*

ENV GOBIN=/usr/local/bin
ENV PATH="/root/.local/bin:${PATH}"

# ponytail: mirrors scripts/install_go_tools.sh by hand (build context here is
# ../hexstrike-ai, can't COPY a file from the fenrir repo) — keep the two in sync.
RUN go install github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest && \
    go install github.com/projectdiscovery/httpx/cmd/httpx@latest && \
    go install github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest && \
    go install github.com/projectdiscovery/katana/cmd/katana@latest && \
    go install github.com/projectdiscovery/naabu/v2/cmd/naabu@latest && \
    go install github.com/hahwul/dalfox/v2@latest && \
    go install github.com/lc/gau/v2/cmd/gau@latest && \
    go install github.com/tomnomnom/waybackurls@latest

RUN pipx install arjun && pipx install paramspider

# Trimmed requirements: skips hexstrike-ai's pwntools/angr (binary-analysis
# extras, unused by fenrir's WSTG-focused agents — see AGENTS.md skill list).
RUN python3 -m venv /opt/hexstrike-env && \
    /opt/hexstrike-env/bin/pip install --no-cache-dir \
    flask requests psutil aiohttp beautifulsoup4 selenium webdriver-manager

WORKDIR /app
COPY . /app

EXPOSE 8888
CMD ["/opt/hexstrike-env/bin/python", "/app/hexstrike_server.py"]
