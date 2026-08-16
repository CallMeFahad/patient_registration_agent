# Patient Registration Voice Agent

A voice AI agent that answers a phone call, conversationally collects new-patient
demographic information, and registers it via a REST API backed by PostgreSQL.

## Architecture

```
Caller (phone)
      │
      ▼
   Vapi  ──── Transcriber (STT) → LLM (gpt-4o-mini) → Voice (TTS)
      │
      │  LLM decides to call a tool mid-conversation
      ▼
POST /vapi/tool-calls  (FastAPI, deployed on Railway)
      │
      │  dispatches to the matching handler, reuses the same
      │  Pydantic validation + crud functions as the REST API
      ▼
PostgreSQL (Railway managed Postgres)
```

The REST API (`/patients`) and the voice agent's tools are two entry points into
the *same* service layer (`app/crud.py`) — neither duplicates the other's logic.

## Tech stack and why

| Choice | Reason |
|---|---|
| **Vapi** | Handles telephony, speech-to-text, and text-to-speech, and supports LLM tool-calling out of the box — building that pipeline from raw Twilio + a transcription service wasn't a good use of a 3-hour window. |
| **FastAPI** | Async-capable, automatic request validation via Pydantic, minimal boilerplate for a small number of endpoints. |
| **PostgreSQL (Docker locally, Railway managed in production)** | Chosen for familiarity over SQLite; Docker Compose keeps local setup to one command. |
| **SQLAlchemy (Core ORM, no Alembic)** | The schema is one table and isn't expected to change during this project, so raw versioned `.sql` migration files are simpler than introducing a migration framework. |

## Project structure

```
database/
  migrations/          numbered raw SQL migration files
  connect.py            SQLAlchemy engine + session factory
app/
  models.py              SQLAlchemy model (mirrors the migration)
  crud.py                 DB read/write functions — the actual logic
api/
  main.py                 FastAPI app, REST endpoints, Vapi webhook route
  schemas.py               Pydantic request/response models + validation
  vapi_tools.py             Handlers for each Vapi tool call
vapi_system_prompt.md        The voice agent's system prompt
docker-compose.yml            Local Postgres for development
railpack.json                  Tells Railway to install libpq5 at runtime
Procfile                        Tells Railway how to start the app
```

## Setup — running locally

1. `cp .env.example .env` and fill in real values (a local dummy password is fine).
2. `docker compose up -d` — starts a local Postgres container.
3. Run the migration:
   ```
   docker compose cp database/migrations/0001_init.sql db:/tmp/0001_init.sql
   docker compose exec db psql -U <POSTGRES_USER> -d <POSTGRES_DB> -f /tmp/0001_init.sql
   ```
4. `pip install -r requirements.txt`
5. `uvicorn api.main:app --reload`
6. Visit `http://127.0.0.1:8000/health` — expect `{"data":{"status":"ok"},"error":null}`.

## Environment variables

| Variable | Purpose |
|---|---|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | Used by `docker-compose.yml` to create the local container |
| `DATABASE_URL` | Full connection string the app actually uses to reach Postgres (local or Railway) |

`.env.example` documents the exact format; the real `.env` is gitignored.

## API reference

All responses use a consistent envelope: `{"data": ..., "error": ...}`.

| Method | Path | Description |
|---|---|---|
| GET | `/patients` | List patients. Optional query params: `last_name`, `date_of_birth`, `phone_number` |
| GET | `/patients/{id}` | Get one patient by ID |
| POST | `/patients` | Register a new patient |
| PUT | `/patients/{id}` | Partial update — only fields included in the request body are changed |
| DELETE | `/patients/{id}` | Soft delete — sets `deleted_at`, does not remove the row |

Validation (both required fields and formats — phone, zip, state, DOB-not-in-future,
sex enum) is enforced twice: once in Pydantic (`api/schemas.py`, gives a clean `422`
before the DB is touched) and once as Postgres `CHECK` constraints (the last line of
defense if application-level validation is ever bypassed).

## Voice agent design

- **System prompt**: Defined directly into Vapi's voice agent dashboard.
- **Tools** (defined in Vapi's dashboard, handled by `api/vapi_tools.py`):
  - `check_existing_patient` — looks up by phone number before registration, enabling
    the duplicate-detection bonus (offers to update instead of creating a duplicate).
  - `create_patient` — registers a new patient after confirmation.
  - `update_patient` — partial update on an existing record.
- **Error handling on the call**: if a tool call fails (bad data, DB error), the handler
  returns a plain-language message the LLM relays to the caller (e.g. "I didn't catch a
  valid phone number") rather than the call silently hanging or ending.

## Observability

Every tool call and every successful patient registration is logged to stdout
(`api/main.py`), including the final collected data payload. On Railway this is visible
under the service's **Logs** tab; locally it prints directly to the terminal running
`uvicorn`.

## Known limitations

- **The production (Railway) database migration was not confirmed to have run
  successfully during the review window.** Locally, the schema, all 5 endpoints, and
  the full voice-call flow were verified working end-to-end. The Railway deployment
  itself is live and `/health` responds correctly, but repeated attempts to run the
  migration against Railway's managed Postgres from a Windows machine hit a persistent
  connection/networking issue we weren't able to fully resolve in the time available.
  The fix, if continuing past this point, is either enabling Railway's browser-based
  SQL query tool (feature flag: "Raw SQL Query Tab") to run the migration without a
  local `psql` client at all, or installing `psql` natively on the host machine rather
  than relying on the local Docker container as a client for a remote server, which
  introduced avoidable connection-string confusion.
- API doesn't have any authorization implemented YET due to time constraints. Validation via an API key is a must when moving into production.
- No formal idempotency key on `POST /patients`. The duplicate-detection tool
  (`check_existing_patient`) is the practical mitigation for the realistic failure mode
  (a dropped call causing a retry), but a client sending two independent requests with
  different phone numbers for the same person would still create two records.
- Endpoints were verified manually via `curl` and the Vapi
  in-browser test call, given the time constraint.

## Deliverables checklist

- [x] Working REST API (5 endpoints, validation, soft delete, consistent envelope)
- [x] Voice agent with tool-calling wired to the same service layer
- [x] System prompt
- [x] Logging of tool calls and registrations to stdout
- [x] Bonus: duplicate detection by phone number
- [ ] Fully confirmed production DB (see Known Limitations)

## Next Steps
- Correction of the database connectivity issues.
- On-prem deployment of Database to ensure patient PII safety.
- Use of local agents like Qwen3-TTS to make sure the voice agent server also doesn't access the customer PII.
- Implementation of API validation via an API key for authorization.
