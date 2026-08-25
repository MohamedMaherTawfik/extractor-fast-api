import asyncio

import httpx

from backend.main import app


async def request_health() -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.get("/health")


def test_health_endpoint() -> None:
    response = asyncio.run(request_health())

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "ok",
        "environment": "local",
        "version": "0.1.0",
    }
