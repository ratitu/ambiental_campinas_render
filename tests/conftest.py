import json
import os
import sys
import types

import pytest

os.environ["EE_CREDENTIALS"] = json.dumps({
    "client_email": "test@example.com",
    "private_key": "-----BEGIN PRIVATE KEY-----\\nAAAA\\n-----END PRIVATE KEY-----",
    "project_id": "test-project",
})


class FakeTileFetcher:
    url_format = "https://fake-ee.test/tile?z={z}&x={x}&y={y}"


class FakeImage:
    def paint(self, *args, **kwargs):
        return self

    def getMapId(self, vis_params=None):
        return {"mapid": "fake", "token": "t", "tile_fetcher": FakeTileFetcher()}


class FakeFeature:
    def __init__(self, info):
        self._info = info

    def getInfo(self):
        return self._info


class FakeFeatureCollection:
    def __init__(self, asset_id):
        self.asset_id = asset_id
        self.empty = False

    def map(self, fn):
        return self

    def filterBounds(self, geom):
        return self

    def first(self):
        if self.empty:
            return FakeFeature(None)
        return FakeFeature({"properties": {"nome": "APA", "area_ha": 123.4}})


class FakeGeometry:
    def __init__(self, coords=None):
        self.coords = coords

    def buffer(self, meters):
        return self


fake_ee = types.SimpleNamespace(
    ServiceAccountCredentials=lambda *a, **k: types.SimpleNamespace(),
    Initialize=lambda *a, **k: None,
    FeatureCollection=FakeFeatureCollection,
    Image=lambda: FakeImage(),
    Geometry=types.SimpleNamespace(Point=FakeGeometry),
)

sys.modules["ee"] = fake_ee

import main  # noqa: E402  (imports must come after fake ee is installed)


@pytest.fixture(autouse=True)
def reset_state():
    main._tile_cache.clear()
    main._rate_limiter._hits.clear()
    main._gee_ready = True
    yield
    main._tile_cache.clear()
    main._rate_limiter._hits.clear()
