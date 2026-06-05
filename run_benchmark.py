"""Run Terminus LLM benchmark — sets API key inline to avoid Windows env var propagation issues.

Usage:
    python run_benchmark.py benchmark-single-test.json
    python run_benchmark.py my-config.json --verbose
"""

import os
import sys

# ── Set your API key here ──────────────────────────────────────────────────────
os.environ["NVIDIA_API_KEY"] = "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"

# Any other keys you want to test against:
# os.environ["OPENAI_API_KEY"] = "sk-..."
# os.environ["ANTHROPIC_API_KEY"] = "sk-ant-..."
# ──────────────────────────────────────────────────────────────────────────────

if len(sys.argv) < 2:
    print("Usage: python run_benchmark.py <config.json> [--verbose]")
    sys.exit(1)

config_arg = sys.argv[1]
verbose = "--verbose" in sys.argv

sys.argv = ["terminus", "--benchmark", config_arg] + (["--verbose"] if verbose else [])
from terminus.__main__ import main
main()
