from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from healthcheck import heartbeat_is_fresh
from storage import OpportunityRepository


class HealthcheckTests(unittest.TestCase):
    test_data_root = Path(__file__).resolve().parents[1] / "data"

    def setUp(self) -> None:
        self.test_data_root.mkdir(exist_ok=True)
        self.database_path = self.test_data_root / f"test-{uuid4().hex}.db"
        self.repository = OpportunityRepository(self.database_path)
        self.repository.initialize()

    def tearDown(self) -> None:
        for suffix in ("", "-shm", "-wal"):
            path = Path(f"{self.database_path}{suffix}")
            if path.exists():
                path.unlink()

    def test_missing_heartbeat_is_unhealthy(self) -> None:
        self.assertFalse(
            heartbeat_is_fresh(
                self.repository,
                "worker",
                maximum_age_seconds=60,
            )
        )

    def test_recent_heartbeat_is_healthy_and_old_one_is_not(self) -> None:
        before = datetime.now(timezone.utc)
        self.repository.set_service_heartbeat("worker")
        heartbeat = self.repository.get_service_heartbeat("worker")

        self.assertIsNotNone(heartbeat)
        self.assertTrue(
            heartbeat_is_fresh(
                self.repository,
                "worker",
                maximum_age_seconds=60,
                now=before + timedelta(seconds=30),
            )
        )
        self.assertFalse(
            heartbeat_is_fresh(
                self.repository,
                "worker",
                maximum_age_seconds=60,
                now=before + timedelta(seconds=90),
            )
        )

    def test_rejects_unsafe_service_name(self) -> None:
        with self.assertRaisesRegex(ValueError, "Service name"):
            self.repository.set_service_heartbeat("worker'; delete")


if __name__ == "__main__":
    unittest.main()
