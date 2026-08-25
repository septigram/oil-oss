# Ops Incident Ledger (oil)

Ops Incident Ledger — 運用インシデント管理のための Web ツール（Tsurugi 搭載）。

FastAPI + Vue/Quasar + Tsurugi + FAISS + LangGraph。インシデント管理と手順書（KEDB）に、AI 支援の検索・トリアージを組み合わせた構成です。**運用監視の閉域網**を想定し、LLM・埋め込み・RAG 索引は **Ollama オンプレ**が標準です。

[English](README.md)

![スクリーンショット](docs/images/tsurugi-oil.png)

## クイックスタート

ホストに [Ollama](https://ollama.com/) を用意し、Docker でサンプルデータセットを試す:

```bash
ollama pull qwen3.6:27b
ollama pull nomic-embed-text
cp .env.example .env
docker compose up --build
```

http://localhost:8000/oil/ を開く（`OPENAI_API_KEY` は不要）。

デフォルトログイン（評価環境）:

| 項目 | 値 |
|------|-----|
| ログイン ID | `admin` |
| パスワード | `.env` の `OIL_BOOTSTRAP_PASSWORD`（未設定時は `admin`） |

## 機能

- 検索・フィルタ・詳細表示を備えたインシデント台帳
- 既知エラー / 手順書（procedure）管理
- RDB 検索とインシデント文書への RAG を組み合わせた AI チャット
- セッション認証とロールベースアクセス（VIEWER / OPERATOR / ADMIN）

## 動作要件

- [Docker](https://docs.docker.com/get-docker/) および Docker Compose v2
- AI（標準）: ホスト上の Ollama（`qwen3.6:27b` クラス + `nomic-embed-text`）。同梱 FAISS 索引はオンプレ埋め込み済み
- AI（任意）: OpenAI API キー（`OPENAI_API_KEY`）— より高速な応答向け
- データベース: [Tsurugi](https://github.com/project-tsurugi/tsurugidb)（`docker compose` に含まれる）

サンプルデータは架空のものです（株式会社ストッククラウド）。詳細は [data/20260624T221136/README.md](data/20260624T221136/README.md) を参照してください。

## ドキュメント

| 文書 | 説明 |
|------|------|
| [docs/user-manual.md](docs/user-manual.md) | 利用者向けガイド（画面操作） |
| [BUILD.md](BUILD.md) | ビルドと設定 |
| [docs/release-notes.md](docs/release-notes.md) | リリース履歴 |

## ライセンス

Apache License 2.0。詳細は [LICENSE](LICENSE) を参照してください。

## セキュリティ

脆弱性の報告は [SECURITY.md](SECURITY.md) を参照してください。

## コントリビューション

本リポジトリは読み取り専用の公開ミラーです。詳細は [CONTRIBUTING.md](CONTRIBUTING.md) を参照してください。
