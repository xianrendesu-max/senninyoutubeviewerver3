from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import requests
import random

app = FastAPI()

# ===============================
# パス設定
# ===============================
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ===============================
# API プール
# ===============================
API_POOLS = {
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

# ===============================
# EDU / STREAM API
# ===============================
EDU_STREAM_API_BASE_URL = "https://siawaseok.duckdns.org/api/stream/"
EDU_VIDEO_API_BASE_URL = "https://siawaseok.duckdns.org/api/video2/"
STREAM_YTDL_API_BASE_URL = "https://yudlp.vercel.app/stream/"
SHORT_STREAM_API_BASE_URL = "https://yt-dl-kappa.vercel.app/short/"

# ===============================
# 共通関数
# ===============================
def pick(pool):
    return random.choice(pool)

# ===============================
# HTML ルーティング
# ===============================
@app.get("/", response_class=HTMLResponse)
def index():
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")

@app.get("/watch", response_class=HTMLResponse)
def watch():
    return (STATIC_DIR / "watch.html").read_text(encoding="utf-8")

@app.get("/channel", response_class=HTMLResponse)
def channel_page():
    return (STATIC_DIR / "channel.html").read_text(encoding="utf-8")

# ===============================
# SEARCH
# ===============================
@app.get("/api/search")
def api_search(q: str = Query(...)):
    base = pick(API_POOLS["search"])
    try:
        r = requests.get(
            f"{base}api/search",
            params={"q": q, "type": "video"},
            timeout=10,
        )
        return r.json()
    except:
        return {"items": []}

# ===============================
# VIDEO INFO
# ===============================
@app.get("/api/video")
def api_video(video_id: str):
    try:
        r = requests.get(
            f"{EDU_VIDEO_API_BASE_URL}{video_id}",
            timeout=10,
        )
        return r.json()
    except:
        return {
            "title": "取得失敗",
            "author": "",
            "description": "",
        }

# ===============================
# COMMENTS
# ===============================
@app.get("/api/comments")
def api_comments(video_id: str):
    base = pick(API_POOLS["comments"])
    try:
        r = requests.get(
            f"{base}api/v1/comments/{video_id}",
            timeout=10,
        )
        data = r.json()
        out = []
        for c in data.get("comments", []):
            out.append(
                {
                    "author": c.get("author", ""),
                    "content": c.get("content", ""),
                }
            )
        return {"comments": out}
    except:
        return {"comments": []}

# ===============================
# CHANNEL INFO
# ===============================
@app.get("/api/channel")
def api_channel(channel_id: str):
    base = pick(API_POOLS["channel"])
    try:
        r = requests.get(
            f"{base}api/v1/channels/{channel_id}",
            timeout=10,
        )
        return r.json()
    except:
        return {}

# ===============================
# STREAM URL
# ===============================
@app.get("/api/streamurl")
def api_streamurl(video_id: str, quality: str = "best"):
    candidates = [
        f"{EDU_STREAM_API_BASE_URL}{video_id}",
        f"{STREAM_YTDL_API_BASE_URL}{video_id}",
        f"{SHORT_STREAM_API_BASE_URL}{video_id}",
    ]

    for url in candidates:
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                return RedirectResponse(r.url)
        except:
            pass

    return JSONResponse({"error": "stream unavailable"})

# ===============================
# STATUS
# ===============================
@app.get("/status")
def status():
    return {"status": "ok"}
