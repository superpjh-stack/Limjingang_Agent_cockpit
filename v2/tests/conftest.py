"""Unit tests never send credentials or prompts to a live model."""
import pytest
from openai.resources.responses.responses import Responses

@pytest.fixture(autouse=True)
def no_live_responses(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError('Use a fake model client in unit tests')
    monkeypatch.setattr(Responses, 'create', blocked)
