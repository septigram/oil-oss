"""アプリケーション設定の読込。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class OperatorConfig:
    employee_id: str
    display_name: str


@dataclass
class AuthConfig:
    enabled: bool
    session_ttl_hours: int
    cookie_name: str
    secure_cookie: bool


def default_auth_config() -> AuthConfig:
    return AuthConfig(
        enabled=False,
        session_ttl_hours=8,
        cookie_name="oil_session",
        secure_cookie=False,
    )


@dataclass
class ReferenceDateConfig:
    mode: str
    fixed_date: str


@dataclass
class TsurugiConfig:
    endpoint: str
    user: str
    password: str


@dataclass
class PathsConfig:
    corpus_jsonl: Path
    rag_summary_dir: Path
    faiss_dir: Path
    chat_prompt_templates: Path


@dataclass
class RagConfig:
    top_k: int


@dataclass
class AiConfig:
    provider: str
    llm_provider: str
    llm_model: str
    embedding_model: str
    ollama_base_url: str
    ollama_llm_model: str
    ollama_embedding_model: str


@dataclass
class SlackConfig:
    bot_token: str | None
    app_token: str | None


@dataclass
class AppConfig:
    timezone: str
    context_path: str
    base_url: str
    operator: OperatorConfig
    auth: AuthConfig
    reference_date: ReferenceDateConfig
    tsurugi: TsurugiConfig
    paths: PathsConfig
    rag: RagConfig
    ai: AiConfig
    slack: SlackConfig
    project_root: Path


def _normalize_context_path(value: str) -> str:
    path = value.strip()
    if not path.startswith("/"):
        path = f"/{path}"
    return path.rstrip("/") or "/"


def _resolve_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


@lru_cache
def get_settings() -> AppConfig:
    load_dotenv(PROJECT_ROOT / ".env")
    config_path = PROJECT_ROOT / "config" / "config.yaml"
    if not config_path.exists():
        config_path = PROJECT_ROOT / "config" / "config.yaml.example"
    with config_path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    paths = raw["paths"]
    app_raw = raw["app"]
    auth_raw = raw.get("auth", {})
    context_path = _normalize_context_path(app_raw.get("context_path", "/oil"))
    base_url = str(app_raw.get("base_url", f"http://localhost:8000{context_path}")).rstrip("/")
    return AppConfig(
        timezone=app_raw["timezone"],
        context_path=context_path,
        base_url=base_url,
        operator=OperatorConfig(**app_raw["operator"]),
        auth=AuthConfig(
            enabled=bool(auth_raw.get("enabled", False)),
            session_ttl_hours=int(auth_raw.get("session_ttl_hours", 8)),
            cookie_name=str(auth_raw.get("cookie_name", "oil_session")),
            secure_cookie=bool(auth_raw.get("secure_cookie", False)),
        ),
        reference_date=ReferenceDateConfig(**raw["reference_date"]),
        tsurugi=TsurugiConfig(
            endpoint=os.getenv("OIL_TSURUGI_ENDPOINT", raw["tsurugi"]["endpoint"]),
            user=os.getenv("OIL_TSURUGI_USER", raw["tsurugi"]["user"]),
            password=os.getenv("OIL_TSURUGI_PASSWORD", raw["tsurugi"]["password"]),
        ),
        paths=PathsConfig(
            corpus_jsonl=_resolve_path(paths["corpus_jsonl"]),
            rag_summary_dir=_resolve_path(paths["rag_summary_dir"]),
            faiss_dir=_resolve_path(paths["faiss_dir"]),
            chat_prompt_templates=_resolve_path(
                paths.get("chat_prompt_templates", "data/chat-prompt-templates.yaml")
            ),
        ),
        rag=RagConfig(**raw["rag"]),
        ai=AiConfig(
            **{
                **raw["ai"],
                "llm_provider": raw["ai"].get("llm_provider", raw["ai"]["provider"]),
            }
        ),
        project_root=PROJECT_ROOT,
        slack=SlackConfig(
            bot_token=os.getenv("SLACK_BOT_TOKEN"),
            app_token=os.getenv("SLACK_APP_TOKEN"),
        ),
    )


def get_openai_api_key() -> str | None:
    load_dotenv(PROJECT_ROOT / ".env")
    return os.getenv("OPENAI_API_KEY")


def get_observability_env() -> str:
    load_dotenv(PROJECT_ROOT / ".env")
    return os.getenv("OIL_ENV", "development")


def get_observability_version(*, default: str = "0.1.0") -> str:
    load_dotenv(PROJECT_ROOT / ".env")
    return os.getenv("OIL_VERSION", default)
