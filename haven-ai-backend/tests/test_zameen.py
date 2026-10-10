"""
Zameen.com listings: off / MOCK / live modes, field mapping, filters, caching,
and that a Zameen failure never breaks the Properties page.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import zameen


@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    zameen.clear_cache()
    monkeypatch.setattr(zameen.settings, "ZAMEEN_API_KEY", "secret-key")
    yield
    zameen.clear_cache()


@pytest.fixture
def client():
    return TestClient(app)


def use(monkeypatch, url):
    monkeypatch.setattr(zameen.settings, "ZAMEEN_API_URL", url)


def test_off_returns_nothing(client, monkeypatch):
    use(monkeypatch, "")
    body = client.get("/api/properties/external").json()
    assert body["mode"] == "off" and body["listings"] == [] and body["error"] is None


def test_mock_listings_are_labelled_and_filterable(client, monkeypatch):
    use(monkeypatch, "MOCK")
    all_ = client.get("/api/properties/external").json()["listings"]
    assert all_ and all(l["title"].startswith("[Sample]") and l["source"] == "zameen" for l in all_)
    assert all(l["id"].startswith("zameen-") for l in all_)

    rent = client.get("/api/properties/external", params={"purpose": "for-rent"}).json()["listings"]
    assert rent and all(l["status"] == "for-rent" for l in rent)
    lahore = client.get("/api/properties/external", params={"city": "lahore"}).json()["listings"]
    assert lahore and all(l["city"] == "Lahore" for l in lahore)
    four_plus = client.get("/api/properties/external", params={"beds": 4}).json()["listings"]
    assert four_plus and all(l["beds"] >= 4 for l in four_plus)


def test_normalize_accepts_common_field_names():
    item = zameen.normalize({
        "externalID": 77, "title": "House", "purpose": "for-rent", "category": "House",
        "price": "120,000", "location": {"name": "Gulberg", "city": "Lahore"},
        "bedrooms": "3", "bathrooms": 2, "area": 5, "area_unit": "Marla",
        "coverPhoto": {"url": "https://img/x.jpg"}, "url": "https://www.zameen.com/Property/x.html",
        "agency": {"name": "ABC Estate"},
    })
    assert item["id"] == "zameen-77" and item["status"] == "for-rent" and item["type"] == "house"
    assert item["price"] == 120000 and item["beds"] == 3 and item["baths"] == 2
    assert item["area"] == "5 Marla" and item["location"] == "Gulberg" and item["city"] == "Lahore"
    assert item["img"] == "https://img/x.jpg" and item["agency"] == "ABC Estate"
    assert zameen.normalize({"title": "no id"}) is None


class FakeResponse:
    def __init__(self, body, status=200):
        self._body, self.status_code = body, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._body


def test_live_sends_the_key_from_the_server_and_caches(client, monkeypatch):
    use(monkeypatch, "https://api.example.test/v1/")
    calls = []

    def fake_get(url, params, headers, timeout):
        calls.append((url, params, headers))
        return FakeResponse({"hits": [{"id": 1, "title": "Real one", "purpose": "for-sale", "price": 5}]})

    monkeypatch.setattr(zameen.httpx, "get", fake_get)
    first = client.get("/api/properties/external", params={"city": ""}).json()
    second = client.get("/api/properties/external", params={"city": ""}).json()
    assert first["mode"] == "live" and [l["title"] for l in first["listings"]] == ["Real one"]
    assert second == first
    assert len(calls) == 1                                   # cached
    url, _, headers = calls[0]
    assert url == "https://api.example.test/v1/listings"
    assert headers["Authorization"] == "Bearer secret-key"
    assert "secret-key" not in str(first)                    # never sent to the browser


def test_zameen_failure_is_a_note_not_an_error(client, monkeypatch):
    use(monkeypatch, "https://api.example.test")
    monkeypatch.setattr(zameen.httpx, "get", lambda *a, **k: FakeResponse({}, status=500))
    r = client.get("/api/properties/external")
    assert r.status_code == 200
    assert r.json()["listings"] == [] and "not available" in r.json()["error"]


def test_bad_query_is_rejected(client, monkeypatch):
    use(monkeypatch, "MOCK")
    assert client.get("/api/properties/external", params={"purpose": "steal"}).status_code == 422
    assert client.get("/api/properties/external", params={"min_price": -1}).status_code == 422
