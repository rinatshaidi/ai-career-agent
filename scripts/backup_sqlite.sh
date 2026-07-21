#!/usr/bin/env bash
set -euo pipefail

database_path="/opt/jobmonitor/data/jobmonitor.db"
backup_dir="/root/jobmonitor-backups/daily"
backup_path="${backup_dir}/jobmonitor-$(date -u +%Y%m%d).db"
temporary_path="${backup_path}.tmp"

install -d -m 700 "${backup_dir}"
rm -f "${temporary_path}"

python3 - "${database_path}" "${temporary_path}" <<'PY'
import sqlite3
import sys

source_path, target_path = sys.argv[1:]
with sqlite3.connect(f"file:{source_path}?mode=ro", uri=True) as source:
    with sqlite3.connect(target_path) as target:
        source.backup(target)
        result = target.execute("PRAGMA quick_check").fetchone()[0]
        if result != "ok":
            raise RuntimeError(f"backup quick_check failed: {result}")
PY

chmod 600 "${temporary_path}"
mv -f "${temporary_path}" "${backup_path}"
find "${backup_dir}" -maxdepth 1 -type f -name 'jobmonitor-*.db' -mtime +6 -delete

printf 'JobMonitor backup created: %s (%s bytes)\n' \
  "${backup_path}" "$(stat -c '%s' "${backup_path}")"
