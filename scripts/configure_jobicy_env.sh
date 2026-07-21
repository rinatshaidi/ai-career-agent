#!/usr/bin/env sh
set -eu

env_file="${1:-/opt/jobmonitor/.env}"

if [ ! -f "$env_file" ]; then
  echo "Environment file not found: $env_file" >&2
  exit 1
fi

set_value() {
  key="$1"
  value="$2"
  temporary="${env_file}.tmp.$$"
  awk -v key="$key" -v value="$value" '
    BEGIN { found = 0 }
    index($0, key "=") == 1 {
      print key "=" value
      found = 1
      next
    }
    { print }
    END {
      if (!found) {
        print key "=" value
      }
    }
  ' "$env_file" > "$temporary"
  chmod --reference="$env_file" "$temporary" 2>/dev/null || chmod 600 "$temporary"
  mv "$temporary" "$env_file"
}

for key in \
  HABR_USER_AGENT \
  REMOTEOK_USER_AGENT \
  WWR_USER_AGENT \
  REMOTIVE_USER_AGENT \
  GREENHOUSE_USER_AGENT \
  TRUDVSEM_USER_AGENT
do
  set_value "$key" "JobMonitor/0.8"
done

set_value JOBICY_API_URL "https://jobicy.com/api/v2/remote-jobs"
set_value JOBICY_USER_AGENT "JobMonitor/0.8"
set_value JOBICY_TAG "automation"
set_value JOBICY_VACANCY_LIMIT "20"
set_value JOBICY_ENABLED "true"
set_value JOBICY_POLL_INTERVAL_SECONDS "21600"

chmod 600 "$env_file"
echo "Public Jobicy settings were updated in $env_file."
