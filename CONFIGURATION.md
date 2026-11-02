# Configuration

## Provider setup

Copy `backend/.env.example` to `backend/.env` and set the credentials:

```env
GOOGLE_API_KEY=your-google-api-key
OPENROUTER_API_KEY=your-openrouter-api-key
```

`GOOGLE_API_KEY` is used for document and query embeddings. `OPENROUTER_API_KEY` is used for LLM answer generation. Keep both private and do not commit `backend/.env`. Docker Compose loads this file into the API and worker containers.

The application defaults to `google/gemma-4-31b-it:free` on OpenRouter. OpenRouter currently lists this chat model as free with a 262,144-token context window. The retrieved context is limited to eight chunks, plus at most ten previous chat messages, so this model's context is well above the application's normal prompt size. Free endpoints have provider rate and availability limits.

Optional overrides in `backend/.env`:

| Variable | Default | Purpose |
| --- | --- | --- |
| `OPENROUTER_MODEL` | `google/gemma-4-31b-it:free` | OpenRouter model ID for answer generation |
| `OPENROUTER_FALLBACK_MODELS` | NVIDIA Nemotron 3.5 Lightning Free, then Nemotron 3 Ultra Free | Comma-separated OpenRouter model fallback IDs |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | OpenAI-compatible OpenRouter endpoint |
| `OPENROUTER_TIMEOUT_SECONDS` | `90` | Per-request network timeout |
| `FRONTEND_ORIGIN` | `http://localhost:8080` | CORS origin and OpenRouter app attribution |
| `LOG_LEVEL` | `INFO` | Application log level |
| `LOG_COLOR` | `true` | Colorized container logs |

To change the model, use any chat model ID enabled for your OpenRouter account. The API is OpenAI-compatible; the backend sends chat-completions messages, including the system instruction, recent conversation turns, and the workspace-retrieved PDF context.

## Run with Docker

After setting the two provider keys, run from the repository root:

```bash
./restart_project.sh
```

This builds and starts the app and follows colorized service logs in the same terminal. The web app is at `http://localhost:8080`, and backend API docs are at `http://localhost:8000/docs`.

For local backend development, install `backend/requirements.txt` and run the API and worker using the same environment values. The OpenRouter Python client is installed from that requirements file. Gemini remains a dependency because it provides embeddings.

## Security and operations

- Do not put provider keys in Docker image build arguments, source code, or committed files.
- For deployment, use a secret manager instead of a checked-in environment file.
- OpenRouter errors are logged with model, status, request ID, attempt count, and timing; prompt text and API keys are not logged.
- Free models have shared account limits (currently 20 requests/minute and 50 requests/day on accounts without purchased credits). Fallback models can route around an individual model/provider throttle, but cannot bypass an exhausted account-wide free quota. A 429 is not retried immediately, to avoid consuming more free requests; the API returns a clear rate-limit message and forwards `Retry-After` when supplied.
- Transient network, timeout, HTTP 408/409, and provider 5xx failures receive up to two bounded exponential retries. Invalid credentials, model IDs, and quota/credit errors fail without retrying.
