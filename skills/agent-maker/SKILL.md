---
name: agent-maker
description: Build or extend a Korean manufacturing AI Agent with React, TypeScript, FastAPI, evidence-backed chat, read-only process APIs, knowledge documents, and Realtime voice tool calling. Use for factory copilots that connect LOT, quality, equipment, sensor history, or CCP data; do not use for automatic equipment control or generic chatbots without manufacturing evidence.
---

# Agent Maker

Build an operational manufacturing assistant that answers in Korean from traceable company evidence. Preserve an existing stack when extending a project; for a new web app, prefer React + TypeScript + Vite with a FastAPI server.

## Product shape

- Keep the assistant central, with knowledge/data navigation and a compact recommendation panel around it.
- Make typed, suggested, contextual, and transcribed questions use one submission path.
- Show the submitted question immediately above the composer, then place the answer beneath it and scroll to the newest exchange.
- Separate process-data recommendations from general manufacturing questions. Only label a recommendation as process data when a connected tool can answer it.
- Keep mobile access, keyboard focus, loading, empty, error, cancellation, and reduced-motion behavior usable.

## Evidence and safety

- Use bounded, server-owned, read-only tools. Never expose provider keys, data-platform keys, database URLs, or arbitrary SQL to the browser.
- Treat LOT records, sensor values, documents, and rules as distinct evidence types. Preserve timestamps, units, source names, and KST semantics.
- For missing company data say `미확인`; never convert missing measurements into a normal result.
- Do not automatically change process conditions, dispose product, approve shipment, place orders, or control equipment.
- Clearly label sample data and unapproved procedures. Do not present samples as live operations or approved HACCP limits.
- Answer with the finding first and finish with `근거:`. Put verbose records in a disclosure panel.

## Implementation workflow

1. Inspect the repository, current UI, server boundary, data models, tests, environment-variable names, and running ports.
2. Map every requested question to a real evidence source or tool before exposing it as a recommendation.
3. Keep external integrations behind FastAPI. Return visible, human-readable failures without blocking unrelated UI.
4. For a process data platform, read [references/data-platform.md](references/data-platform.md) before implementing the client or function schemas.
5. For live voice with API lookup, read [references/realtime-voice.md](references/realtime-voice.md) before changing the Realtime session or browser event loop.
6. Build the client, run focused server tests, verify secrets do not enter responses or bundles, and exercise at least one real read-only call when credentials are configured.
7. When starting or deploying services, inspect existing listeners first and report only the environment actually verified.

## Delivery boundaries

- Keep production static serving and local Vite proxy behavior distinct.
- Load secrets from server environment variables; keep `.env` files and local databases out of distributable assets.
- Use a deployment access gate for server-funded AI. Local no-token behavior must be explicitly restricted to loopback hosts.
- Report external setup honestly: source completion, local preview, configured credentials, and production deployment are separate outcomes.
