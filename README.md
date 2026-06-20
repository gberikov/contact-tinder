# Contact Tinder

Self-hosted tool to clean up Google Contacts: immutable **snapshots** (backups) via the Google
People API, **working copies** derived from them, and (later) deduplication + keep/delete triage.

Feature **001-people-api-snapshots** (this slice) delivers the data foundation: connect Google
accounts (read-only), capture immutable snapshots, browse them, derive working copies, and delete
snapshots safely. No data is ever written back to Google.

See the project constitution in `.specify/memory/constitution.md` and the feature spec/plan under
`specs/001-people-api-snapshots/`.

## Stack

- **Backend**: Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic · PostgreSQL
- **Worker**: PostgreSQL-backed resumable import job (no Redis)
- **Frontend**: Vue 3 · Vite · TypeScript · Pinia · Biome
- **Dedup engine** (future): Zingg on Apache Spark

## Google Cloud setup

1. Create a Google Cloud project and **enable the People API**.
2. Create an **OAuth 2.0 Client** (Web application) with redirect URI
   `http://localhost:8000/api/accounts/callback`.
3. On the OAuth consent screen add the scope
   `https://www.googleapis.com/auth/contacts.readonly` and add your Google account as a test user.

## Configuration

Copy `.env.example` to `.env` (git-ignored) and fill in:

```bash
cp .env.example .env
# generate the token encryption key:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Never commit `.env`, tokens, or contact exports (Constitution Principle I; enforced by `.gitignore`).

## Run (docker-compose)

```bash
docker compose up --build      # db, backend (:8000), worker, web (:5173)
docker compose exec backend alembic upgrade head
```

Open http://localhost:5173 → connect a Google account → create a snapshot.

## Develop & test

Backend:

```bash
cd backend
uv venv --python 3.12 .venv
uv pip install -e ".[dev]"
.venv/Scripts/python -m pytest        # unit + contract + integration (SQLite-backed; no live Google)
```

Frontend:

```bash
cd frontend
npm install
npm run test      # Vitest
npm run lint      # Biome CI gate
npm run build     # type-check + production build
```

## Validation

End-to-end validation scenarios (US1–US3, deletion, multi-account isolation, privacy checks) are in
`specs/001-people-api-snapshots/quickstart.md`.
