# FORGE-Vision — Deployment

Two supported deployment paths, both running the **same proven topology**:
one public entry (Caddy) routes API + the live-camera **WebSocket** to FastAPI
and everything else to the native-login Streamlit UI. The React frontend is not
deployed; Streamlit uses its built-in login (`UI_STANDALONE_LOGIN=1`).

| Path | Best for | TLS | Database |
|------|----------|-----|----------|
| **A. Self-hosted (Docker Compose)** | Your own VPS / server, a real domain | Caddy + Let's Encrypt | Bundled Postgres container |
| **B. Hugging Face Space + Supabase** | Free zero-server demo | HF-managed | Supabase (free) |

```
Browser (remote user)
  └─ HTTPS ─► Caddy (one port) ─► /api,/ws,/health → FastAPI :8000 ─► Postgres
                                  else              → Streamlit :8501 (native login)
```

> The live camera streams webcam JPEG frames over a **WebSocket** to FastAPI
> (`/api/v1/ws/live`), which runs the CV pipeline (pose + YOLO overlay) and
> streams annotated frames + LLM feedback back. No WebRTC/TURN/UDP — it works
> through the single HTTP port that both hosts expose.

---

## A. Self-hosted (Docker Compose)

Files: `docker-compose.prod.yml`, `deploy/Caddyfile`, `.env.production.example`.

### 1. Prerequisites
- A host with Docker + Docker Compose, ports **80** and **443** reachable.
- A **domain** whose DNS A/AAAA record points at the host (Caddy needs it to
  issue the certificate on first boot).
- These present on the host: `./data` (SOP library) and
  `./models/action_recognizer_best.pth` (the trained checkpoint — gitignored,
  copy it across manually). The rest of the code is baked into the image.

### 2. Configure
```bash
cp .env.production.example .env.production
# Edit .env.production:
#   DOMAIN, ACME_EMAIL
#   POSTGRES_PASSWORD            (strong random)
#   SETTINGS_ENCRYPTION_KEY      python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
#   JWT_SECRET_KEY               openssl rand -hex 32
#   SEED_ON_START=1              (first boot only — auto-seeds synthetic data if empty)
```
> The app **refuses to boot in production** on the dev `JWT_SECRET_KEY` /
> missing `SETTINGS_ENCRYPTION_KEY` (`src/api/main.py` startup guard).

### 3. Launch
```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```
On `api` startup this runs `alembic upgrade head`, then (if `SEED_ON_START=1`)
`seed_simulation_data --if-empty` to populate the dashboard with synthetic data
(256 workers / 1,555 sessions) only when the tables are empty.

### 4. Create your admin user
The seeder only creates synthetic staff/trainer/manager. Registration **always creates a
`staff` user** (the API ignores any `role` field), so it takes two steps. Register, then promote
the account in the database.

**a) Register** (password needs ≥8 chars, one uppercase letter, one digit; `gdpr_consent` is required):
```bash
curl -k -X POST https://$DOMAIN/api/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","first_name":"Ada","last_name":"Admin","password":"<strong>","gdpr_consent":true}'
```
On Windows PowerShell use `Invoke-RestMethod` with a `ConvertTo-Json` body — `curl` there is an alias and
mangles the JSON quotes.

**b) Promote to admin** (psql, or the Supabase **SQL Editor** for the hosted database):
```sql
UPDATE users SET role = 'admin' WHERE email = 'you@example.com';
```
`/auth/register` is rate-limited to 5 requests/minute.

### 5. After first boot
- Set `SEED_ON_START=0` in `.env.production` and `docker compose ... up -d` again.
- Log in → **Settings** → enter your LLM key (e.g. Groq); it's stored encrypted
  in the DB. Live-camera AI feedback uses it.

### Operating notes
- **Backups:** the Postgres data lives in the `postgres_data_prod` volume —
  back it up (`docker exec forge_prod_db pg_dump …`).
- **Single API worker** is intentional: the realtime session manager keeps
  in-memory session state and loads the CV models once. Scale by replicas behind
  Caddy only if you make session state external first.
