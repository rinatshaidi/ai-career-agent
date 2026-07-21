#!/bin/sh
set -eu

ENV_FILE=${1:-.env}

if [ ! -f "$ENV_FILE" ]; then
    printf '%s\n' "Environment file not found: $ENV_FILE" >&2
    exit 1
fi

set_env() {
    key=$1
    value=$2
    if grep -q "^${key}=" "$ENV_FILE"; then
        sed -i "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
    else
        printf '%s=%s\n' "$key" "$value" >> "$ENV_FILE"
    fi
}

set_env HABR_USER_AGENT "JobMonitor/0.8"
set_env REMOTEOK_USER_AGENT "JobMonitor/0.8"
set_env WWR_USER_AGENT "JobMonitor/0.8"
set_env REMOTIVE_USER_AGENT "JobMonitor/0.8"
set_env GREENHOUSE_USER_AGENT "JobMonitor/0.8"
set_env TRUDVSEM_API_URL "https://opendata.trudvsem.ru/api/v1/vacancies"
set_env TRUDVSEM_USER_AGENT "JobMonitor/0.8"
set_env TRUDVSEM_SEARCH_QUERIES "автоматизация бизнеса;n8n;OpenAI;Telegram бот;искусственный интеллект;интеграция API"
set_env TRUDVSEM_REGION_CODES ""
set_env TRUDVSEM_PER_QUERY_LIMIT "10"
set_env TRUDVSEM_VACANCY_LIMIT "20"
set_env TRUDVSEM_INITIAL_LOOKBACK_DAYS "14"
set_env TRUDVSEM_ENABLED "true"
set_env TRUDVSEM_POLL_INTERVAL_SECONDS "3600"

chmod 600 "$ENV_FILE"
printf '%s\n' "Rabota Rossii environment settings configured."
