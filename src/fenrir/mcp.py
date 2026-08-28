"""HexStrike tool belt over MCP.

The HexStrike server (Flask, :8888) runs separately. We spawn hexstrike_mcp.py as
a stdio bridge and pull its ~150 tools. If the bridge can't produce a tool list,
return [] so the agents degrade to guidance-only instead of crashing.
"""

import logging
import sys

from langchain_mcp_adapters.client import MultiServerMCPClient

from fenrir.settings import settings

log = logging.getLogger(__name__)


async def hexstrike_tools() -> list:
    client = MultiServerMCPClient(
        {
            "hexstrike": {
                "command": sys.executable,
                "args": [str(settings.hexstrike_mcp_path), "--server", settings.hexstrike_server],
                "transport": "stdio",
            }
        }
    )
    try:
        tools = await client.get_tools()
    except Exception as e:  
        log.warning("HexStrike bridge unavailable (%s) — running toolless.", e)
        return []
    
    log.info("Loaded %d HexStrike tools.", len(tools))
    return tools