- **Logs:** `docker compose -f docker-compose.prod.yml logs -f api caddy`.
- **TLS troubleshooting:** if Caddy can't get a cert, confirm DNS resolves to the
  host and ports 80/443 are open; check `docker compose ... logs caddy`.
- **External managed DB instead of the bundled one:** set `DATABASE_URL` in
  `.env.production` (see the Supabase example in that file) and you may delete the
  `db` service from `docker-compose.prod.yml`.

---

## B. Hugging Face Space + Supabase (free demo)

Single container (Caddy + FastAPI + Streamlit via supervisord) on a free HF
Docker Space, backed by free Supabase Postgres. This is what's live at
`https://huggingface.co/spaces/MashkurA/forge-vision`.

Files: `Dockerfile.hf`, `space/` (`Caddyfile`, `supervisord.conf`, `start.sh`,
`README.md`, `.gitattributes`), assembled by `scripts/build_hf_space.py`.

### 1. Supabase (free Postgres)
1. Create a project at <https://supabase.com> → **Project Settings → Database**.
2. Build the asyncpg URL. The free tier is IPv6-only on the direct host, so use
   the **session pooler** and disable prepared statements. Copy the exact host from
   **Connect → Direct → Session pooler** — it is `aws-0-…` or `aws-1-…` depending on the project:
   ```
   DATABASE_URL=postgresql+asyncpg://postgres.<ref>:<PWD>@aws-1-<region>.pooler.supabase.com:5432/postgres?ssl=require&prepared_statement_cache_size=0
   ```
   (URL-encode special characters **inside the password**, e.g. `@` → `%40`. The single `@` between the
   password and the host must stay a plain `@`; encoding it too makes the app crash on boot with
   `ValueError: invalid literal for int()`. A letters-and-digits-only password avoids the issue.)

> **Free-tier lifetime:** a free Supabase project pauses after about a week of inactivity and is
> deleted if it stays paused too long (the data is lost). Keep it active with a scheduled ping to the
> Space's `/health` endpoint — each call writes an `audit_logs` row. This project uses the private
> GitHub repo `forge-vision-keepalive` (every 12 hours).
3. Bootstrap once, pointed at Supabase:
   ```bash
   alembic upgrade head
   python -m src.evaluation.seed_simulation_data --if-empty
   ```
   Or let the Space do it on first boot with `SEED_ON_START=1`.

### 2. Assemble + push the Space repo
```bash
python scripts/build_hf_space.py --out hf_space_build --git-init \
  --remote https://<HF_USER>:<HF_TOKEN>@huggingface.co/spaces/<HF_USER>/<space>
cd hf_space_build && git push -f space main      # model ships via Git LFS
```
> For small `src/` changes afterwards, copy the changed files into
> `hf_space_build/` and `git push space main` — do **not** re-run the build
> script (it re-inits the remote and re-uploads the LFS model). If you change the
> Dockerfile, edit both `Dockerfile.hf` and `hf_space_build/Dockerfile`.

### 3. Space secrets (Settings → Variables and secrets)
| Secret | Value |
|--------|-------|
| `DATABASE_URL` | Supabase asyncpg pooler URL from step 1 |
| `SETTINGS_ENCRYPTION_KEY` | Fernet key |
| `JWT_SECRET_KEY` | long random string |
| `ALLOWED_HOSTS` | `*` (Caddy forwards the HF Host header) |
| `SEED_ON_START` | `1` first boot only; set back to `0` after |

> Changing `SETTINGS_ENCRYPTION_KEY` makes any LLM key already stored in the database unreadable —
> re-enter it in **Settings**. A fresh database needs the key set before the first boot.

The LLM key (Groq etc.) is entered in the in-app **Settings** page after login
and stored encrypted in the DB.

### 4. Verify (both paths)
- Build/startup logs show migrations + the services starting.
- Open the URL → native login → dashboard populated (if seeded).
- **Live Training** → consent → SOP → Start → allow camera → pose skeleton +
  object boxes + AI feedback streamed back over the WebSocket.
