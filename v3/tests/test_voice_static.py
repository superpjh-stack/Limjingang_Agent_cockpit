from pathlib import Path

from fastapi.testclient import TestClient

from v3.api import create_app
from v3.config import V3Settings


def test_pcm_audio_worklet_is_served_as_javascript(repository):
    dist = Path(__file__).parents[1] / "web" / "dist"
    if not (dist / "pcm-processor.js").is_file():
        return
    with TestClient(create_app(repository, V3Settings())) as client:
        response = client.get("/pcm-processor.js")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/javascript")
        assert "registerProcessor('pcm-processor'" in response.text
