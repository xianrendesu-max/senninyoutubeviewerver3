import json
import requests
import datetime
import urllib.parse
from pathlib import Path
import concurrent.futures
from typing import Union

from fastapi import FastAPI, Response, Request, Cookie
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

# ======================
# パス設定（致命的修正）
# ======================
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# ======================
# 例外
# ======================
class APITimeoutError(Exception):
    pass

# ======================
# 共通関数
# ======================
def getRandomUserAgent():
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120 Safari/537.36"
        )
    }

def isJSON(s: str):
    try:
        json.loads(s)
        return True
    except:
        return False

max_time = 10.0
max_api_wait_time = (3.0, 8.0)

# ======================
# 外部API
# ======================
EDU_STREAM_API_BASE_URL = "https://siawaseok.duckdns.org/api/stream/"
STREAM_YTDL_API_BASE_URL = "https://yudlp.vercel.app/stream/"

# ======================
# Invidious
# ======================
invidious_api_data = {
    "search": ["https://api-five-zeta-55.vercel.app/"],
    "video": ["https://invidious.lunivers.trade/"],
    "comments": ["https://invidious.lunivers.trade/"],
    "channel": ["https://invidious.lunivers.trade/"]
}

class InvidiousAPI:
    def __init__(self):
        self.search = invidious_api_data["search"]
        self.video = invidious_api_data["video"]
        self.comments = invidious_api_data["comments"]
        self.channel = invidious_api_data["channel"]

invidious_api = InvidiousAPI()

def requestAPI(path, api_urls):
    if not api_urls:
        raise APITimeoutError("no api")

    with concurrent.futures.ThreadPoolExecutor(len(api_urls)) as ex:
        futures = [
            ex.submit(
                requests.get,
                api + "api/v1" + path,
                headers=getRandomUserAgent(),
                timeout=max_api_wait_time
            )
            for api in api_urls
        ]

        for f in concurrent.futures.as_completed(futures, timeout=max_time):
            try:
                r = f.result()
                if r.status_code == 200 and isJSON(r.text):
                    return r.text
            except:
                pass

    raise APITimeoutError("all api failed")

# ======================
# yt-dlp
# ======================
def get_ytdl_formats(videoid):
    r = requests.get(
        f"{STREAM_YTDL_API_BASE_URL}{videoid}",
        headers=getRandomUserAgent(),
        timeout=max_api_wait_time
    )
    r.raise_for_status()
    return r.json()["formats"]

def get_360p_single_url(videoid):
    for f in get_ytdl_formats(videoid):
        if f.get("itag") == "18":
            return f["url"]
    raise APITimeoutError("360p not found")

# ======================
# FastAPI
# ======================
app = FastAPI()

app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static"
)

# ======================
# API: search
# ======================
@app.get("/api/search")
async def api_search(q: str, page: int = 1):
    text = await run_in_threadpool(
        requestAPI,
        f"/search?q={urllib.parse.quote(q)}&page={page}&hl=jp",
        invidious_api.search
    )
    data = json.loads(text)

    return {
        "results": [
            {
                "videoId": v["videoId"],
                "title": v["title"],
                "author": v.get("author", "")
            }
            for v in data if v["type"] == "video"
        ],
        "source": "invidious"
    }

# ======================
# API: video info
# ======================
@app.get("/api/video")
async def api_video(video_id: str):
    text = await run_in_threadpool(
        requestAPI,
        f"/videos/{video_id}?hl=jp",
        invidious_api.video
    )
    v = json.loads(text)
    return {
        "title": v.get("title"),
        "author": v.get("author"),
        "description": v.get("description")
    }

# ======================
# API: comments
# ======================
@app.get("/api/comments")
async def api_comments(video_id: str):
    text = await run_in_threadpool(
        requestAPI,
        f"/comments/{video_id}?hl=jp",
        invidious_api.comments
    )
    d = json.loads(text)
    return {
        "comments": [
            {
                "author": c["author"],
                "content": c["contentHtml"]
            }
            for c in d.get("comments", [])
        ]
    }

# ======================
# API: channel
# ======================
@app.get("/api/channel")
async def api_channel(channel_id: str):
    text = await run_in_threadpool(
        requestAPI,
        f"/channels/{channel_id}?hl=jp",
        invidious_api.channel
    )
    d = json.loads(text)

    return {
        "name": d.get("author"),
        "videos": [
            {
                "id": v["videoId"],
                "title": v["title"],
                "thumb": v["videoThumbnails"][-1]["url"]
            }
            for v in d.get("latestVideos", [])
        ]
    }

# ======================
# API: stream
# ======================
@app.get("/api/streamurl", response_class=HTMLResponse)
async def api_streamurl(video_id: str, quality: str = "360p"):
    if quality == "360p":
        url = await run_in_threadpool(get_360p_single_url, video_id)
    else:
        fmts = await run_in_threadpool(get_ytdl_formats, video_id)
        url = None
        for f in fmts:
            if quality == "best" or (quality == "720p" and f.get("height") == 720):
                url = f.get("url")
                break
        if not url:
            raise APITimeoutError("stream not found")

    return f"""
    <html><body style="margin:0;background:#000">
    <video src="{url}" controls autoplay style="width:100vw;height:100vh"></video>
    </body></html>
    """
