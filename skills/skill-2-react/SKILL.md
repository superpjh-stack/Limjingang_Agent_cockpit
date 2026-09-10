---
name: skill-2-react
description: "스킬2 — React·TypeScript와 FastAPI로 제조 AI Agent Cockpit을 만들거나 Streamlit 시제품을 별도 웹앱 V2로 확장합니다. LOT·품질·지식 근거가 연결된 전문 업무용 화면에 사용합니다."
metadata:
  short-description: 스킬2 · React 제조 AI 에이전트
---

# 스킬2 · React Agent Cockpit

Build a working manufacturing application with React + TypeScript and a FastAPI service. This is the second technology track paired with **스킬1 / `skill-1-streamlit`**. Use the user's company, processes, and records; the stack is reusable, company-specific content is not.

## Version and architecture

- Keep an existing Streamlit app runnable. Put V2 under `v2/` when extending the paired reference. Use separate ports, Compose project names, and demo database paths; do not import or launch Streamlit in the V2 runtime.
- Prefer React + TypeScript + Vite for the client, FastAPI for API and production static serving, and the existing repository/service layer for business logic. PostgreSQL + pgvector is the configured backend; SQLite is an explicitly labeled local demo fallback.
- Preserve existing model and database definitions unless the requested feature needs a change. HTTP endpoints must validate IDs and paging, whitelist table names, and return clear failures. Do not expose DB connection strings, provider keys, or client-selectable SQL.
- Read [architecture.md](references/architecture.md) for API contracts, local demo behavior, voice, and deployment mechanics.

## Product and design

Build an operational workspace, not a landing page. The Imjingang example uses a compact navigation rail, restrained green/graphite colors, an open main work area, and a contextual assistant. Adapt those choices to the company's brand rather than making them a universal visual template.

- Put actionable records before long introductions: operations overview → flagged LOT → detail/lineage → supporting measurements/documents → assistant question.
- Give operations, LOT, quality/shipment, documents, rules, and source data distinct views when their content warrants it. Every visible navigation item and filter must work. A refresh refetches data; CSV exports the actual selected rows.
- Use a coherent spacing/type/border system and readable Korean. Reserve strong colors for selected navigation and exception states. Status is text plus color, not color alone. Never invent charts or time-series points to decorate a dashboard.
- Keep large datasets in horizontally scrollable tables; use a detail dialog for lineage and original records. Use semantic buttons, labels and native dialogs or the installed accessible component primitives. Preserve keyboard focus, Escape closing, loading/empty/error states, and reduced-motion behavior.
- At narrow widths, collapse navigation and open the assistant as a full-height panel. Keep task data reachable. Test long Korean names and zoom; avoid page-wide horizontal overflow.

## Evidence and AI

- Reuse a bounded, read-only tool registry and server-side Responses loop. Retain retrieved evidence across all rounds. For missing records say “미확인”; missing prediction is not zero risk. Trace upstream CCP records before summarizing shipment evidence.
- Keep document procedures, process DB records, and rules distinct. Document status/revision/owner and record timestamps must remain visible. Sample rules are not approved food-safety limits or production control logic.
- A no-key demo can provide deterministic record lookup and document search. Label it **데모 조회**, state supported scope, and return actual retrieved records. Never call fixed templates AI analysis or pretend they perform arbitrary reasoning.
- Keep provider keys on the server. If server-funded AI is externally reachable, gate paid endpoints with the deployment's access mechanism. In the reference, a server access code protects chat/voice, remains only in frontend memory, and is never an OpenAI key. Prefer the user's existing authentication when present.
- All typed, suggested, contextual and transcribed questions use one submission function. Prevent duplicate submission. Reset clears server response chaining as well as visible history; ignore late results after reset. Browser clients must not choose arbitrary provider response IDs.
- Answer in concise Korean, lead with the finding and finish with `근거:`. Detailed source excerpts belong in a disclosure/detail surface. Changing source documents must not silently alter previous answer evidence.

## Deliver and validate

- Keep a lockfile and a production build. Serve the built client and `/api` from the same origin; proxy `/api` in local Vite development. Copy only runtime code/assets into a multistage image. Secrets and local caches stay outside source and images.
- Verify meaningful invariants: invalid table/LOT handling, upstream CCP and missing data, document/rule linkage, deterministic demo evidence, paid-endpoint authentication, no key leakage, production static entrypoint, and working UI controls. Test existing V1 when shared code changes.
- When deployment is requested, inspect existing services/ports first. Build and deploy an immutable source revision, validate Compose, confirm container health and the public application data load. Do not replace V1 just to make V2 available. See the Hostinger-specific reference note before assuming its GUI builds images.
- Deliver the usable V2 and identify remaining external setup truthfully (e.g. absent AI credentials). An installed reusable skill, a deployable source tree, a running local preview and a production deployment are distinct outcomes; report only those completed.

Reference source: `https://github.com/superpjh-stack/Limjingang_Agent_cockpit` (V2: `v2/`, shared repository: `imjingang_agent/`). If unavailable, implement the architecture without relying on local paths from earlier sessions.
