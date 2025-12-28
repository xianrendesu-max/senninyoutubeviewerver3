import json
import datetime
import urllib.parse
import requests
import concurrent.futures
from pathlib import Path
from typing import List, Dict

from fastapi import FastAPI, Response
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

# =========================
# 基本設定
# =========================

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI()

app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static",
)

# =========================
# 共通
# =========================

class APITimeoutError(Exception):
    pass


def getRandomUserAgent():
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        )
    }


def isJSON(text: str) -> bool:
    try:
        json.loads(text)
        return True
    except Exception:
        return False


max_time = 10.0
max_api_wait_time = (3.0, 8.0)

# =========================
# 外部 API（指定どおり全部）
# =========================

EDU_STREAM_API_BASE_URL = "https://siawaseok.duckdns.org/api/stream/"
EDU_VIDEO_API_BASE_URL = "https://siawaseok.duckdns.org/api/video2/"
STREAM_YTDL_API_BASE_URL = "https://yudlp.vercel.app/stream/"
SHORT_STREAM_API_BASE_URL = "https://yt-dl-kappa.vercel.app/short/"

# =========================
# Invidious API（完全版）
# =========================

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
        self.video = list(invidious_api_data["video"])
        self.playlist = list(invidious_api_data["playlist"])
        self.search = list(invidious_api_data["search"])
        self.channel = list(invidious_api_data["channel"])
        self.comments = list(invidious_api_data["comments"])


invidious_api = InvidiousAPI()


def requestAPI(path: str, api_urls: List[str]) -> str:
    if not api_urls:
        raise APITimeoutError("No API instances")

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=len(api_urls)
    ) as executor:
        futures = {
            executor.submit(
                requests.get,
                api + "api/v1" + path,
                headers=getRandomUserAgent(),
                timeout=max_api_wait_time,
            ): api
            for api in api_urls
        }

        for future in concurrent.futures.as_completed(futures, timeout=max_time):
            try:
                res = future.result()
                if res.status_code == 200 and isJSON(res.text):
                    return res.text
            except Exception:
                pass

    raise APITimeoutError("All Invidious APIs failed")

# =========================
# EDU 動画情報
# =========================

def fetch_video_data_from_edu_api(videoid: str) -> dict:
    res = requests.get(
        f"{EDU_VIDEO_API_BASE_URL}{urllib.parse.quote(videoid)}",
        headers=getRandomUserAgent(),
        timeout=max_api_wait_time,
    )
    res.raise_for_status()
    return res.json()


async def getVideoData(videoid: str):
    data = await run_in_threadpool(fetch_video_data_from_edu_api, videoid)

    return {
        "title": data.get("title"),
        "author": data.get("author", {}).get("name"),
        "description": data.get("description", {}).get("formatted", ""),
    }

# =========================
# 検索
# =========================

def formatSearchData(d: dict) -> dict:
    return {
        "videoId": d.get("videoId"),
        "title": d.get("title"),
        "author": d.get("author"),
    }


async def getSearchData(q: str):
    text = await run_in_threadpool(
        requestAPI,
        f"/search?q={urllib.parse.quote(q)}&hl=jp",
        invidious_api.search,
    )
    data = json.loads(text)
    return [formatSearchData(i) for i in data if i.get("type") == "video"]

# =========================
# チャンネル
# =========================

async def getChannelVideos(channel_id: str):
    text = await run_in_threadpool(
        requestAPI,
        f"/channel/{urllib.parse.quote(channel_id)}",
        invidious_api.channel,
    )
    data = json.loads(text)
    return data.get("latestVideos", [])

# =========================
# コメント
# =========================

async def getCommentsData(videoid: str):
    text = await run_in_threadpool(
        requestAPI,
        f"/comments/{urllib.parse.quote(videoid)}",
        invidious_api.comments,
    )
    data = json.loads(text).get("comments", [])
    return [
        {
            "author": i.get("author"),
            "content": i.get("content"),
        }
        for i in data
    ]

# =========================
# ストリーム
# =========================

def get_360p_single_url(videoid: str) -> str:
    res = requests.get(
        f"{STREAM_YTDL_API_BASE_URL}{videoid}",
        headers=getRandomUserAgent(),
        timeout=max_api_wait_time,
    )
    res.raise_for_status()

    for f in res.json().get("formats", []):
        if f.get("itag") == "18" and f.get("url"):
            return f["url"]

    raise APITimeoutError("360p not found")


def get_short_stream(videoid: str) -> str:
    res = requests.get(
        f"{SHORT_STREAM_API_BASE_URL}{videoid}",
        headers=getRandomUserAgent(),
        timeout=max_api_wait_time,
    )
    res.raise_for_status()
    return res.json().get("url")

# =========================
# API ROUTES
# =========================

@app.get("/api/search")
async def api_search(q: str):
    return {
        "results": await getSearchData(q),
        "source": "invidious",
    }


@app.get("/api/video")
async def api_video(video_id: str):
    return await getVideoData(video_id)


@app.get("/api/comments")
async def api_comments(video_id: str):
    return {"comments": await getCommentsData(video_id)}


@app.get("/api/channel")
async def api_channel(channel_id: str):
    return {"videos": await getChannelVideos(channel_id)}


@app.get("/api/streamurl")
async def api_streamurl(video_id: str, quality: str = "360p"):
    if quality == "360p":
        url = await run_in_threadpool(get_360p_single_url, video_id)
        return Response(status_code=307, headers={"Location": url})

    if quality == "short":
        url = await run_in_threadpool(get_short_stream, video_id)
        return Response(status_code=307, headers={"Location": url})

    return Response("unsupported quality", status_code=400)

# =========================
# 起動確認
# =========================

@app.get("/")
def root():
    return {"status": "ok"}
