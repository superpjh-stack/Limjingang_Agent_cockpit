from __future__ import annotations

import os
import re
import secrets
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from imjingang_agent.data_hub import PostgresRepository, create_repository
from imjingang_agent.ui_helpers import lot_snapshot
from v3 import __version__
from v3.aws import AgentCoreClient, AgentCoreError
from v3.backends import AgentCoreBackend, DemoBackend
from v3.config import V3Settings
from v3.contracts import AgentRequest, ChatRequest, VoiceSessionRequest, VoiceSessionResponse, utc_stamp
from v3.aws.voice_session import VoiceSessionError, VoiceSessionSigner
from v3.observability import audit


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
LOT_PATTERN = re.compile(r"(?:RAW|SORT|SALT|MIX|FERM|PACK)-\d{6}-\d{3}")


class _VoiceTicketLimiter:
    def __init__(self, limit: int = 6, window: int = 60) -> None:
        self.limit, self.window = limit, window
        self.requests: dict[str, deque[float]] = defaultdict(deque)
        self.lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self.lock:
            values = self.requests[key]
            while values and values[0] <= now - self.window:
                values.popleft()
            if len(values) >= self.limit:
                return False
            values.append(now)
            return True


def _valid_voice_origin(request: Request) -> bool:
    origin = request.headers.get("origin")
    if not origin:
        return True
    from urllib.parse import urlparse
    parsed = urlparse(origin)
    host = (parsed.hostname or "").lower()
    request_host = request.headers.get("x-forwarded-host", request.url.hostname or "").split(":", 1)[0].lower()
    return parsed.scheme == "https" and (host == request_host or host.endswith(".cloudfront.net"))


def _repository(settings: V3Settings):
    return create_repository(ROOT / settings.sqlite_path)


