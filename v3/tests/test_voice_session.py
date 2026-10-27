import asyncio
import base64

from v3.voice.session import VoiceSession


class FakeTranscriber:
    callback = None
    async def run(self, audio, callback):
        self.callback = callback
        while await audio.get() is not None:
            pass


class FakeAgent:
    calls = []
    async def ask(self, question, session_id, lot_id):
        self.calls.append((question, session_id, lot_id))
        return {"text": "출하 승인 대기입니다.", "data_tools": ["get_shipment_readiness"], "sources": []}


class FakeSpeaker:
    async def stream(self, text):
        yield b"first"
        yield b"second"


def run(coro):
    return asyncio.run(coro)


def sender(items):
    async def send(value):
        items.append(value)
    return send


def test_partial_does_not_call_agent_and_final_is_deduplicated():
    async def scenario():
        sent = []
        transcriber, agent = FakeTranscriber(), FakeAgent()
        agent.calls = []
        session = VoiceSession(transcriber, agent, FakeSpeaker(), sender(sent))
        await session.handle({"type": "session.start", "session_id": "session-1234567890", "lot_id": "PACK-260903-001"})
        await asyncio.sleep(0)
        await session.handle({"type": "audio.chunk", "utterance_id": "u-1", "sequence": 0, "audio": base64.b64encode(b"pcm").decode()})
        await transcriber.callback("포장 로트", False)
        assert agent.calls == []
        await transcriber.callback("포장 로트 출하 확인", True)
        await transcriber.callback("포장 로트 출하 확인", True)
        await session.response_task
        assert len(agent.calls) == 1
        assert any(item["type"] == "answer.complete" for item in sent)
        await session.close()
    run(scenario())


def test_audio_sequence_is_monotonic_and_cancel_drops_late_audio():
    async def scenario():
        sent = []
        transcriber = FakeTranscriber()
        session = VoiceSession(transcriber, FakeAgent(), FakeSpeaker(), sender(sent))
        await session.handle({"type": "session.start", "session_id": "session-1234567890"})
        await asyncio.sleep(0)
        chunk = base64.b64encode(b"pcm").decode()
        await session.handle({"type": "audio.chunk", "utterance_id": "u-1", "sequence": 2, "audio": chunk})
        await session.handle({"type": "audio.chunk", "utterance_id": "u-1", "sequence": 1, "audio": chunk})
        assert any(item.get("code") == "AUDIO_SEQUENCE" for item in sent)
        await session.close()
    run(scenario())
