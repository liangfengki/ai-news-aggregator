import asyncio
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from scraper import (
    init_db, refresh_news, get_news, get_news_count, cleanup_old_news,
    get_stats, get_sources, get_trending_topics,
)

_last_refresh = 0
_refresh_lock = asyncio.Lock()
BG_REFRESH_INTERVAL = 120  # 2 minutes for RSS fetch
LLM_INTERVAL = 600  # 10 minutes for LLM translation


async def _background_rss():
    """Fast RSS fetch every 2 minutes (no LLM)."""
    global _last_refresh
    while True:
        await asyncio.sleep(BG_REFRESH_INTERVAL)
        try:
            async with _refresh_lock:
                result = await refresh_news(use_llm=False)
                _last_refresh = time.time()
                print(f"📡 RSS: {result['fetched']} fetched, {result['new']} new")
            # 每次刷新后清理 48 小时前的旧新闻
            cleanup_old_news(keep_hours=48)
        except Exception as e:
            print(f"⚠ RSS refresh failed: {e}")


async def _background_llm():
    """Slow LLM translation every 10 minutes."""
    while True:
        await asyncio.sleep(LLM_INTERVAL)
        try:
            from scraper import translate_untranslated
            count = await translate_untranslated()
            if count > 0:
                print(f"🤖 LLM: translated {count} items")
        except Exception as e:
            print(f"⚠ LLM translation failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    global _last_refresh
    print("🚀 AI News Aggregator starting...")
    init_db()

    # Initial fetch (fast, keyword-only)
    try:
        result = await refresh_news(use_llm=False)
        _last_refresh = time.time()
        print(f"✅ Initial fetch: {result['fetched']} items, {result['new']} new")
    except Exception as e:
        print(f"⚠ Initial fetch failed: {e}")

    # Start background tasks
    rss_task = asyncio.create_task(_background_rss())
    llm_task = asyncio.create_task(_background_llm())

    yield

    rss_task.cancel()
    llm_task.cancel()
    print("👋 Shutting down...")


app = FastAPI(title="AI News Aggregator", lifespan=lifespan)

# Middleware
app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main dashboard page."""
    with open("static/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/api/news")
async def api_news(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    market: str = Query(None),
    sentiment: str = Query(None),
    source: str = Query(None),
    highlight: bool = Query(False),
    search: str = Query(None),
    sort: str = Query("impact"),
    hours: int = Query(24),
):
    """Get news with optional filters and search."""
    items = get_news(
        limit=limit, offset=offset, market=market,
        sentiment=sentiment, source=source,
        highlight_only=highlight, search=search, sort=sort, hours=hours,
    )
    total = get_news_count(
        market=market, sentiment=sentiment, source=source,
        highlight_only=highlight, search=search,
    )
    return {
        "items": items,
        "count": len(items),
        "total": total,
        "offset": offset,
    }


@app.get("/api/search")
async def api_search(
    q: str = Query(..., min_length=1),
    limit: int = Query(30, ge=1, le=100),
):
    """Search news by keyword."""
    items = get_news(limit=limit, search=q)
    return {
        "items": items,
        "count": len(items),
        "query": q,
    }


@app.get("/api/trending")
async def api_trending():
    """Get trending topics."""
    topics = get_trending_topics()
    return {"topics": topics}


@app.get("/api/stats")
async def api_stats():
    """Get dashboard statistics."""
    stats = get_stats()
    stats["last_refresh"] = _last_refresh
    return stats


@app.get("/api/sources")
async def api_sources():
    """Get list of news sources."""
    return {"sources": get_sources()}


@app.get("/api/news/count")
async def api_news_count(
    market: str = Query(None),
    sentiment: str = Query(None),
    source: str = Query(None),
    highlight: bool = Query(False),
    search: str = Query(None),
    hours: int = Query(24),
):
    """Get total count of news matching filters."""
    total = get_news_count(
        market=market, sentiment=sentiment, source=source,
        highlight_only=highlight, search=search, hours=hours,
    )
    return {"total": total}


@app.post("/api/refresh")
async def api_refresh():
    """Trigger a manual refresh (with LLM classification)."""
    global _last_refresh
    async with _refresh_lock:
        result = await refresh_news(use_llm=True)
        _last_refresh = time.time()
    return result


@app.get("/api/health")
async def health():
    return {"status": "ok", "uptime": time.time() - _last_refresh if _last_refresh else 0}


@app.get("/api/market")
async def api_market():
    """Get real-time market index data."""
    from fastapi.responses import JSONResponse
    import httpx

    indices = []

    # 新浪财经 - 国内指数
    try:
        cn_codes = "s_sh000001,s_sz399001,s_sz399006,s_sh000688"
        r = await httpx.AsyncClient().get(
            f"https://hq.sinajs.cn/list={cn_codes}",
            headers={"Referer": "https://finance.sina.com.cn", "User-Agent": "Mozilla/5.0"},
            timeout=8.0,
        )
        for line in r.text.strip().split("\n"):
            if "=" in line:
                raw = line.split("=")[1].strip().strip('"').strip(';').strip('"')
                parts = raw.split(",")
                if len(parts) >= 4:
                    try:
                        indices.append({
                            "name": parts[0],
                            "price": float(parts[1]),
                            "change": float(parts[2]),
                            "change_pct": float(parts[3]),
                        })
                    except ValueError:
                        pass
    except Exception as e:
        print(f"CN indices error: {e}")

    # 新浪财经 - 国际指数
    try:
        intl_codes = "int_dji,int_nasdaq,int_sp500,int_nikkei,int_ftse"
        r = await httpx.AsyncClient().get(
            f"https://hq.sinajs.cn/list={intl_codes}",
            headers={"Referer": "https://finance.sina.com.cn", "User-Agent": "Mozilla/5.0"},
            timeout=8.0,
        )
        for line in r.text.strip().split("\n"):
            if "=" in line:
                raw = line.split("=")[1].strip().strip('"').strip(';').strip('"')
                parts = raw.split(",")
                if len(parts) >= 4:
                    try:
                        indices.append({
                            "name": parts[0],
                            "price": float(parts[1]),
                            "change": float(parts[2]),
                            "change_pct": float(parts[3]),
                        })
                    except ValueError:
                        pass
    except Exception as e:
        print(f"Intl indices error: {e}")

    return JSONResponse(
        content={"indices": indices},
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8080, reload=False, log_level="info")
