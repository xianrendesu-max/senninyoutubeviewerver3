import json
import random
import urllib.parse
import requests
import concurrent.futures
from typing import List
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool

# =====================================================
# 基本設定
# =====================================================

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

def ua():
    return {
        "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    }

MAX_TIMEOUT = 10

# =====================================================
# Invidious API 一覧（全部）
# =====================================================

INVIDIOUS_APIS = {
    "video": [
        "https://invidious.exma.de/",
        "https://invidious.f5.si/",
        "https://siawaseok-wakame-server2.glitch.me/",
        "https://lekker.gay/",
        "https://id.420129.xyz/",
        "https://invid-api.poketube.fun/",
        "https://eu-proxy.poketube.fun/",
        "https://cal1.iv.ggtyler.dev/",
        "https://pol1.iv.ggtyler.dev/",
    ],
    "search": [
        "https://pol1.iv.ggtyler.dev/",
        "https://youtube.mosesmang.com/",
        "https://iteroni.com/",
        "https://invidious.0011.lt/",
        "https://iv.melmac.space/",
        "https://rust.oskamp.nl/",
        "https://api-five-zeta-55.vercel.app/",
    ],
    "channel": [
        "https://siawaseok-wakame-server2.glitch.me/",
        "https://id.420129.xyz/",
        "https://invidious.0011.lt/",
        "https://invidious.nietzospannend.nl/",
        "https://invidious.lunivers.trade/",
        "https://invidious.ducks.party/",
        "https://super8.absturztau.be/",
        "https://invidious.nikkosphere.com/",
        "https://yt.omada.cafe/",
        "https://iv.melmac.space/",
        "https://iv.duti.dev/",
    ],
    "playlist": [
        "https://siawaseok-wakame-server2.glitch.me/",
        "https://invidious.0011.lt/",
        "https://invidious.nietzospannend.nl/",
        "https://youtube.mosesmang.com/",
        "https://iv.melmac.space/",
        "https://lekker.gay/",
    ],
    "comments": [
        "https://siawaseok-wakame-server2.glitch.me/",
        "https://invidious.0011.lt/",
        "https://invidious.nietzospannend.nl/",
        "https://invidious.lunivers.trade/",
        "https://invidious.ducks.party/",
        "https://super8.absturztau.be/",
        "https://invidious.nikkosphere.com/",
        "https://yt.omada.cafe/",
        "https://iv.duti.dev/",
        "https://iv.melmac.space/",
    ],
}

# =====================================================
# EDU / ytdlp API
# =====================================================

EDU_STREAM_API_BASE_URL = "https://siawaseok.duckdns.org/api/stream/"
EDU_VIDEO_API_BASE_URL = "https://siawaseok.duckdns.org/api/video2/"
STREAM_YTDL_API_BASE_URL = "https://yudlp.vercel.app/stream/"
SHORT_STREAM_API_BASE_URL = "https://yt-dl-kappa.vercel.app/short/"
YTDLP_M3U8_API = "https://yudlp.vercel.app/m3u8/"

# =====================================================
# 共通：Invidious API フォールバック
# =====================================================

def request_invidious(path: str, apis: List[str]):
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(apis)) as ex:
        futures = [
            ex.submit(
                requests.get,
                api + "api/v1" + path,
                headers=ua(),
                timeout=MAX_TIMEOUT,
            )
            for api in apis
        ]
        for f in concurrent.futures.as_completed(futures):
            try:
                r = f.result()
                if r.status_code == 200:
                    return r.json()
            except Exception:
                pass
    raise RuntimeError("All Invidious APIs failed")

# =====================================================
# FastAPI
# =====================================================

app = FastAPI()

app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static",
)

# =====================================================
# ページ
# =====================================================

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/watch", response_class=HTMLResponse)
async def watch(request: Request):
    return templates.TemplateResponse("watch.html", {"request": request})

# =====================================================
# 検索
# =====================================================

@app.get("/api/search")
async def api_search(q: str):
    return await run_in_threadpool(
        request_invidious,
        f"/search?q={urllib.parse.quote(q)}&type=video",
        INVIDIOUS_APIS["search"],
    )

# =====================================================
# 動画情報（EDU優先 → Invidious）
# =====================================================

@app.get("/api/video")
async def api_video(video_id: str):
    try:
        r = await run_in_threadpool(
            requests.get,
            f"{EDU_VIDEO_API_BASE_URL}{video_id}",
            ua(),
            MAX_TIMEOUT,
        )
        if r.status_code == 200:
            d = r.json()
            return {
                "title": d.get("title"),
                "author": d.get("author", {}).get("name"),
                "description": d.get("description", {}).get("formatted", ""),
            }
    except Exception:
        pass

    d = await run_in_threadpool(
        request_invidious,
        f"/videos/{video_id}",
        INVIDIOUS_APIS["video"],
    )
    return {
        "title": d.get("title"),
        "author": d.get("author"),
        "description": d.get("description"),
    }

# =====================================================
# コメント
# =====================================================

@app.get("/api/comments")
async def api_comments(video_id: str):
    d = await run_in_threadpool(
        request_invidious,
        f"/comments/{video_id}",
        INVIDIOUS_APIS["comments"],
    )
    return {
        "comments": [
            {
                "author": c["author"],
                "content": c["contentHtml"],
            }
            for c in d.get("comments", [])
        ]
    }

# =====================================================
# 高画質フォーマット一覧（m3u8）
# =====================================================

@app.get("/api/formats")
async def api_formats(video_id: str):
    r = await run_in_threadpool(
        requests.get,
        f"{YTDLP_M3U8_API}{video_id}",
        None,
        MAX_TIMEOUT,
    )
    r.raise_for_status()
    data = r.json()

    formats = []
    for f in data.get("m3u8_formats", []):
        formats.append({
            "resolution": f.get("resolution"),
            "fps": f.get("fps"),
            "url": f.get("url"),
        })

    formats.sort(
        key=lambda x: int(x["resolution"].split("x")[-1])
        if x["resolution"] else 0,
        reverse=True,
    )

    return {"formats": formats}

# =====================================================
# 360p / short ストリーム
# =====================================================

@app.get("/api/streamurl")
async def api_streamurl(video_id: str, short: bool = False):
    base = SHORT_STREAM_API_BASE_URL if short else STREAM_YTDL_API_BASE_URL
    r = await run_in_threadpool(
        requests.get,
        f"{base}{video_id}",
        ua(),
        MAX_TIMEOUT,
    )
    r.raise_for_status()
    data = r.json()

    for f in data.get("formats", []):
        if f.get("itag") == "18":
            return {"url": f["url"]}

    return JSONResponse({"error": "not found"}, status_code=404)

# =====================================================
# EDU ストリーム（埋め込み用）
# =====================================================

@app.get("/api/edu_stream")
async def api_edu_stream(video_id: str):
    r = await run_in_threadpool(
        requests.get,
        f"{EDU_STREAM_API_BASE_URL}{video_id}",
        ua(),
        MAX_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()
