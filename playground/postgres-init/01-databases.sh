#!/bin/sh
# Runs once, on first container start only (postgres:17-alpine's own entrypoint convention:
# every *.sh under /docker-entrypoint-initdb.d/ executes iff the data directory was empty).
# POSTGRES_DB (docker-compose.yml) only creates ONE database — this creates the second one the
# subclassed host needs. Both hosts must never share a database: `swappable` skips
# dynamic_user_user/_profile/_setting on the swapped leg entirely, so the two hosts' migrations
# produce genuinely different table sets against the same POSTGRES_USER.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-SQL
    CREATE DATABASE playground_subclassed OWNER $POSTGRES_USER;
SQL
