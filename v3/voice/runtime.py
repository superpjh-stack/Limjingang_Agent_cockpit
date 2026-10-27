from __future__ import annotations

import os

from bedrock_agentcore import BedrockAgentCoreApp

from v3.aws import AgentCoreClient
from v3.voice.agent import VoiceAgent
from v3.voice.polly import PollyVoice
from v3.voice.session import VoiceSession
from v3.voice.transcribe import KoreanTranscriber


app = BedrockAgentCoreApp()


@app.websocket
async def websocket_handler(websocket, context):
    await websocket.accept()
    region = os.getenv("AWS_REGION", "ap-northeast-2")
    text_runtime_arn = os.environ["V3_AGENTCORE_RUNTIME_ARN"]
    text_qualifier = os.getenv("V3_AGENTCORE_QUALIFIER", "ImjingangV3Live")
    session = VoiceSession(
        KoreanTranscriber(region),
        VoiceAgent(AgentCoreClient(text_runtime_arn, region, 120, text_qualifier)),
        PollyVoice(region),
        websocket.send_json,
    )
    try:
        while await session.handle(await websocket.receive_json()):
            pass
    except Exception:
        await session.emit("error", code="VOICE_RUNTIME_ERROR", message="실시간 음성 연결에 문제가 생겼습니다.")
    finally:
        await session.close()
        await websocket.close()


if __name__ == "__main__":
    app.run(log_level="info")
