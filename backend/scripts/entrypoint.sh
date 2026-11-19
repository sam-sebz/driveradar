#!/bin/sh
# Container start: migrate the database, optionally seed demo data, then serve.
set -eu

echo '{"msg": "running migrations"}'
alembic upgrade head

python -m app.seed

exec uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 --no-access-log
