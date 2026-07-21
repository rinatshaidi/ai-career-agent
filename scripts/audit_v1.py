from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path


def grouped(connection: sqlite3.Connection, query: str) -> dict[str, int]:
    return {str(row[0]): int(row[1]) for row in connection.execute(query).fetchall()}


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: audit_v1.py DATABASE_PATH", file=sys.stderr)
        return 2
    database_path = Path(sys.argv[1])
    connection = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
    try:
        connection.row_factory = sqlite3.Row
        quick_check = connection.execute("PRAGMA quick_check").fetchone()[0]
        required_tables = {
            "opportunities",
            "opportunity_sources",
            "ai_analyses",
            "telegram_notifications",
            "source_states",
            "system_runs",
            "profile_search_tracks",
        }
        actual_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        duplicate_source_ids = connection.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT source, external_id
                FROM opportunity_sources
                GROUP BY source, external_id
                HAVING COUNT(*) > 1
            )
            """
        ).fetchone()[0]
        duplicate_canonical_urls = connection.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT canonical_url
                FROM opportunities
                WHERE canonical_url IS NOT NULL AND canonical_url <> ''
                GROUP BY canonical_url
                HAVING COUNT(*) > 1
            )
            """
        ).fetchone()[0]
        source_states = [
            {
                "source": row["source"],
                "last_status": row["last_status"],
                "last_success_at": row["last_success_at"],
                "last_received": row["last_received"],
                "last_saved": row["last_saved"],
                "last_duplicates": row["last_duplicates"],
            }
            for row in connection.execute(
                """
                SELECT source, last_status, last_success_at, last_received,
                       last_saved, last_duplicates
                FROM source_states
                ORDER BY source
                """
            ).fetchall()
        ]
        latest_runs = [
            {
                "id": row["id"],
                "status": row["status"],
                "started_at": row["started_at"],
                "finished_at": row["finished_at"],
            }
            for row in connection.execute(
                """
                SELECT id, status, started_at, finished_at
                FROM system_runs
                ORDER BY id DESC
                LIMIT 5
                """
            ).fetchall()
        ]
        analysis_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(ai_analyses)")
        }
        if {"input_tokens", "output_tokens", "total_tokens"}.issubset(analysis_columns):
            usage_row = connection.execute(
                """
                SELECT COUNT(*) AS analyses,
                       COALESCE(SUM(input_tokens), 0) AS input_tokens,
                       COALESCE(SUM(output_tokens), 0) AS output_tokens,
                       COALESCE(SUM(total_tokens), 0) AS total_tokens
                FROM ai_analyses
                """
            ).fetchone()
            ai_usage: dict[str, int | str] = dict(usage_row)
        else:
            ai_usage = {"status": "token tracking not deployed"}
        report = {
            "database_quick_check": quick_check,
            "missing_tables": sorted(required_tables - actual_tables),
            "opportunity_statuses": grouped(
                connection,
                "SELECT status, COUNT(*) FROM opportunities GROUP BY status ORDER BY status",
            ),
            "recommendations": grouped(
                connection,
                """
                SELECT COALESCE(recommendation, 'legacy'), COUNT(*)
                FROM ai_analyses
                GROUP BY COALESCE(recommendation, 'legacy')
                ORDER BY COALESCE(recommendation, 'legacy')
                """,
            ),
            "ai_usage": ai_usage,
            "notification_statuses": grouped(
                connection,
                """
                SELECT status, COUNT(*)
                FROM telegram_notifications
                GROUP BY status
                ORDER BY status
                """,
            ),
            "duplicate_source_ids": int(duplicate_source_ids),
            "duplicate_canonical_urls": int(duplicate_canonical_urls),
            "source_states": source_states,
            "latest_system_runs": latest_runs,
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
