#!/usr/bin/env python3
"""Mermaid ソースを PNG にレンダリングする（mermaid-cli / npx）。"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def render_mermaid(
    source: str,
    output: Path,
    *,
    background: str = "transparent",
) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    npx = shutil.which("npx")
    if npx is None:
        raise RuntimeError("npx が見つかりません。Node.js をインストールしてください。")

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".mmd",
        encoding="utf-8",
        delete=False,
    ) as tmp:
        tmp.write(source)
        tmp_path = Path(tmp.name)

    try:
        cmd = [
            npx,
            "--yes",
            "@mermaid-js/mermaid-cli",
            "-i",
            str(tmp_path),
            "-o",
            str(output),
            "-b",
            background,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise RuntimeError(
                f"mermaid-cli 失敗 (exit {result.returncode}):\n{result.stderr or result.stdout}"
            )
    finally:
        tmp_path.unlink(missing_ok=True)

    if not output.is_file():
        raise RuntimeError(f"PNG が生成されませんでした: {output}")
    return output


def render_mermaid_file(input_path: Path, output: Path, *, background: str = "transparent") -> Path:
    return render_mermaid(input_path.read_text(encoding="utf-8"), output, background=background)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mermaid を PNG に変換")
    parser.add_argument("input", type=Path, help="入力 .mmd またはテキスト")
    parser.add_argument("output", type=Path, help="出力 PNG")
    parser.add_argument("-b", "--background", default="transparent")
    args = parser.parse_args(argv)

    if not args.input.is_file():
        print(f"入力が見つかりません: {args.input}", file=sys.stderr)
        return 1

    try:
        render_mermaid_file(args.input, args.output, background=args.background)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"生成: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
