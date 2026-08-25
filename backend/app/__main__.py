"""Uvicorn 起動ラッパー（--verbose 対応）。"""

from __future__ import annotations

import argparse
import os

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Ops Incident Ledger API server")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="ログポーリング API 以外の HTTP アクセスログと api_timing を出力。ポーリング分も含める",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    os.environ["OIL_VERBOSE"] = "1" if args.verbose else "0"

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        access_log=True,
    )


if __name__ == "__main__":
    main()
