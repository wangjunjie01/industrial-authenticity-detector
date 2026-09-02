from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .analyzer import analyze_text
from .server import serve


def main() -> None:
    parser = argparse.ArgumentParser(description="Industrial writing-pattern quality analyzer")
    sub = parser.add_subparsers(dest="command", required=True)
    analyze = sub.add_parser("analyze", help="Analyze a UTF-8 text file, or stdin with -")
    analyze.add_argument("path")
    analyze.add_argument("--platform", default="general", choices=["general", "linkedin", "facebook", "blog", "b2b"])
    web = sub.add_parser("serve", help="Start the local Web UI")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    if args.command == "serve":
        serve(args.host, args.port)
        return
    text = sys.stdin.read() if args.path == "-" else Path(args.path).read_text(encoding="utf-8")
    print(json.dumps(analyze_text(text, args.platform), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

