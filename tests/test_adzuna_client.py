import pytest

from app.integrations.adzuna_client import AdzunaClient
from app.config import Settings, AppConfig


class DummyResp:
    def __init__(self):
        self.called_params = None

    def raise_for_status(self):
        pass

    def json(self):
        return {"results": []}


class DummyClient:
    def __init__(self, resp: DummyResp):
        self.resp = resp

    async def get(self, url, params):
        self.resp.called_params = params
        return self.resp

    async def aclose(self):
        pass


@pytest.mark.asyncio
async def test_search_passes_salary_min(monkeypatch):
    settings = Settings(ADZUNA_APP_ID="id", ADZUNA_APP_KEY="key")
    cfg = AppConfig()
    client = AdzunaClient(settings, cfg)
    resp = DummyResp()
    dummy = DummyClient(resp)
    monkeypatch.setattr(client, "_client_or_create", lambda: dummy)

    await client.search("gb", 1, 10, salary_min=1234)

    assert resp.called_params["salary_min"] == 1234


class DupResp(DummyResp):
    def json(self):
        return {
            "results": [
                {"title": "t1", "redirect_url": "u1"},
                {"title": "t2", "redirect_url": "u1"},
            ]
        }


@pytest.mark.asyncio
async def test_search_dedup(monkeypatch):
    settings = Settings(ADZUNA_APP_ID="id", ADZUNA_APP_KEY="key")
    cfg = AppConfig()
    client = AdzunaClient(settings, cfg)
    resp = DupResp()
    dummy = DummyClient(resp)
    monkeypatch.setattr(client, "_client_or_create", lambda: dummy)

    data = await client.search("gb", 1, 10)
    assert len(data) == 1


@pytest.mark.asyncio
async def test_search_invalid_country():
    settings = Settings(ADZUNA_APP_ID="id", ADZUNA_APP_KEY="key")
    cfg = AppConfig()
    client = AdzunaClient(settings, cfg)
    with pytest.raises(ValueError):
        await client.search("xx", 1, 10)


@pytest.mark.asyncio
async def test_search_requires_credentials():
    settings = Settings(ADZUNA_APP_ID="", ADZUNA_APP_KEY="")
    cfg = AppConfig()
    client = AdzunaClient(settings, cfg)
    with pytest.raises(ValueError):
        await client.search("gb", 1, 10)
