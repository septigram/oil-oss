# リリースノート

版番号: 2.0

本書はバージョンごとの変更点を記録する。

## 2026-07-03 — 外部 Webhook・Slack 連携（RFC008）


| 領域        | 内容                                                                                                                                                                                             |
| --------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| DB        | `oil_webhook_api_keys`、`oil_notification_channels`、`oil_notification_channel_types`。`tools/apply_rfc008_migration.py`                                                                          |
| バックエンド    | `POST /oil/api/webhooks/incidents`（`X-API-Key` 認証）、`IncidentCreateService` 共通化、受信時 `auto_triage` による重要度自動昇格、`NotificationService`、通知チャネル CRUD、AI ツール `send_incident_notification`（OPERATOR 以上） |
| Slack Bot | `slack-bolt` + Socket Mode 常駐（`lifespan`）。メンションに VIEWER 相当の単発 AI 応答。`deploy/slack/manifest.yaml`                                                                                               |
| Slack 表示  | GFM 表を `blocks: markdown` で送信。失敗時は mrkdwn フォールバック（`slack/markdown.py`）                                                                                                                         |
| フロント      | **Webhook API キー**（ADMIN）、**通知チャネル**（OPERATOR 以上）管理画面                                                                                                                                          |
| 設定        | `config.yaml` の `app.base_url`、`.env` の `SLACK_BOT_TOKEN` / `SLACK_APP_TOKEN`                                                                                                                  |
| 文書        | schema / api-design / system-design / operator-runbook §15                                                                                                                                     |


REST API エンドポイント数: **67**（`/oil/api/`*）。`/health` 系・`/metrics` を含めると **72**。

## 2026-07-02 — 一覧検索の是正と RAG 検索（RFC007）


| 領域     | 内容                                                                                                              |
| ------ | --------------------------------------------------------------------------------------------------------------- |
| バックエンド | インシデント・手順書一覧の SQL `LIMIT`/`OFFSET` 化。`GET` に `rag` クエリ追加（`true` 時 FAISS 意味検索、`score` 付与）。`ListRagSearchService` |
| フロント   | 明示検索時の `initial` 解除・ページ 1 リセット、Pinia store と検索フォーム同期、**意味検索（RAG）** チェックボックス（インシデント・手順書一覧）                       |
| 文書     | api-design / system-requirements / user-manual                                                                  |




## 2026-06-30 — 動作確認に基づく機能改善（RFC006）


| 領域     | 内容                                                                                                                        |
| ------ | ------------------------------------------------------------------------------------------------------------------------- |
| バックエンド | 紐づけ手順書解除（`DELETE .../procedures/{link_id}`）、AI 手順書下書き（`from-incident` + LLM）、トリアージの説明文から `occurred_at` / `detected_at` 提案 |
| フロント   | 手順書編集 Markdown プレビュー改善、左ペインから一覧導線、下書き生成ローディング UI                                                                          |
| 文書     | rfc006 / user-manual                                                                                                      |




## 2026-06-29 — 製品名・識別子の統一


| 領域           | 旧                                | 新                                                   |
| ------------ | -------------------------------- | --------------------------------------------------- |
| 製品名          | Tsurugi IRDB / IRDB              | **Ops Incident Ledger**（サブタイトル: powered by Tsurugi） |
| コンテキストパス     | `/irdb2/`                        | `/oil/`                                             |
| セッション Cookie | `irdb2_session`                  | `oil_session`                                       |
| 環境変数         | `IRDB_*`                         | `OIL_*`                                             |
| RDB テーブル     | `irdb_*`                         | `oil_*`                                             |
| パッケージ        | `irdb-backend` / `irdb-frontend` | `oil-backend` / `oil-frontend`                      |


デプロイ・監視サンプル（`deploy/nginx/oil.conf`、`oil.service`、Grafana ダッシュボード）および関連文書を同期。既存 FAISS インデックスは `doc_id` / `INC-*` ベースのため再ビルド不要。

## 2026-06-28 — 認証・RBAC・マスタ管理・楽観ロック（RFC005）


