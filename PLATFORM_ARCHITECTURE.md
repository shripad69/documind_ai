# Workspace RAG platform

## Storage and service choices

- PostgreSQL 16 with pgvector stores accounts, workspaces, source records, chat history, and 384-dimensional Gemini embeddings. This keeps ownership constraints and vector metadata in one database and gives local Docker development a persistent, inspectable store.
- Redis and a Celery worker handle document parsing and embedding outside the upload request. Uploads accept PDF and DOCX files and expose `processing`, `indexed`, or `failed` status.
- Uploaded source files live in the shared Docker `document_storage` volume. For a multi-host deployment, replace this with private object storage and keep only an object key in `documents.file_path`.
- Argon2id password hashes and signed JWTs backed by revocable server-side sessions provide authentication. The browser stores the JWT only in an HttpOnly cookie.
- Gemini `gemini-embedding-001` generates document and query vectors. OpenRouter's OpenAI-compatible chat completions API generates answers using `google/gemma-4-31b-it:free` by default; `OPENROUTER_MODEL` can override it. Retrieval remains scoped by user and workspace, and the cited document/page references are stored with the assistant message.
- OpenRouter requests include up to ten prior turns and the retrieved workspace context, with free-model fallbacks when a model/provider is rate limited. Timeout/network errors, HTTP 408/409, and provider 5xx errors use at most two bounded exponential retries. HTTP 429 returns a clear free-tier limit message without rapid retries; credential, model, and quota errors fail quickly with sanitized operational logs.

## Start and inspect

From the repository root, run `./restart_project.sh`. It rebuilds changed images and starts PostgreSQL, Redis, API, worker, and frontend. The frontend is at `http://localhost:8080`; OpenAPI docs are at `http://localhost:8000/docs`.

Run `./restart_project.sh` to rebuild/start the stack and follow color-coded live logs in that same terminal. `Ctrl+C` stops log viewing while leaving the services running. The Docker log driver rotates each service's logs at 10 MB per file and keeps five files. Set `LOG_COLOR=false` to disable ANSI level colors when collecting logs. PostgreSQL migrations run automatically before the API starts. Data persists in named Docker volumes; `docker compose down -v` deletes that local database, queue data, and uploaded files.

## Deployment settings

Keep `GOOGLE_API_KEY` (embeddings) and `OPENROUTER_API_KEY` (answer generation) in `backend/.env` and do not commit that file. See [CONFIGURATION.md](CONFIGURATION.md) for model and timeout settings. Set `POSTGRES_PASSWORD` and a long random `JWT_SECRET_KEY` in the root environment for deployment, configure `FRONTEND_ORIGIN` to the actual browser origin, and set `COOKIE_SECURE=true` when serving over HTTPS. Use a managed PostgreSQL/pgvector and Redis service, private object storage, TLS termination, and a secrets manager for a multi-instance production deployment. The compose defaults are for local development only.

The API scopes every workspace operation to the signed-in user. Vector retrieval filters by both `user_id` and `workspace_id` before ranking, then returns source document IDs, names, pages, and snippets with the answer.
