from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from imjingang_agent import ImjingangRepository
from v3.api import create_app
from v3.config import V3Settings


@pytest.fixture
def repository(tmp_path: Path):
    return ImjingangRepository(tmp_path / "v3.db")


@pytest.fixture
def client(repository):
    app = create_app(repository, V3Settings())
    with TestClient(app) as test_client:
        yield test_client
