from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from cachetools import TTLCache
import ee
import json
import os
import threading
import time

app = FastAPI()

# ---------------------------
# INIT GEE (graceful: app boots even without EE_CREDENTIALS)
# ---------------------------
_gee_ready = False


def init_gee():
    global _gee_ready
    try:
        creds = json.loads(os.environ["EE_CREDENTIALS"])
        private_key = creds["private_key"].replace("\\n", "\n")
        credentials = ee.ServiceAccountCredentials(
            creds["client_email"],
            key_data=private_key
        )
        ee.Initialize(credentials, project=creds["project_id"])
        _gee_ready = True
    except Exception as e:
        _gee_ready = False
        print(f"[init_gee] failed: {e}", flush=True)


init_gee()

# ---------------------------
# CACHE DE TILE (TTL ~ GEE tile URLs expire in ~1 day)
# ---------------------------
_tile_cache = TTLCache(maxsize=128, ttl=12 * 3600)
_tile_lock = threading.RLock()


def generate_tile(asset_id, palette, is_point):
    key = (asset_id, palette, is_point)
    with _tile_lock:
        cached = _tile_cache.get(key)
    if cached:
        return cached

    fc = ee.FeatureCollection(asset_id)
    if is_point:
        image = ee.Image().paint(fc.map(lambda f: f.buffer(15)), 0)
    else:
        image = ee.Image().paint(fc, 0, 2)

    map_id = image.getMapId({'palette': palette})
    url = map_id['tile_fetcher'].url_format

    with _tile_lock:
        _tile_cache[key] = url
    return url


# ---------------------------
# RATE LIMIT (fixed window per client IP)
# ---------------------------
class FixedWindowLimiter:
    def __init__(self, limit, window):
        self.limit = limit
        self.window = window
        self._hits = {}
        self._lock = threading.RLock()

    def allow(self, key):
        now = time.monotonic()
        with self._lock:
            cutoff = now - self.window
            self._hits = {k: [t for t in ts if t > cutoff]
                          for k, ts in self._hits.items() if ts}
            timestamps = self._hits.setdefault(key, [])
            if len(timestamps) >= self.limit:
                return False
            timestamps.append(now)
            return True


_rate_limiter = FixedWindowLimiter(limit=60, window=60)


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check_rate_limit(request: Request):
    if not _rate_limiter.allow(client_ip(request)):
        raise HTTPException(status_code=429, detail="Too many requests")


def require_gee():
    if not _gee_ready:
        raise HTTPException(status_code=503, detail="GEE not initialized")


# ---------------------------
# ENDPOINTS
# ---------------------------
@app.get("/healthz")
def healthz():
    if not _gee_ready:
        raise HTTPException(status_code=503, detail="GEE not initialized")
    return {"status": "ok"}


@app.get("/tile")
def get_tile(request: Request, asset_id: str, palette: str, is_point: bool = False):
    check_rate_limit(request)
    require_gee()
    try:
        url = generate_tile(asset_id, palette, is_point)
        return {"url": url}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/info")
def get_info(request: Request, asset_id: str, lat: float, lon: float):
    check_rate_limit(request)
    require_gee()
    try:
        fc = ee.FeatureCollection(asset_id)
        point = ee.Geometry.Point([lon, lat]).buffer(50)
        info = fc.filterBounds(point).first().getInfo()
        properties = (info or {}).get("properties", {})
        return {"properties": properties}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------
# FRONTEND
# ---------------------------
app.mount("/", StaticFiles(directory="static", html=True), name="static")
