#!/usr/bin/env python3
"""FAISS インデックス初回生成ツール。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.logging_config import setup_logging
from app.rag.index_service import RagIndexService

setup_logging()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build FAISS index from corpus and summaries")
    parser.add_argument(
        "--rebuild-summaries-only",
        action="store_true",
        help="Rebuild only summary documents",
    )
    parser.add_argument(
        "--allow-db-fallback",
        action="store_true",
        help="Use count=0 for summaries when Tsurugi is unavailable",
    )
    args = parser.parse_args()
    service = RagIndexService()
    if args.rebuild_summaries_only:
        count = service.rebuild_summaries_only()
        print(f"Summaries rebuilt: {count}")
    else:
        count = service.build_full_index(allow_db_fallback=args.allow_db_fallback)
        print(f"Full index built: {count} documents")


if __name__ == "__main__":
    main()
