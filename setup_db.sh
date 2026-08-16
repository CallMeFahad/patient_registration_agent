#!/bin/bash
set -e

# Create the 'patients' database on the default 'postgres' database
PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$PGHOST" -U "$POSTGRES_USER" -d postgres -c "CREATE DATABASE IF NOT EXISTS patients;"

# Run migrations on the 'patients' database
PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$PGHOST" -U "$POSTGRES_USER" -d patients < /app/database/migrations/0001_init.sql

echo "Database setup complete."