| 領域     | 内容                                                                                                                                     |
| ------ | -------------------------------------------------------------------------------------------------------------------------------------- |
| DB     | `oil_users` / `oil_sessions` / `oil_user_roles`、主要テーブルに `row_version`。`tools/apply_rfc005_migration.py`                                |
| バックエンド | セッション認証（`auth.enabled`）、RBAC（ADMIN / OPERATOR / VIEWER）、マスタ CRUD 23 エンドポイント、ユーザ管理 4 エンドポイント、409 楽観ロック、監査ログ（`auth_*` / `master_change`） |
| フロント   | `LoginPage.vue`、`authStore`、ルートガード、`MastersPage.vue`、`AdminUsersPage.vue`、競合 Dialog                                                    |
| データ    | `setup.sql` 手順書 51 件、Tsurugi 非対応 DEFAULT 削除                                                                                            |
| 文書     | schema / api-design / user-manual / operator-runbook                                                                                   |


REST API エンドポイント数: **56**（`/oil/api/`*）。

## 2026-06-28 — 本番運用監視（RFC004）


| 領域     | 内容                                                                                                                            |
| ------ | ----------------------------------------------------------------------------------------------------------------------------- |
| バックエンド | `X-Request-Id`、`GET /oil/metrics`（Prometheus）、`/health/live`・`/health/ready`・`/health/degraded`、OpenTelemetry（OTLP 未設定時 NoOp） |
| 運用     | `deploy/` サンプル、[operator-runbook.md](operator-runbook.md) 初版                                                                  |
| CI     | ruff / mypy 設定                                                                                                                |




## 2026-06-28 — 対応手順書（KEDB / RFC003）


| 領域     | 内容                                                                                                                                                 |
| ------ | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| DB     | `oil_procedures` / `oil_incident_procedures`、シード 8 件 + 適用履歴 12 件（`setup.sql` に同梱）。`is_active` / `was_successful` は Tsurugi 制約により **INTEGER (0/1)** |
| バックエンド | 手順書 REST API 10 エンドポイント、RAG `DOC-PRC-*`、`python -m app --verbose` で HTTP アクセスログと `api_timing` を stderr 出力（通常起動時は抑制）                                |
| バッチ    | `tools/generate_procedures_batch.py`（`is_active=0` で保存、`--dry-run` 可）                                                                              |
| フロント   | 手順書 CRUD、インシデント詳細統合、左ペイン（クイックフィルタ + 使用回数 Top5 常時表示）、PRC リンク                                                                                        |
| エージェント | 手順書 RAG 検索                                                                                                                                         |


REST API エンドポイント数: **31**（`/oil/api/`*）。

## 2026-06-26 — AI トリアージ（RFC002）Mark


| 領域     | 内容                                                                         |
| ------ | -------------------------------------------------------------------------- |
| バックエンド | `TriageService`、トリアージ MCP ツール、SSE `widget` / `proposal` / `triage_started` |
| フロント   | 提案カード、新規保存後の自動トリアージ起動                                                      |




## 2026-06-25 — コンテキストパス `/oil`

SPA・REST API・health を `/oil/` 配下に統一（のち製品リネームで `/irdb2/` から `/oil/` へ再統一）。

## 2026-06-25 — GAP001 設計・実装ギャップ是正


| 領域     | 内容                                                                          |
| ------ | --------------------------------------------------------------------------- |
| バックエンド | 新規作成時の調査 INSERT 削除、対応保存時 RAG upsert、`search_incidents` に severity、静的 SPA 配信 |
| フロント   | 一覧の発生日時ソート切替、重要度フィルタ、モバイルログパネル切替                                            |
| 文書     | 要件・設計・RAG 仕様の同期                                                             |




## 2026-06-25 — ログパネル・レイアウト（RFC001）


| 領域     | 内容                               |
| ------ | -------------------------------- |
| バックエンド | `GET /oil/api/logs/recent`、構造化ログ |
| フロント   | 3 ペイン + 下部ログパネル、INC-ID リンク       |




## 2026-06-24 — 初版

インシデント管理、RAG、AI チャット、FAISS インデックス、Quasar SPA。REST API **20** エンドポイント。

## 変更履歴


| 版   | 日付         | 変更内容                                    |
| --- | ---------- | --------------------------------------- |
| 1.0 | 2026-06-28 | 初版（RFC003 まで）                           |
| 2.0 | 2026-07-03 | RFC004〜008、製品リネーム、GAP001 を追記。版構成を時系列で整理 |


