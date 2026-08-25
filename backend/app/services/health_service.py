"""Readiness / degraded ヘルスチェック。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import AppConfig, get_settings
from app.rag.faiss_store import FaissStore
from app.repository.tsurugi_conn import TsurugiConnection


@dataclass
class HealthCheck:
    name: str
    ok: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "ok": self.ok, "detail": self.detail}


@dataclass
class HealthResult:
    status: str
    checks: list[HealthCheck] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return all(c.ok for c in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "checks": [c.to_dict() for c in self.checks]}


class HealthService:
    def __init__(
        self,
        settings: AppConfig | None = None,
        db: TsurugiConnection | None = None,
        faiss: FaissStore | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._db = db or TsurugiConnection(self._settings)
        self._faiss = faiss or FaissStore(self._settings)

    def check_readiness(self) -> HealthResult:
        checks = [
            self._check_tsurugi(),
            self._check_faiss(),
            self._check_disk(),
        ]
        status = "ready" if all(c.ok for c in checks) else "not_ready"
        return HealthResult(status=status, checks=checks)

    def check_degraded(self) -> HealthResult:
        checks = [self._check_llm()]
        status = "degraded" if any(not c.ok for c in checks) else "ok"
        return HealthResult(status=status, checks=checks)

    def _check_tsurugi(self) -> HealthCheck:
        try:
            self._db.fetchone("SELECT 1")
            return HealthCheck(name="tsurugi", ok=True, detail="connected")
        except Exception as exc:
            return HealthCheck(name="tsurugi", ok=False, detail=str(exc))

    def _check_faiss(self) -> HealthCheck:
        try:
            if not self._faiss.exists():
                return HealthCheck(
                    name="faiss",
                    ok=False,
                    detail="index files not found",
                )
            if not self._faiss.is_loaded():
                self._faiss.load()
            return HealthCheck(name="faiss", ok=True, detail="index loaded")
        except Exception as exc:
            return HealthCheck(name="faiss", ok=False, detail=str(exc))

    def _check_disk(self) -> HealthCheck:
        faiss_dir = self._settings.paths.faiss_dir
        try:
            faiss_dir.mkdir(parents=True, exist_ok=True)
            probe = faiss_dir / ".write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return HealthCheck(name="disk", ok=True, detail="writable")
        except Exception as exc:
            return HealthCheck(name="disk", ok=False, detail=str(exc))

    def _check_llm(self) -> HealthCheck:
        ai = self._settings.ai
        provider = ai.llm_provider
        try:
            if provider == "ollama":
                url = f"{ai.ollama_base_url.rstrip('/')}/api/tags"
                with httpx.Client(timeout=3.0) as client:
                    resp = client.get(url)
                    resp.raise_for_status()
                return HealthCheck(
                    name="llm", ok=True, detail=f"ollama reachable ({ai.ollama_llm_model})"
                )
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                return HealthCheck(name="llm", ok=False, detail="OPENAI_API_KEY not set")
            return HealthCheck(name="llm", ok=True, detail=f"openai configured ({ai.llm_model})")
        except Exception as exc:
            return HealthCheck(name="llm", ok=False, detail=str(exc))
