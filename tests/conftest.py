from collections.abc import AsyncGenerator

import pytest
from app.main import app
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
