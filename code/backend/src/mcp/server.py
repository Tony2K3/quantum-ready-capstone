"""Decision Cortex — MCP connector server.

    python server.py

starts the server over stdio, installing requirements.txt first if any
dependency is missing. The code lives in the connectors/ package;
see README.md for setup, tools and live-data configuration.
"""

import importlib
import logging
import subprocess
import sys
from pathlib import Path

REQUIREMENTS = Path(__file__).resolve().parents[2] / "mcp" / "requirements.txt"


def ensure_dependencies():
    """pip install requirements.txt if mcp (pre-2.0) or httpx can't be imported."""
    try:
        import httpx  # noqa: F401
        from mcp.server.fastmcp import FastMCP  # noqa: F401  (gone in mcp 2.x)
    except ImportError as exc:
        print(f"Missing dependency ({exc}); installing {REQUIREMENTS.name}...", file=sys.stderr)
        # stdout is the MCP stdio channel, so pip's output must go to stderr
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS)],
            stdout=sys.stderr,
        )
        importlib.invalidate_caches()  # so this process sees the newly installed packages


if __name__ == "__main__":
    ensure_dependencies()

    from connectors.tools import mcp

    logging.basicConfig(level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)  # one log line per request is too noisy
    mcp.run()
