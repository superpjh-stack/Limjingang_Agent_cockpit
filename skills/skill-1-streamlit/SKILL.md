---
name: skill-1-streamlit
description: "스킬1 — Streamlit 기반 제조 AI Agent Cockpit을 만들거나 확장합니다. 빠른 시제품과 사내 분석 화면에 사용하며, React 기반 V2 또는 스킬2 요청에는 사용하지 않습니다."
metadata:
  short-description: 스킬1 · Streamlit 제조 AI 에이전트
---

# 스킬1 · Streamlit Agent Cockpit

Use this skill for a Streamlit manufacturing cockpit, including food and metal manufacturing. Adapt the company-specific process, terminology, and approval documents. Preserve the user's existing data model and conversation flow while making the cockpit useful to production, purchasing, design, and quality staff.

The original reference implementation is the Kyungdong Globaltech cockpit (`kyungdong-globaltech-ai-agent`): Streamlit app, `kyungdong_agent/` package, `sample_docs/knowledge/` documents and rules, `scripts/migrate_sqlite_to_postgres.py`, `tests/`, `Dockerfile`, and `docker-compose.yml`. When adapting to another company, copy the structure and replace the domain content; do not carry over Kyungdong project IDs, customers, or measurements.

## Product shape

- Keep one connected workspace: KPI strip, manufacturing conversation, recommendations, and a knowledge/data panel.
- Use an industrial visual language: steel or charcoal neutrals, one safety-orange accent, compact rectangular surfaces, readable Korean typography, and touch-sized controls on mobile.
- Give the conversation a distinct visual identity instead of styling it like another data card. On desktop, use a high-contrast chat console with a clear header/status line, warm accent edge, and visible user/assistant message hierarchy. Keep the console visually dominant without obscuring evidence controls.
- On narrow mobile screens, make the conversation the primary surface: hide secondary dashboards, recommendation lists, knowledge tables, and voice controls when they compete with reading and sending messages. Keep the chat input reachable and use `100dvh`-aware sizing without horizontal overflow.
- Treat every number, document, and prediction as demo or operational data explicitly. Never imply that a forecast is an achieved KPI.
- Keep actions read-only by default. Quotes, purchase orders, substitute materials, FAT acceptance, shipment, and safety decisions require human approval.
- Offer recommended questions in three groups that mirror the three data sources (knowledge documents, DB, rules), about ten each. Every recommendation, history item, and voice transcript must go through the same `pending_question` path as typed input.

## Knowledge and data

Separate three sources:

1. **RAG knowledge**: approved or clearly labeled sample documents such as process flow, estimating, drawing changes, incoming inspection, material substitution, laser cutting, forming, welding, FAT, and delay response. Store document number, revision, owner, effective date, status, searchable content, and the database identifiers it explains.
2. **Process DB**: projects, drawings, materials/Lots, incoming inspections, operations, equipment readings, quote predictions, purchase orders, FAT tests, claims, and knowledge-document metadata.
3. **Rules DB**: rule ID, name, source table, condition, owner, action, source document, revision, and status. Rules describe findings and recommended follow-up; they must not execute external work automatically.

Use PostgreSQL as the local operational backend when `DATABASE_URL` is configured. Enable the `vector` extension and keep document embeddings in a fixed-dimension `vector` column with an ANN index. Preserve a SQLite fallback for offline tests and first-run demos, but do not describe SQLite as the production architecture.

On a brand-new PostgreSQL database, create the `vector` extension on a connection that has not registered the pgvector type adapter, commit, and only then open normal connections. Registering the adapter before the extension exists fails and leaves the connection open; close it on failure. Cover this with a regression test that creates a throwaway database from an admin URL and skips when that URL is absent.

When replacing an existing SQLite demo database, use the repository's migration script rather than copying files. Migrate business tables, rules, knowledge documents, and settings; make a full replacement import idempotent so seed rows do not duplicate tables without unique keys. Keep vector retrieval optional: lexical document search must still work when embeddings or an API key are unavailable.

Expose read-only table browsing with row counts, a selected-table view, record details, and a clear empty state. Add a small knowledge browser with keyword search, document body view, provenance, and (when embeddings exist) nearest-neighbor retrieval. Persist local sample documents and rules in PostgreSQL when configured so a restart does not make the cockpit appear empty.

## Retrieval and answer behavior

