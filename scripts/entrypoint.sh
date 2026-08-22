#!/bin/sh
set -e

python /srv/scripts/wait_for_postgres.py

case "$ROLE" in
  api)
    python -m app.db.migrate
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers
    ;;
  worker)
    exec celery -A app.jobs.celery_app worker \
      --loglevel=INFO \
      --concurrency="${CELERY_CONCURRENCY:-4}" \
      -Q "${CELERY_QUEUES:-scans,reports,tickets,maintenance}"
    ;;
  beat)
    exec celery -A app.jobs.celery_app beat --loglevel=INFO
    ;;
  test)
    exec pytest -q "$@"
    ;;
  *)
    echo "Unknown ROLE '$ROLE' — expected one of: api, worker, beat, test" >&2
    exit 1
    ;;
esac
