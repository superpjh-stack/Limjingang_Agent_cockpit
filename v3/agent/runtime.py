from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException

from imjingang_agent.data_hub import create_repository
from v3.agent.tools import ReadOnlyTools
from v3.backends.demo import DemoBackend
from v3.config import V3Settings
from v3.contracts import AgentRequest


app = FastAPI(title="임진강김치 AgentCore Runtime", version="3.0.0")
settings = V3Settings.from_env()
repository = create_repository(settings.sqlite_path)
tools = ReadOnlyTools(repository)


@app.get("/ping")
def ping() -> dict[str, str]:
    return {"status": "Healthy"}


@app.post("/invocations")
def invoke(request: AgentRequest) -> dict[str, Any]:
    """Runtime contract. Bedrock orchestration is enabled only with an explicit model configuration."""
    model_id = os.getenv("V3_BEDROCK_MODEL_ID", "")
    if not model_id:
        return DemoBackend(repository, settings.aws_region).ask(request).model_dump()
    try:
        import boto3
    except ImportError as exc:
        raise HTTPException(503, "Bedrock 호출에 boto3가 필요합니다.") from exc
    # Converse is intentionally bounded to text here; Gateway-hosted tools remain the governed production path.
    client = boto3.client("bedrock-runtime", region_name=settings.aws_region)
    tool_context = DemoBackend(repository, settings.aws_region).ask(request)
    prompt = request.question + "\n조회 근거:\n" + tool_context.model_dump_json()
    try:
        result = client.converse(
            modelId=model_id,
            system=[{"text": __import__("v3.agent.prompts", fromlist=["AGENT_INSTRUCTIONS"]).AGENT_INSTRUCTIONS}],
            messages=[{"role": "user", "content": [{"text": prompt[:20000]}]}],
            inferenceConfig={"maxTokens": 1200, "temperature": 0.1},
        )
        text = "".join(block.get("text", "") for block in result["output"]["message"]["content"])
    except Exception as exc:
        raise HTTPException(502, "Bedrock 모델 응답을 받지 못했습니다.") from exc
    payload = tool_context.model_dump()
    payload.update({"text": text, "mode": "agentcore", "demo_data": True, "model": model_id})
    return payload
