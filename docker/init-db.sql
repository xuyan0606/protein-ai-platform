-- Auto-create Outline wiki database on first Postgres init.
-- This file is mounted to /docker-entrypoint-initdb.d/ and runs once
-- when the pgdata volume is empty (fresh install).

CREATE DATABASE outline;
CREATE DATABASE outline_test;
