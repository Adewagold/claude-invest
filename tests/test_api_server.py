import pytest
from httpx import AsyncClient, ASGITransport
from claude_invest.modules.api_server import create_app
from claude_invest.modules.db import Database


@pytest.fixture
def app(tmp_db_path):
    db = Database(tmp_db_path)
    db.initialize()
    # Seed some test data
    db.insert_trade({
        "symbol": "AAPL", "side": "buy", "qty": 5, "price": 150.0,
        "order_id": "t1", "trade_type": "swing", "status": "filled",
    })
    db.insert_decision({
        "ticker": "AAPL", "action": "buy",
        "reasoning": "Strong momentum", "signals_snapshot": "{}",
    })
    db.insert_portfolio_snapshot({
        "total_value": 5200, "cash": 4100, "positions_value": 1100, "daily_pnl": 50,
    })
    db.insert_discovery({
        "ticker": "NVDA", "volume_score": 3.0, "news_score": 0.7,
        "sentiment": 0.6, "action_taken": "flagged",
    })
    db.close()
    return create_app(tmp_db_path)


@pytest.mark.asyncio
async def test_get_trades(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/trades")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["symbol"] == "AAPL"


@pytest.mark.asyncio
async def test_get_decisions(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/decisions")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["action"] == "buy"


@pytest.mark.asyncio
async def test_get_portfolio(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/portfolio")
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["total_value"] == 5200


@pytest.mark.asyncio
async def test_get_discovery(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/discovery")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["ticker"] == "NVDA"


@pytest.mark.asyncio
async def test_get_config(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/config")
    assert resp.status_code == 200
    data = resp.json()
    assert "mode" in data
    assert "capital" in data
