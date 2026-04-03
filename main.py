from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import ee
import os
import json
from functools import lru_cache

app = FastAPI()

# ---------------------------
# INIT GEE
# ---------------------------
def init_gee():
    creds = json.loads(os.environ["EE_CREDENTIALS"])
    private_key = creds["private_key"].replace("\\n", "\n")

    credentials = ee.ServiceAccountCredentials(
        creds["client_email"],
        key_data=private_key
    )

    ee.Initialize(credentials, project=creds["project_id"])

init_gee()

# ---------------------------
# CACHE DE TILE (🔥)
# ---------------------------
@lru_cache(maxsize=128)
def generate_tile(asset_id, palette, is_point):
    fc = ee.FeatureCollection(asset_id)

    if is_point:
        image = ee.Image().paint(fc.map(lambda f: f.buffer(15)), 0)
    else:
        image = ee.Image().paint(fc, 0, 2)

    map_id = image.getMapId({'palette': palette})
    return map_id['tile_fetcher'].url_format

# ---------------------------
# ENDPOINT
# ---------------------------
@app.get("/tile")
def get_tile(asset_id: str, palette: str, is_point: bool = False):
    try:
        url = generate_tile(asset_id, palette, is_point)
        return {"url": url}
    except Exception as e:
        return {"error": str(e)}

# ---------------------------
# FRONTEND
# ---------------------------
app.mount("/", StaticFiles(directory="static", html=True), name="static")
