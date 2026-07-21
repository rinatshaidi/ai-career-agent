# JobMonitor: Docker и VPS

## Сервисы

- `jobmonitor-worker` — полный цикл Habr Career + Remote OK + We Work Remotely + Remotive + Greenhouse + «Работа России» + Jobicy → OpenAI → Telegram.
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
REMOTIVE_ENABLED=true
REMOTIVE_VACANCY_LIMIT=20
REMOTIVE_POLL_INTERVAL_SECONDS=21600
GREENHOUSE_ENABLED=false
GREENHOUSE_BOARDS=remotecom|Remote;nebius|Nebius;fueledcareers|Fueled;spotme|SpotMe
GREENHOUSE_VACANCY_LIMIT=20
GREENHOUSE_POLL_INTERVAL_SECONDS=3600
TRUDVSEM_ENABLED=true
TRUDVSEM_SEARCH_QUERIES=автоматизация бизнеса;n8n;OpenAI;Telegram бот;искусственный интеллект;интеграция API
TRUDVSEM_REGION_CODES=
TRUDVSEM_PER_QUERY_LIMIT=10
TRUDVSEM_VACANCY_LIMIT=20
TRUDVSEM_INITIAL_LOOKBACK_DAYS=14
TRUDVSEM_POLL_INTERVAL_SECONDS=3600
JOBICY_API_URL=https://jobicy.com/api/v2/remote-jobs
JOBICY_USER_AGENT=JobMonitor/0.8
JOBICY_TAG=automation
JOBICY_VACANCY_LIMIT=20
JOBICY_ENABLED=true
JOBICY_POLL_INTERVAL_SECONDS=21600
MAX_PENDING_AI_QUEUE=50
SOURCE_INITIAL_IMPORT_LIMIT=20
```

Если параметры отсутствуют в существующем production `.env`, используются эти
значения по умолчанию. Минимальный интервал Habr Career, Remote OK и We Work Remotely — 60 секунд. Для Remotive жёстко установлен минимум 21 600 секунд, а быстрые повторы HTTP-запроса отключены. Greenhouse по умолчанию выключен; после выбора компаний минимальный интервал каждой доски составляет 900 секунд. Для «Работы России» установлен минимум 3 600 секунд, первый запрос охватывает 14 дней, а следующие используют `modifiedFrom` от времени последнего успешного запуска. Jobicy выполняет один фильтрованный запрос `tag=automation` не чаще одного раза в 21 600 секунд; быстрые повторы отключены. Первый запуск нового источника импортирует не более `SOURCE_INITIAL_IMPORT_LIMIT` записей. Если очередь `new` достигла `MAX_PENDING_AI_QUEUE`, очередной источник откладывается и сохраняет право на следующий запуск.

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
docker image inspect jobmonitor:0.12
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

## Проверка «Работы России»

Безопасный smoke test не читает `.env`, не пишет в SQLite и не вызывает OpenAI или Telegram:

```bash
cd /opt/jobmonitor
docker run --rm -v "$PWD/scripts/smoke_trudvsem.py:/app/smoke_trudvsem.py:ro" \
  jobmonitor:0.12 python /app/smoke_trudvsem.py
```

Ожидаются `count` от 0 до 3 и `normalized=true`. Нулевой результат допустим, если за период нет совпадений.

## Проверка Jobicy

Безопасный smoke test не читает `.env`, не пишет в SQLite и не вызывает OpenAI или Telegram:

```bash
cd /opt/jobmonitor
docker run --rm -v "$PWD/scripts/smoke_jobicy.py:/app/smoke_jobicy.py:ro" \
  jobmonitor:0.12 python /app/smoke_jobicy.py
```

Ожидаются `count` от 0 до 3 и `normalized=true`. Запрос использует официальный фильтр `tag=automation`.

## Откат с 0.8 на 0.7

Образ `jobmonitor:0.7` и файл `docker-compose.yml.rollback-0.7-jobicy` сохранены на VPS. Для отката восстановить этот Compose-файл и выполнить:

```bash
cd /opt/jobmonitor
cp docker-compose.yml.rollback-0.7-jobicy docker-compose.yml
docker compose up -d --no-build --force-recreate
docker compose ps
```

Дополнительные переменные `JOBICY_*` игнорируются версией `0.7`; базу данных и `.env` удалять не требуется.
