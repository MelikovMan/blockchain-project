#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
	CREATE USER regulator_master ENCRYPTED PASSWORD 'regulator_master' LOGIN;
	CREATE DATABASE regulator OWNER regulator_master;
EOSQL

psql -v ON_ERROR_STOP=1 --username "regulator_master" --dbname "regulator" -f /app/sql/init-db.sql
