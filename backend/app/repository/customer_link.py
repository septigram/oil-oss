"""影響顧客紐づけリポジトリ。"""

from __future__ import annotations

from app.repository.tsurugi_conn import TsurugiConnection


class CustomerLinkRepository:
    def __init__(self, db: TsurugiConnection | None = None) -> None:
        self._db = db or TsurugiConnection()

    def replace(self, incident_id: str, customer_ids: list[str]) -> None:
        self._db.execute(
            "DELETE FROM oil_incident_customers WHERE incident_id = ?",
            (incident_id,),
        )
        for customer_id in customer_ids:
            self._db.execute(
                "INSERT INTO oil_incident_customers (incident_id, customer_id) VALUES (?, ?)",
                (incident_id, customer_id),
            )