- Give the agent read-only tools for project, material, inspection, quote, procurement, FAT, lead-time, claim, rule, DB-table, and local-document retrieval. Keep the tool registry a whitelist: unknown or write-style tool names return an error payload, and every successful payload carries `demo_data: true` plus a `status`.
- Run the OpenAI Responses tool loop with strict JSON schemas, `parallel_tool_calls` off, and a hard round cap; when the cap is reached, force a text answer with `tool_choice: none` so the user never receives an empty reply. Accumulate cited files and search snippets across every round, not only from the final response.
- Search knowledge documents whenever the question asks about a procedure, SOP, tolerance, approval, inspection criterion, or rule. Cite only documents actually returned by retrieval. Record whether any document search ran, and show a warning under the answer when it did not.
- Answer in easy Korean in at most five lines: answer first, then the immediate reason or next action, then one final line beginning `근거:`. Use plain terms such as “도면 버전” and “작업시간”. Keep detailed evidence behind a UI disclosure panel.
- If evidence is missing, say that it could not be confirmed. Distinguish a sample rule or prediction from an approved operational standard.

## API key and model settings

- Read the server default key from `OPENAI_API_KEY` (project `.env` locally, container environment in deployment) and apply it to every new session automatically.
- Never pre-fill the full server key into a text input. Show only a masked tail (last four characters) and the source label (server default vs session override).
- Put key, model, and retrieval-depth changes in a collapsed form. An empty key field means keep the current key; a submitted key applies to the current session only. Offer a one-click return to the server default key.
- Reset the Responses conversation chain identifier whenever the key changes, because a response chain cannot be continued under a different key.
- Bound each model call with a request timeout and a small retry count so a stalled request does not hold the Streamlit run forever.

## Voice interface

When an API key is available, provide a stable-key `st.audio_input` control for Korean speech-to-text, a reviewable editable transcript, and an explicit send button. Provide a per-assistant-message “음성으로 듣기” action using text-to-speech and cache the generated bytes in session state. Do not change the audio widget key during reruns or conversation reset; this avoids Streamlit DOM removal errors. Keep recordings in memory and tell the user that transcription is sent to the configured API.

If the key is unavailable or audio fails, disable the controls with a clear fallback to typed questions. Enforce reasonable size and text-length limits and show actionable errors.

## Deployment

Ship a `Dockerfile` and a `docker-compose.yml` that run the Streamlit app together with a `pgvector/pgvector` PostgreSQL image. Require `POSTGRES_PASSWORD` through Compose variable interpolation, gate the app on the database healthcheck, keep the database in a named volume, and pass `OPENAI_API_KEY`, `OPENAI_MODEL`, and `DATABASE_URL` only as environment values. Copy only runtime files plus the demo SQLite database into the image; exclude `.env`, virtual environments, caches, and local PostgreSQL data directories via `.dockerignore` and `.gitignore`. Document how to change the server key on the target host (for example the Hostinger Docker Manager environment or a `.env` beside the Compose file, then recreate the app container). Keep one source of truth for the default model name across `.env.example`, Compose, and code.

## Validation

Run the project's unit tests (SQLite fallback needs no services; set the PostgreSQL admin URL to also run the fresh-database test) and a Streamlit render smoke test. Exercise a new-chat reset more than once, switching recommendation groups, changing the data table, opening document details, changing and reverting the API key, and loading the voice panel. Verify the desktop chat console has readable contrast for both message roles, while a narrow viewport leaves only the conversation and input as the primary UI. In a fresh browser tab confirm there is no `NotFoundError: ... removeChild ...` console error and that the mobile layout has no horizontal page overflow. Before deployment, validate the Compose file and confirm a fresh container pair initializes the schema, extension, seed data, and documents without manual steps.

For implementation details and the recommended sample schema, read [references/manufacturing-cockpit.md](references/manufacturing-cockpit.md).

## Version routing

The paired implementation is **스킬2 / `skill-2-react`**, a React + TypeScript frontend with FastAPI. A V2 request does not authorize replacing the Streamlit app. The Imjingang reference keeps V1 at root (`app.py`) and V2 under `v2/`. Use the company repository supplied by the user; do not depend on a previous machine’s absolute paths.

Imjingang reference: `https://github.com/superpjh-stack/Limjingang_Agent_cockpit`. Its root Streamlit app is the V1 implementation. Food thresholds, CCP designation, customer records, and model predictions remain samples unless an approved source is supplied.
