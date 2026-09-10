# React manufacturing cockpit reference

## Layout and dependency boundaries

```text
app.py                     V1 Streamlit entrypoint
imjingang_agent/            Shared repository, tool registry, AI service and documents
v2/api.py                  FastAPI app factory and HTTP boundary
v2/web/src/                 React + TypeScript UI and typed API client
v2/web/package-lock.json   Repeatable client dependency resolution
v2/Dockerfile              Node build stage → Python API/static runtime
v2/docker-compose.yml      Dedicated V2 app + pgvector PostgreSQL
v2/tests/                  API behavior tests with isolated SQLite
skills/                    Version-controlled reusable skill packages
```

The API owns repository initialization through FastAPI lifespan, once per process. React renders fetched data and doesn't import seed fixtures. The V2 demo DB is independent of V1. PostgreSQL initialization must create and commit the vector extension before registering its type adapter; reinitialization must retain rules, documents and settings.

## API contract

- `GET /api/health`: checks DB access as well as process liveness.
- `GET /api/workspace`: KPIs, LOTs, measurements/predictions, quality/shipment/inventory, rules, table counts, recommendations and non-secret capability metadata. Dates describe the records, not today's operational state.
- `GET /api/lots/{id}`: selected LOT, connected lineage, measurements, CCP and shipment evidence. Unknown IDs return 404.
- `GET /api/documents?q=...`: bounded keyword retrieval or complete document catalog, excluding embeddings and private settings.
- `GET /api/tables/{name}?limit=...&offset=...`: whitelisted, bounded, stable paging. No arbitrary SQL endpoint.
- `POST /api/chat`: validated question, optional selected LOT, explicit `demo` or `ai` mode; returns text, sources, excerpts, tool names, actual record results and mode.
- `POST /api/chat/reset`: clear the HTTP-only session's provider chain.
- Voice requests use server provider credentials and the same access gate as paid chat. A transcript populates the editable composer and requires explicit send. Audio file limits and provider timeout errors remain visible. Revoke object URLs after playback replacement/unmount.

Responses chaining lives server-side under an opaque HTTP-only SameSite cookie with expiry and a bounded session count. Don't accept raw `previous_response_id` from React. Use bounded provider concurrency/timeouts. For multi-worker production, use a shared session store if chain persistence across workers is required; the reference runs one worker.

The demo mode handles explicit LOT/claim IDs, stock, fermentation, CCP, shipment, rules and document search without external calls. It must disclose that fixed record summaries are not an LLM. If the question asks about today but the source is historical, state the actual source date. If a combined query cannot be fully answered by the selected demo handler, make the limitation visible rather than claiming complete coverage.

## Deployment

Node 22+ builds React; Python 3.11+ serves API and static assets. The V2 container port is 8510; the paired Hostinger example reserves host 8503 because V1 uses 8502 and the original Kyungdong cockpit uses 8501. These are example allocations, not universal defaults. Validate the destination before publishing.

`DATABASE_URL` selects PostgreSQL, `V2_SQLITE_PATH` selects offline storage, `OPENAI_API_KEY` and `OPENAI_MODEL` configure the provider, and `COCKPIT_ACCESS_TOKEN` gates paid endpoints. Browser bundle variables must never contain provider keys. Use an appropriate HTTPS/reverse-proxy setup before browser microphone capture or credential entry over the public internet; audio-file selection works without capture but still requires provider setup.

In the observed Hostinger Docker Manager flow, composing a `build:` service did **not** build its image. It attempted to start a missing image. When that behavior recurs, use the authorized VPS console to `docker build` from the exact source revision, tag the image used by Compose, then validate and start it. Preserve its compose labels so Docker Manager can manage the project. Don't blindly redeploy the same missing image or overwrite another company's service.

Reference docs: [Vite](https://vite.dev/guide/), [FastAPI frontend](https://fastapi.tiangolo.com/tutorial/frontend/), [FastAPI static files](https://fastapi.tiangolo.com/tutorial/static-files/). Check current APIs when changing versions rather than encoding a moving “latest” assumption into the skill.
