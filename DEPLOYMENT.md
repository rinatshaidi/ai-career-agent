# JobMonitor: Docker и VPS

## Сервисы

- `jobmonitor-worker` — полный цикл Habr Career + Remote OK + We Work Remotely → OpenAI → Telegram.
- `jobmonitor-profile-bot` — команды и анкета профиля в Telegram.

Сервисы используют один образ и общую SQLite-базу в `./data`. Каталог `./logs`
содержит rotating file log worker. Порты наружу не публикуются.

## Каталоги VPS

Production-каталог: `/opt/jobmonitor`.
Закрытый временный каталог: `/root/jobmonitor-staging`.

До подготовки production-каталога в staging должны находиться:

```text
/root/jobmonitor-staging/jobmonitor-deploy.tar.gz
/root/jobmonitor-staging/.env
/root/jobmonitor-staging/jobmonitor.db
```

Файл `.env` не входит в Docker-образ и не должен попадать в Git. SQLite-база
также не входит в образ и хранится в постоянном bind mount.

## Расписание источников

Block 8 не требует отдельного контейнера для каждого источника. Один worker
использует постоянное состояние расписания в общей SQLite-базе. При первом
запуске после обновления таблицы `source_runs` и `source_states` создаются
автоматически без удаления существующих данных.

Новые необязательные параметры `.env`:

```text
HABR_ENABLED=true
HABR_POLL_INTERVAL_SECONDS=300
REMOTEOK_ENABLED=true
REMOTEOK_POLL_INTERVAL_SECONDS=900
WWR_ENABLED=true
WWR_POLL_INTERVAL_SECONDS=900
```

Если параметры отсутствуют в существующем production `.env`, используются эти
значения по умолчанию. Минимально допустимый интервал любого источника — 60 секунд.

## Этап 1. Подготовка файлов

Скрипт только подготавливает `/opt/jobmonitor`. Он не собирает образ и не
запускает контейнеры.

```bash
sh /root/jobmonitor-staging/deploy_vps.sh
```

## Этап 2. Проверка Compose

```bash
cd /opt/jobmonitor
docker compose config --quiet
```

## Этап 3. Сборка образа

```bash
cd /opt/jobmonitor
timeout 300s docker compose --progress plain build
docker image inspect jobmonitor:0.3
```

## Этап 4. Запуск profile-bot

```bash
cd /opt/jobmonitor
docker compose up -d profile-bot
docker compose ps profile-bot
docker compose logs --tail 100 profile-bot
```

После проверки Telegram-бота перейти к worker.

## Этап 5. Запуск worker

```bash
cd /opt/jobmonitor
docker compose up -d worker
docker compose ps worker
docker compose logs --tail 100 worker
```

## Этап 6. Итоговое состояние

```bash
cd /opt/jobmonitor
docker compose up -d
docker compose ps
docker inspect --format '{{.State.Health.Status}}' jobmonitor-worker
docker inspect --format '{{.State.Health.Status}}' jobmonitor-profile-bot
```

## Проверка логов

```bash
cd /opt/jobmonitor
docker compose logs --tail 100 worker profile-bot
```

## Перезапуск и сохранность

```bash
cd /opt/jobmonitor
docker compose restart
docker compose ps
```

После перезапуска число записей в `data/jobmonitor.db` и сохранённый профиль
должны остаться прежними. Одновременно должен работать только один long polling
процесс `profile_bot.py` для используемого Telegram-токена.

## Остановка

```bash
cd /opt/jobmonitor
docker compose down
```

Compose ожидает корректного завершения процесса не более 60 секунд. Команда
`down` не удаляет bind-mounted каталоги `data` и `logs`.
