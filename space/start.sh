#!/usr/bin/env bash
# FORGE-Vision — Hugging Face Space entrypoint.
# 1. Apply DB migrations against the configured DATABASE_URL (Supabase).
# 2. Optionally seed synthetic simulation data on first boot (SEED_ON_START=1),
#    only when the operational tables are empty (--if-empty), so the dashboard
#    has records without touching real participant data.
# 3. Launch the API + UI under supervisord.
set -euo pipefail

echo "[start] FORGE-Vision Space booting..."

if [ -n "${DATABASE_URL:-}" ]; then
    echo "[start] Applying Alembic migrations..."
    alembic upgrade head || echo "[start] WARNING: alembic upgrade failed (continuing)."

    if [ "${SEED_ON_START:-0}" = "1" ]; then
        echo "[start] Seeding simulation data if empty..."
        python -m src.evaluation.seed_simulation_data --if-empty \
            || echo "[start] WARNING: seeder skipped/failed (continuing)."
    fi
else
    echo "[start] WARNING: DATABASE_URL not set — skipping migrations/seed."
fi

echo "[start] Starting supervisord (api:8000 + ui:7860)..."
exec supervisord -c /app/space/supervisord.conf
