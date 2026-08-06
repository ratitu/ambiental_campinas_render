from fastapi.testclient import TestClient

import main


def make_client():
    return TestClient(main.app)


def test_healthz_ok():
    assert make_client().get("/healthz").status_code == 200


def test_healthz_503_when_gee_not_ready(monkeypatch):
    monkeypatch.setattr(main, "_gee_ready", False)
    r = make_client().get("/healthz")
    assert r.status_code == 503


def test_tile_returns_url():
    r = make_client().get("/tile", params={"asset_id": "projects/x/assets/y", "palette": "000000"})
    assert r.status_code == 200
    assert r.json()["url"].startswith("https://fake-ee.test")


def test_tile_point_flag():
    r = make_client().get("/tile", params={"asset_id": "a", "palette": "fff", "is_point": "true"})
    assert r.status_code == 200
    assert "url" in r.json()


def test_tile_500_on_gee_error(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("ee exploded")
    monkeypatch.setattr(main, "generate_tile", boom)
    r = make_client().get("/tile", params={"asset_id": "a", "palette": "fff"})
    assert r.status_code == 500
    assert "ee exploded" in r.json()["detail"]


def test_tile_503_when_gee_not_ready(monkeypatch):
    monkeypatch.setattr(main, "_gee_ready", False)
    r = make_client().get("/tile", params={"asset_id": "a", "palette": "fff"})
    assert r.status_code == 503


def test_info_returns_properties():
    r = make_client().get("/info", params={"asset_id": "a", "lat": -22.9, "lon": -47.06})
    assert r.status_code == 200
    assert r.json()["properties"]["nome"] == "APA"


def test_info_empty_returns_empty_properties(monkeypatch):
    fake_fc = main.ee.FeatureCollection

    def empty_fc(asset_id):
        fc = fake_fc(asset_id)
        fc.empty = True
        return fc
    monkeypatch.setattr(main.ee, "FeatureCollection", empty_fc)
    r = make_client().get("/info", params={"asset_id": "a", "lat": -22.9, "lon": -47.06})
    assert r.status_code == 200
    assert r.json()["properties"] == {}


def test_rate_limit():
    client = make_client()
    params = {"asset_id": "a", "palette": "fff"}
    statuses = [client.get("/tile", params=params).status_code for _ in range(61)]
    assert statuses.count(429) >= 1
    assert statuses.count(200) >= 1
