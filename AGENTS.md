# AGENTS.md

FastAPI + Earth Engine app: serves Leaflet tile URLs for environmental layers of Campinas. Deployed on Render (free plan). No linter; tests run via GitHub Actions on push/PR.

## Run locally

```sh
pip install -r requirements.txt -r requirements-dev.txt
export EE_CREDENTIALS='{"client_email":"...","private_key":"...","project_id":"..."}'
uvicorn main:app --reload
python -m pytest -q   # tests mock `ee`, no network/credentials needed
```

- `init_gee()` runs at import time (`main.py:34`). It is **graceful**: without a valid `EE_CREDENTIALS` the app still boots, `/healthz` returns 503, and `/tile`+`/info` return 503. `EE_CREDENTIALS` must be a JSON service-account key with the `private_key` newlines escaped as `\\n` (the code replaces `\\n` → `\n` at `main.py:22`).
- Never commit the service-account JSON (see `0765a6d "Delete ee.json"`). On Render it is set manually in the dashboard; `render.yaml` declares it with `sync: false`, so it is absent from the repo.

## Tests

- `tests/conftest.py` injects a fake `ee` module into `sys.modules` **before** importing `main`, so no GEE credentials or network are needed. Keep it that way for new tests.
- The rate limiter (`main._rate_limiter`) and tile cache are module-level state; the `reset_state` autouse fixture clears them between tests.

## Architecture

- `main.py` — the whole backend.
  - `/tile?asset_id=&palette=&is_point=` returns a GEE tile URL via `ee.Image().getMapId()`, cached in a `TTLCache` (12h, keyed on `(asset_id, palette, is_point)`) because GEE URLs expire in ~1 day.
  - `/info?asset_id=&lat=&lon=` returns the first feature's properties within 50 m of the click point (powers the frontend popup).
  - `/healthz` — Render health check (`healthCheckPath` in `render.yaml`).
  - `/tile` and `/info` are rate-limited per client IP (fixed 60 req/min window) and return proper 4xx/5xx, not `{"error": ...}` with HTTP 200.
- `static/index.html` — frontend served at `/` by `StaticFiles(html=True)` (`main.py:149`). Layers are hardcoded in `layersConfig` (asset IDs in GEE projects `ee-pigee` / `ee-rogodoytest`, colors, and `point: true` for point features). To add a layer, edit `layersConfig`, not the backend. Layers load lazily on checkbox enable; the client refetches expired URLs and shows per-layer loading/error/opacity UI.
- GEE tile URLs from `getMapId` expire (~1 day); server `TTLCache` (12h) and client `tileCache` (20h) keep caches fresher than expiry.

## Deploy

Git push to `main` (Render auto-deploys). Build/start commands live in `render.yaml`. Free plan = single web service, ephemeral filesystem.
