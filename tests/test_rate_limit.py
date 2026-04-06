import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_rate_limit_exceeded():
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Free tier = 20 req/min
        for _ in range(20):
            r = await client.get("/api/v1/users/me")
        
        # 21st request should be 429
        response = await client.get("/api/v1/users/me")
        assert response.status_code == 429
        assert response.json()["code"] == "RATE_LIMIT_EXCEEDED"
        assert "X-RateLimit-Remaining" in response.headers