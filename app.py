import json
import time
import requests
import datetime
import urllib.parse
from pathlib import Path
from typing import Union, List, Dict, Any
import asyncio
import concurrent.futures

from fastapi import FastAPI, Response, Request, Cookie
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

# ===== パス =====
BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# ===== 例外 =====
class APITimeoutError(Exception):
    pass

# ===== Utils =====
def getRandomUserAgent():
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/94.0.4606.61 Safari/537.36"
        )
    }

def isJSON(json_str: str) -> bool:
    try:
        json.loads(json_str)
        return True
    except json.JSONDecodeError:
        return False

# ===== 定数 =====
max_time = 10.0
max_api_wait_time = (3.0, 8.0)
failed = "Load Failed"

EDU_STREAM_API_BASE_URL = "https://siawaseok.duckdns.org/api/stream/"
EDU_VIDEO_API_BASE_URL = "https://siawaseok.duckdns.org/api/video2/"
STREAM_YTDL_API_BASE_URL = "https://yudlp.vercel.app/stream/"
SHORT_STREAM_API_BASE_URL = "https://yt-dl-kappa.vercel.app/short/"

# ===== Invidious =====
invidious_api_data = {
    "video": [],
    "playlist": [
        "https://invidious.lunivers.trade/",
        "https://invidious.ducks.party/",
        "https://super8.absturztau.be/",
        "https://invidious.nikkosphere.com/",
        "https://yt.omada.cafe/",
        "https://iv.melmac.space/",
        "https://iv.duti.dev/",
    ],
    "search": [
        "https://api-five-zeta-55.vercel.app/",
    ],
    "channel": [
        "https://invidious.lunivers.trade/",
        "https://invid-api.poketube.fun/",
        "https://invidious.ducks.party/",
        "https://super8.absturztau.be/",
        "https://invidious.nikkosphere.com/",
        "https://yt.omada.cafe/",
        "https://iv.melmac.space/",
        "https://iv.duti.dev/",
    ],
    "comments": [
        "https://invidious.lunivers.trade/",
        "https://invidious.ducks.party/",
        "https://super8.absturztau.be/",
        "https://invidious.nikkosphere.com/",
        "https://yt.omada.cafe/",
        "https://iv.duti.dev/",
        "https://iv.melmac.space/",
    ],
}

class InvidiousAPI:
    def __init__(self):
        self.all = invidious_api_data
        self.video = list(self.all["video"])
        self.playlist = list(self.all["playlist"])
        self.search = list(self.all["search"])
        self.channel = list(self.all["channel"])
        self.comments = list(self.all["comments"])

# ===== API Request =====
def requestAPI(path: str, api_urls: List[str]) -> str:
    if not api_urls:
        raise APITimeoutError("No API instances configured.")

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(api_urls)) as executor:
        futures = [
            executor.submit(
                requests.get,
                api + "api/v1" + path,
                headers=getRandomUserAgent(),
                timeout=max_api_wait_time
            )
            for api in api_urls
        ]

        for future in concurrent.futures.as_completed(futures, timeout=max_time):
            try:
                res = future.result()
                if res.status_code == 200 and isJSON(res.text):
                    return res.text
            except Exception:
                continue

    raise APITimeoutError("All API instances failed.")

# ===== EDU Key =====
def getEduKey():
    api_url = "https://apis.kahoot.it/media-api/youtube/key"
    try:
        res = requests.get(api_url, headers=getRandomUserAgent(), timeout=max_api_wait_time)
        res.raise_for_status()
        if isJSON(res.text):
            return json.loads(res.text).get("key")
    except Exception:
        pass
    return None

# ===== Search =====
def formatSearchData(d: Dict[str, Any]) -> Dict[str, Any]:
    if d["type"] == "video":
        return {
            "type": "video",
            "title": d.get("title", failed),
            "id": d.get("videoId", failed),
            "author": d.get("author", failed),
            "published": d.get("publishedText", failed),
            "length": str(datetime.timedelta(seconds=d.get("lengthSeconds", 0))),
            "view_count_text": d.get("viewCountText", failed),
        }

    if d["type"] == "playlist":
        return {
            "type": "playlist",
            "title": d.get("title", failed),
            "id": d.get("playlistId", failed),
            "thumbnail": d.get("playlistThumbnail", failed),
            "count": d.get("videoCount", failed),
        }

    if d["type"] == "channel":
        thumb = d.get("authorThumbnails", [{}])[-1].get("url", failed)
        if thumb != failed and not thumb.startswith("https"):
            thumb = "https://" + thumb.lstrip("/")
        return {
            "type": "channel",
            "author": d.get("author", failed),
            "id": d.get("authorId", failed),
            "thumbnail": thumb,
        }

    return {"type": "unknown"}

async def getSearchData(q: str, page: int):
    text = await run_in_threadpool(
        requestAPI,
        f"/search?q={urllib.parse.quote(q)}&page={page}&hl=jp",
        invidious_api.search
    )
    return [formatSearchData(i) for i in json.loads(text)]

async def getCommentsData(videoid: str):
    text = await run_in_threadpool(
        requestAPI,
        f"/comments/{urllib.parse.quote(videoid)}",
        invidious_api.comments
    )
    return [
        {
            "author": i["author"],
            "authoricon": i["authorThumbnails"][-1]["url"],
            "authorid": i["authorId"],
            "body": i["contentHtml"].replace("\n", "<br>"),
        }
        for i in json.loads(text)["comments"]
    ]

# ===== yt-dlp =====
def get_ytdl_formats(videoid: str):
    res = requests.get(
        f"{STREAM_YTDL_API_BASE_URL}{videoid}",
        headers=getRandomUserAgent(),
        timeout=max_api_wait_time
    )
    res.raise_for_status()
    return res.json().get("formats", [])

def get_360p_single_url(videoid: str):
    for f in get_ytdl_formats(videoid):
        if f.get("itag") == "18" and f.get("url"):
            return f["url"]
    raise APITimeoutError("360p stream not found")

async def fetch_embed_url_from_external_api(videoid: str):
    def sync():
        res = requests.get(
            f"{EDU_STREAM_API_BASE_URL}{videoid}",
            headers=getRandomUserAgent(),
            timeout=max_api_wait_time
        )
        res.raise_for_status()
        return res.json()["url"]

    return await run_in_threadpool(sync)

# ===== FastAPI =====
app = FastAPI()
invidious_api = InvidiousAPI()

app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static"
)

@app.get("/api/edu")
async def get_edu_key_route():
    key = await run_in_threadpool(getEduKey)
    if key:
        return {"key": key}
    return Response(
        content='{"error":"failed"}',
        media_type="application/json",
        status_code=500
    )

@app.get("/api/stream_360p_url/{videoid}")
async def get_360p_stream_url_route(videoid: str):
    try:
        url = await run_in_threadpool(get_360p_single_url, videoid)
        return {"stream_url": url}
    except Exception as e:
        return Response(
            content=json.dumps({"error": str(e)}),
            media_type="application/json",
            status_code=503
        )

@app.get("/api/edu/{videoid}", response_class=HTMLResponse)
async def embed_edu_video(
    request: Request,
    videoid: str,
    proxy: Union[str, None] = Cookie(None)
):
    try:
        embed_url = await fetch_embed_url_from_external_api(videoid)
    except Exception:
        return Response("Failed to load stream", status_code=503)

    return templates.TemplateResponse(
        "embed.html",
        {
            "request": request,
            "embed_url": embed_url,
            "videoid": videoid,
            "proxy": proxy
        }
    )
