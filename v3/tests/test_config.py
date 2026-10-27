import pytest

from v3.config import ConfigurationError, V3Settings


def test_demo_is_the_safe_default(monkeypatch):
    for name in ["V3_AGENT_BACKEND", "AWS_REGION", "AWS_DEFAULT_REGION", "V3_BEDROCK_MODEL_ID", "V3_AGENTCORE_RUNTIME_ARN", "V3_AGENTCORE_GATEWAY_URL"]:
        monkeypatch.delenv(name, raising=False)
    settings = V3Settings.from_env()
    assert settings.backend == "demo"
    assert settings.aws_region == "ap-northeast-2"


def test_agentcore_requires_runtime_gateway_and_model(monkeypatch):
    monkeypatch.setenv("V3_AGENT_BACKEND", "agentcore")
    monkeypatch.delenv("V3_BEDROCK_MODEL_ID", raising=False)
    monkeypatch.delenv("V3_AGENTCORE_RUNTIME_ARN", raising=False)
    monkeypatch.delenv("V3_AGENTCORE_GATEWAY_URL", raising=False)
    with pytest.raises(ConfigurationError, match="설정 누락"):
        V3Settings.from_env()


def test_agentcore_settings_are_valid():
    V3Settings(backend="agentcore", model_id="model", runtime_arn="arn:aws:test", gateway_url="https://example.invalid").validate()


def test_voice_requires_runtime_and_short_url_expiry():
    with pytest.raises(ConfigurationError, match="V3_VOICE_RUNTIME_ARN"):
        V3Settings(voice_enabled=True).validate()
    with pytest.raises(ConfigurationError, match="30~300"):
        V3Settings(voice_url_ttl_seconds=301).validate()