def create_app(repository: Any | None = None, settings: V3Settings | None = None, backend: Any | None = None, voice_signer: Any | None = None) -> FastAPI:
    settings = settings or V3Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.repo = repository or _repository(settings)
        if backend is not None:
            app.state.agent = backend
        elif settings.backend == "agentcore":
            app.state.agent = AgentCoreBackend(
                AgentCoreClient(settings.runtime_arn, settings.aws_region, settings.request_timeout, settings.runtime_qualifier),
                settings.aws_region,
                settings.model_id,
            )
        else:
            app.state.agent = DemoBackend(app.state.repo, settings.aws_region)
        app.state.voice_signer = voice_signer
        if settings.voice_enabled and app.state.voice_signer is None:
            app.state.voice_signer = VoiceSessionSigner(
                settings.voice_runtime_arn,
                settings.aws_region,
                settings.voice_url_ttl_seconds,
            )
        yield

    app = FastAPI(title="임진강김치 AWS AgentCore V3", version=__version__, lifespan=lifespan)
    app.state.settings = settings
    app.state.voice_ticket_limiter = _VoiceTicketLimiter()

    @app.get("/api/health")
    def health(request: Request):
        request.app.state.repo.dashboard()
        return {
            "status": "ok",
            "version": __version__,
            "backend": settings.backend,
            "region": settings.aws_region,
            "database": "PostgreSQL + pgvector" if isinstance(request.app.state.repo, PostgresRepository) else "SQLite",
        }

    @app.get("/api/workspace")
    def workspace(request: Request):
        repo = request.app.state.repo
        return {
            "kpi": repo.dashboard(),
            "lots": repo.all_lots(),
            "fermentation": repo.fermentation_status(None),
            "ccp": repo.ccp_deviations(None),
            "inventory": repo.inventory_status(None, False),
            "shipments": repo.shipment_readiness(None),
            "rules": repo.get_rules(),
            "tables": repo.table_inventory(),
            "questions": {
                "공정데이터": ["포장 LOT의 공정 계보와 출하 확인사항을 알려줘", "현재 CCP 기록을 확인해줘", "재고 부족 품목을 알려줘"],
                "문서규칙": ["금속검출 기준 문서를 찾아줘", "발효 점검 절차를 알려줘", "출하 전 확인 규칙을 알려줘"],
            },
            "meta": {
                "company": "임진강김치",
                "version": __version__,
                "agent_platform": "Amazon Bedrock AgentCore" if settings.backend == "agentcore" else "로컬 결정형 데모",
                "backend": settings.backend,
                "region": settings.aws_region,
                "model": settings.model_id or "deterministic-demo",
                "database": "PostgreSQL + pgvector" if isinstance(repo, PostgresRepository) else "SQLite",
                "demo_data": True,
                "as_of": "2026-09-04 13:10",
                "retrieved_at": utc_stamp(),
                "voice_enabled": settings.voice_enabled,
            },
        }

    @app.post("/api/voice/session", response_model=VoiceSessionResponse)
    def voice_session(body: VoiceSessionRequest, request: Request):
        if not settings.voice_enabled:
            raise HTTPException(404, "실시간 음성 기능이 비활성화되어 있습니다.")
        if not _valid_voice_origin(request):
            raise HTTPException(403, "허용되지 않은 음성 세션 요청입니다.")
        client_ip = request.client.host if request.client else "unknown"
        if not request.app.state.voice_ticket_limiter.allow(client_ip):
            raise HTTPException(429, "음성 세션 요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.")
        if body.lot_id and not request.app.state.repo.lot_trace(body.lot_id):
            raise HTTPException(404, "LOT를 찾을 수 없습니다.")
        session_id = secrets.token_hex(24)
        try:
            url = request.app.state.voice_signer.create_url(session_id)
        except VoiceSessionError as exc:
            audit("voice_session_failed", request_id=secrets.token_hex(12), backend=settings.backend, error_type="voice_session")
            raise HTTPException(503, str(exc)) from exc
        audit("voice_session_created", request_id=secrets.token_hex(12), session_id=session_id, backend=settings.backend, ok=True)
        return VoiceSessionResponse(session_id=session_id, url=url, expires_in=settings.voice_url_ttl_seconds)

    @app.get("/api/lots/{lot_id}")
    def lot(lot_id: str, request: Request):
        result = lot_snapshot(request.app.state.repo, lot_id)
        if not result["lot"]:
            raise HTTPException(404, "LOT를 찾을 수 없습니다.")
        return result

    @app.get("/api/documents")
    def documents(request: Request, q: str = Query(default="", max_length=200)):
        repo = request.app.state.repo
        matches = {item["document_id"] for item in repo.search_knowledge(q)} if q.strip() else None
        return [{key: value for key, value in item.items() if key not in {"embedding", "embedding_model"}}
                for item in repo.knowledge_documents() if matches is None or item["document_id"] in matches]

    @app.get("/api/tables/{table}")
    def table(table: str, request: Request, limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0)):
        try:
            return request.app.state.repo.table_records(table, limit, offset)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/api/chat/reset")
    def reset(response: Response):
        response.delete_cookie("imj_v3_session", path="/api")
        return {"status": "ok"}

    @app.post("/api/chat")
    def chat(body: ChatRequest, request: Request, response: Response):
        question = body.question.strip()
        explicit = LOT_PATTERN.findall(question.upper())
        if explicit and (len(set(explicit)) > 1 or (body.lot_id and explicit[0] != body.lot_id)):
            raise HTTPException(422, "질문의 LOT와 선택한 LOT를 일치시켜 주세요. 한 번에 하나의 LOT를 확인합니다.")
        lot_id = body.lot_id or (explicit[0] if explicit else None)
        if lot_id and not request.app.state.repo.lot_trace(lot_id):
            raise HTTPException(404, "LOT를 찾을 수 없습니다.")
        session_id = body.session_id or request.cookies.get("imj_v3_session") or secrets.token_urlsafe(32)
        agent_request = AgentRequest(question=question, session_id=session_id, lot_id=lot_id, user_context={"role": "operator"})
        request_id = request.headers.get("x-request-id") or secrets.token_hex(12)
        try:
            result = request.app.state.agent.ask(agent_request)
        except AgentCoreError as exc:
            audit("chat_failed", request_id=request_id, session_id=session_id, backend=settings.backend, error_type="agentcore")
            raise HTTPException(503, str(exc)) from exc
        except Exception as exc:
            audit("chat_failed", request_id=request_id, session_id=session_id, backend=settings.backend, error_type=exc.__class__.__name__)
            raise HTTPException(502, "Agent 응답을 검증하지 못했습니다.") from exc
        response.set_cookie("imj_v3_session", session_id, httponly=True, samesite="lax", secure=os.getenv("V3_SECURE_COOKIE", "0") == "1", path="/api", max_age=86400)
        audit("chat_completed", request_id=request_id, session_id=session_id, backend=settings.backend, region=settings.aws_region, model=result.model, ok=True)
        return result.model_dump()

    dist = ROOT / "v3" / "web" / "dist"
    if dist.is_dir():
        assets = dist / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=assets), name="v3-assets")

        @app.get("/{path:path}")
        def frontend(path: str):
            if path.startswith("api/"):
                raise HTTPException(404)
            return FileResponse(dist / "index.html")

    return app


app = create_app()
