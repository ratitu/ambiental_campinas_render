# AGENTS.md

FastAPI + Earth Engine app: serves Leaflet tile URLs for environmental layers of Campinas. Deployed on Render (free plan). No tests, no linter, no CI.

## Run locally

```sh
pip install -r requirements.txt
export EE_CREDENTIALS='{"client_email":"...","private_key":"...","project_id":"..."}'
uvicorn main:app --reload
```

- `init_gee()` runs at import time (`main.py:24`), so the app **fails to start without `EE_CREDENTIALS`**. It must be a JSON service-account key with the `private_key` newlines escaped as `\\n` (the code replaces `\\n` → `\n` at `main.py:15`).
- Never commit the service-account JSON (see `0765a6d "Delete ee.json"`). On Render it is set manually in the dashboard; `render.yaml` declares it with `sync: false`, so it is absent from the repo.

## Architecture

- `main.py` — the whole backend. One endpoint `/tile?asset_id=&palette=&is_point=` returns a GEE tile URL via `ee.Image().getMapId()`. `generate_tile` is cached with `@lru_cache` keyed on `(asset_id, palette, is_point)`.
- `static/index.html` — frontend served at `/` by `StaticFiles(html=True)` (`main.py:55`). Leaflet map; layers are hardcoded in `layersConfig` (asset IDs in GEE projects `ee-pigee` / `ee-rogodoytest`, colors, and `point: true` for point features). To add a layer, edit `layersConfig`, not the backend.
- GEE tile URLs from `getMapId` expire (~1 day); the client (`tileCache`) and server caches are just per-process/per-session, not persistent.

## Deploy

Git push to `main` (Render auto-deploys). Build/start commands live in `render.yaml`. Free plan = single web service, ephemeral filesystem.
