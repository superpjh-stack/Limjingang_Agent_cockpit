import base64

import pytest
from pydantic import ValidationError

from v3.voice.contracts import AudioChunk, SessionStart, parse_client_event


def test_voice_contract_parses_approved_events():
    start = parse_client_event({"type": "session.start", "session_id": "session-1234567890", "lot_id": "PACK-260903-001"})
    assert isinstance(start, SessionStart)
    chunk = parse_client_event({"type": "audio.chunk", "utterance_id": "u-1", "sequence": 0, "audio": base64.b64encode(b"pcm").decode()})
    assert isinstance(chunk, AudioChunk)


@pytest.mark.parametrize("payload", [
    {"type": "unknown"},
    {"type": "audio.chunk", "utterance_id": "u-1", "sequence": -1, "audio": "cGNt"},
    {"type": "audio.chunk", "utterance_id": "u-1", "sequence": 0, "audio": "not-base64"},
    {"type": "session.end", "secret": "must-not-pass"},
])
def test_voice_contract_rejects_unknown_or_invalid_payload(payload):
    with pytest.raises(ValidationError):
        parse_client_event(payload)
