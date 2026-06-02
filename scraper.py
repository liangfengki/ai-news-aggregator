import asyncio
import hashlib
import json
import re
import sqlite3
import time
from datetime import datetime, timezone
from difflib import SequenceMatcher

import feedparser
import httpx
from bs4 import BeautifulSoup

from sources import RSS_FEEDS
from classifier import (
    classify_news, classify_news_batch, init_classifier_cache,
    OPENROUTER_API_KEY, OPENROUTER_BASE_URL, OPENROUTER_MODEL,
)

DB_PATH = "data/news.db"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def init_db():
    """Initialize SQLite database."""
    import os
    os.makedirs(os.path.dirname(DB_PATH) or "data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS news (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            summary TEXT,
            link TEXT NOT NULL,
            source TEXT NOT NULL,
            lang TEXT DEFAULT 'en',
            category TEXT,
            published_at TEXT,
            fetched_at REAL,
            markets TEXT,
            sentiment TEXT DEFAULT 'neutral',
            impact_score INTEGER DEFAULT 0,
            tags TEXT,
            is_highlight INTEGER DEFAULT 0
        )
    """)
    # Safe migration: add translation columns if missing
    try:
        conn.execute("ALTER TABLE news ADD COLUMN title_zh TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE news ADD COLUMN summary_zh TEXT")
    except sqlite3.OperationalError:
        pass
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_news_fetched ON news(fetched_at DESC)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_news_impact ON news(impact_score DESC)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_news_sentiment ON news(sentiment)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_news_source ON news(source)
    """)
    conn.commit()
    conn.close()

    # Initialize classifier cache
    init_classifier_cache()


def _make_id(link: str, title: str) -> str:
    """Generate unique ID for a news item."""
    raw = f"{link}:{title}"
    return hashlib.md5(raw.encode()).hexdigest()


def _clean_html(html_text: str) -> str:
    """Clean HTML content, removing scripts, styles, and extracting text."""
    if not html_text:
        return ""

    soup = BeautifulSoup(html_text, "html.parser")

    # Remove unwanted elements
    for tag in soup.find_all(["script", "style", "iframe", "noscript", "svg", "form", "nav", "footer", "header"]):
        tag.decompose()

    # Remove comments
    from bs4 import Comment
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()

    text = soup.get_text(separator=" ", strip=True)

    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    return text[:800]


def _extract_summary(entry) -> str:
    """Extract clean text summary from feed entry."""
    summary = ""
    if hasattr(entry, "summary"):
        summary = entry.summary
    elif hasattr(entry, "description"):
        summary = entry.description
    elif hasattr(entry, "content"):
        for c in entry.content:
            summary = c.get("value", "")
            break

    return _clean_html(summary)


def _extract_content(entry) -> str:
    """Try to extract full article content from entry."""
    # Some feeds include full content in content:encoded
    if hasattr(entry, "content"):
        for c in entry.content:
            val = c.get("value", "")
            if len(val) > 200:  # Likely full content
                return _clean_html(val)

    # Try content:encoded (common in WordPress feeds)
    if hasattr(entry, "content_encoded"):
        return _clean_html(entry.content_encoded)

    return ""


def _parse_date(entry) -> str:
    """Parse published date from entry with improved parsing."""
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            try:
                dt = datetime(*parsed[:6], tzinfo=timezone.utc)
                return dt.isoformat()
            except Exception:
                pass

    # Try parsing string dates
    for attr in ("published", "updated"):
        val = getattr(entry, attr, None)
        if val:
            # Try common formats
            for fmt in (
                "%a, %d %b %Y %H:%M:%S %z",
                "%a, %d %b %Y %H:%M:%S %Z",
                "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%d %H:%M:%S",
            ):
                try:
                    dt = datetime.strptime(val.strip(), fmt)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt.isoformat()
                except ValueError:
                    continue
            return val  # Return raw string if parsing fails

    return datetime.now(timezone.utc).isoformat()


def _is_similar(title1: str, title2: str, threshold: float = 0.75) -> bool:
    """Check if two titles are similar (duplicate detection)."""
    # Normalize
    t1 = re.sub(r'[^\w\s]', '', title1.lower()).strip()
    t2 = re.sub(r'[^\w\s]', '', title2.lower()).strip()

    if not t1 or not t2:
        return False

    return SequenceMatcher(None, t1, t2).ratio() >= threshold


async def fetch_feed(client: httpx.AsyncClient, feed_config: dict) -> list:
    """Fetch and parse a single RSS feed."""
    url = feed_config["url"]
    name = feed_config["name"]
    items = []

    try:
        resp = await client.get(url, timeout=15.0, follow_redirects=True)
        if resp.status_code != 200:
            print(f"  ⚠ {name}: HTTP {resp.status_code}")
            return []

        feed = feedparser.parse(resp.text)

        if not feed.entries:
            print(f"  ⚠ {name}: no entries found")
            return []

        for entry in feed.entries[:30]:
            title = getattr(entry, "title", "").strip()
            if not title:
                continue

            link = getattr(entry, "link", "").strip()
            if not link:
                continue

            summary = _extract_summary(entry)
            content = _extract_content(entry)
            published = _parse_date(entry)

            # Use content if summary is too short
            effective_summary = summary if len(summary) > 50 else content[:500] if content else summary

            news_id = _make_id(link, title)

            items.append({
                "id": news_id,
                "title": title,
                "summary": effective_summary,
                "link": link,
                "source": name,
                "lang": feed_config.get("lang", "en"),
                "category": feed_config.get("category", "general"),
                "published_at": published,
                "fetched_at": time.time(),
            })

        print(f"  ✓ {name}: {len(items)} items")

    except httpx.TimeoutException:
        print(f"  ⏱ {name}: timeout")
    except Exception as e:
        print(f"  ✗ {name}: {e}")

    return items


def _deduplicate(items: list) -> list:
    """Remove duplicate/similar news items."""
    if not items:
        return []

    unique = []
    seen_titles = []

    for item in items:
        title = item["title"]
        is_dup = False
        for seen in seen_titles:
            if _is_similar(title, seen):
                is_dup = True
                break

        if not is_dup:
            unique.append(item)
            seen_titles.append(title)

    removed = len(items) - len(unique)
    if removed:
        print(f"  🔄 Deduplication: removed {removed} similar items")

    return unique


async def fetch_all_feeds() -> list:
    """Fetch all RSS feeds concurrently."""
    print(f"\n📡 Fetching {len(RSS_FEEDS)} feeds...")
    all_items = []

    async with httpx.AsyncClient(headers=HEADERS) as client:
        tasks = [fetch_feed(client, fc) for fc in RSS_FEEDS]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, list):
            all_items.extend(result)

    # Deduplicate across sources
    all_items = _deduplicate(all_items)

    return all_items


async def classify_items(items: list, use_llm: bool = True) -> list:
    """Classify all items using batch LLM classification."""
    if not use_llm:
        # Fast path: keyword-only classification
        from classifier import keyword_classify
        for item in items:
            cls = keyword_classify(item["title"], item.get("summary", ""))
            item["markets"] = ",".join(cls.get("markets", ["综合"]))
            item["sentiment"] = cls.get("sentiment", "neutral")
            item["impact_score"] = cls.get("impact_score", 50)
            item["tags"] = ",".join(cls.get("tags", []))
            item["is_highlight"] = 1 if cls.get("impact_score", 50) >= 60 else 0
        return items

    print(f"\n🧠 Classifying {len(items)} items...")

    # Prepare items for batch classification
    classify_inputs = [{"title": item["title"], "summary": item.get("summary", "")} for item in items]

    # Batch classify
    classifications = await classify_news_batch(classify_inputs)

    # Apply classifications
    for item, cls in zip(items, classifications):
        item["markets"] = ",".join(cls.get("markets", ["综合"]))
        item["sentiment"] = cls.get("sentiment", "neutral")
        item["impact_score"] = cls.get("impact_score", 50)
        item["tags"] = ",".join(cls.get("tags", []))
        item["is_highlight"] = 1 if cls.get("impact_score", 50) >= 60 else 0

    return items


def save_news(items: list) -> int:
    """Save news items to SQLite. Returns count of new items."""
    conn = sqlite3.connect(DB_PATH)
    new_count = 0

    for item in items:
        try:
            cursor = conn.execute("""
                INSERT OR IGNORE INTO news
                (id, title, summary, link, source, lang, category,
                 published_at, fetched_at, markets, sentiment, impact_score, tags, is_highlight,
                 title_zh, summary_zh)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item["id"], item["title"], item["summary"], item["link"],
                item["source"], item["lang"], item["category"],
                item["published_at"], item["fetched_at"],
                item.get("markets", ""), item.get("sentiment", "neutral"),
                item.get("impact_score", 0), item.get("tags", ""),
                item.get("is_highlight", 0),
                item.get("title_zh"), item.get("summary_zh"),
            ))
            if cursor.rowcount > 0:
                new_count += 1
        except sqlite3.IntegrityError:
            pass

    conn.commit()
    conn.close()
    return new_count


def get_news(limit=100, offset=0, market=None, sentiment=None, source=None,
             highlight_only=False, search=None, sort="impact", hours=24) -> list:
    """Query news from database with filters and optional search."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    conditions = []
    params = []

    # 默认只显示最近 N 小时的新闻
    if hours:
        cutoff = time.time() - hours * 3600
        conditions.append("CAST(fetched_at AS REAL) > ?")
        params.append(cutoff)

    if market:
        conditions.append("markets LIKE ?")
        params.append(f"%{market}%")
    if sentiment:
        conditions.append("sentiment = ?")
        params.append(sentiment)
    if source:
        conditions.append("source = ?")
        params.append(source)
    if highlight_only:
        conditions.append("is_highlight = 1")
    if search:
        conditions.append("(title LIKE ? OR summary LIKE ? OR title_zh LIKE ? OR summary_zh LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%"])

    where = " AND ".join(conditions) if conditions else "1=1"

    if sort == "time":
        order = "is_highlight DESC, published_at DESC, fetched_at DESC"
    else:
        order = "is_highlight DESC, impact_score DESC, fetched_at DESC"

    query = f"""
        SELECT * FROM news
        WHERE {where}
        ORDER BY {order}
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])

    rows = conn.execute(query, params).fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_news_count(market=None, sentiment=None, source=None,
                   highlight_only=False, search=None, hours=24) -> int:
    """Get total count of news matching filters."""
    conn = sqlite3.connect(DB_PATH)

    conditions = []
    params = []

    # 默认只统计最近 N 小时的新闻
    if hours:
        cutoff = time.time() - hours * 3600
        conditions.append("CAST(fetched_at AS REAL) > ?")
        params.append(cutoff)

    if market:
        conditions.append("markets LIKE ?")
        params.append(f"%{market}%")
    if sentiment:
        conditions.append("sentiment = ?")
        params.append(sentiment)
    if source:
        conditions.append("source = ?")
        params.append(source)
    if highlight_only:
        conditions.append("is_highlight = 1")
    if search:
        conditions.append("(title LIKE ? OR summary LIKE ? OR title_zh LIKE ? OR summary_zh LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%"])

    where = " AND ".join(conditions) if conditions else "1=1"

    count = conn.execute(f"SELECT COUNT(*) FROM news WHERE {where}", params).fetchone()[0]
    conn.close()
    return count


def get_trending_topics() -> list:
    """Get trending topics by grouping news by tags."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Get recent news (last 24h)
    cutoff = time.time() - 86400
    rows = conn.execute(
        "SELECT tags, markets, sentiment FROM news WHERE fetched_at > ?",
        (cutoff,)
    ).fetchall()
    conn.close()

    # Count topic occurrences
    topic_counts = {}
    for row in rows:
        tags = (row["tags"] or "").split(",")
        for tag in tags:
            tag = tag.strip()
            if tag and tag not in ("A股", "港股", "美股", "币圈", "综合"):
                if tag not in topic_counts:
                    topic_counts[tag] = {"count": 0, "bullish": 0, "bearish": 0, "neutral": 0}
                topic_counts[tag]["count"] += 1
                sentiment = row["sentiment"] or "neutral"
                topic_counts[tag][sentiment] = topic_counts[tag].get(sentiment, 0) + 1

    # Sort by count
    topics = [
        {"topic": k, **v}
        for k, v in topic_counts.items()
        if v["count"] >= 2  # At least 2 mentions
    ]
    topics.sort(key=lambda x: x["count"], reverse=True)

    return topics[:20]


def get_stats() -> dict:
    """Get database statistics."""
    conn = sqlite3.connect(DB_PATH)
    total = conn.execute("SELECT COUNT(*) FROM news").fetchone()[0]
    highlights = conn.execute("SELECT COUNT(*) FROM news WHERE is_highlight = 1").fetchone()[0]

    market_counts = {}
    for row in conn.execute("SELECT markets FROM news"):
        for m in (row[0] or "").split(","):
            m = m.strip()
            if m:
                market_counts[m] = market_counts.get(m, 0) + 1

    source_counts = {}
    for row in conn.execute("SELECT source, COUNT(*) as cnt FROM news GROUP BY source ORDER BY cnt DESC"):
        source_counts[row[0]] = row[1]

    sentiment_counts = {}
    for row in conn.execute("SELECT sentiment, COUNT(*) FROM news GROUP BY sentiment"):
        sentiment_counts[row[0]] = row[1]

    conn.close()

    return {
        "total": total,
        "highlights": highlights,
        "markets": market_counts,
        "sources": source_counts,
        "sentiments": sentiment_counts,
    }


def get_sources() -> list:
    """Get unique sources from database."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT DISTINCT source FROM news ORDER BY source").fetchall()
    conn.close()
    return [row[0] for row in rows]


# ── Translation ─────────────────────────────────────────────

def _is_english(text: str) -> bool:
    """Check if text is English (>50% ASCII letters)."""
    if not text:
        return False
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    ascii_letters = [c for c in letters if ord(c) < 128]
    return len(ascii_letters) / len(letters) > 0.5


async def _translate_batch(items: list[dict]) -> dict:
    """Translate a batch of English news items to Chinese (with classification).
    items: list of {"id": str, "title": str, "summary": str}
    Returns: {id: {"title_zh": str, "summary_zh": str, "markets": [...], ...}}
    """
    if not items:
        return {}

    items_text = ""
    for i, item in enumerate(items):
        title = item["title"][:200]
        summary = item.get("summary", "")[:400]
        items_text += f"\n[{i}] ID: {item['id']}\nTitle: {title}\nSummary: {summary}\n"

    prompt = f"""你是一个金融新闻翻译助手。请将以下{len(items)}条英文新闻翻译成中文。

同时分析每条新闻的市场影响（分类）。

新闻列表：
{items_text}

请返回一个 JSON 数组，每个元素包含：
- index: 新闻序号
- title_zh: 中文标题（简洁准确）
- summary_zh: 中文摘要（100字以内）
- markets: 受影响的市场数组，从 ["A股","港股","美股","币圈","综合"] 中选择
- sentiment: 情绪 "bullish"/"bearish"/"neutral"
- impact_score: 影响力评分 0-100（50=一般新闻，70+=重要，90+=重大）
- tags: 主题标签数组（如 ["AI","货币政策","贸易"]）

只返回 JSON 数组，不要其他文字。"""

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://ai-news-aggregator.local",
                },
                json={
                    "model": OPENROUTER_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 4000,
                },
            )

            if resp.status_code != 200:
                print(f"  ⚠ Translation API error: {resp.status_code} {resp.text[:200]}")
                return {}

            data = resp.json()
            content = data["choices"][0]["message"]["content"]

            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if not json_match:
                print(f"  ⚠ Translation response not JSON: {content[:200]}")
                return {}

            results = json.loads(json_match.group())

            out = {}
            for r in results:
                idx = r.get("index", 0)
                if 0 <= idx < len(items):
                    item_id = items[idx]["id"]
                    out[item_id] = {
                        "title_zh": r.get("title_zh", ""),
                        "summary_zh": r.get("summary_zh", ""),
                        "markets": r.get("markets", ["综合"]),
                        "sentiment": r.get("sentiment", "neutral"),
                        "impact_score": max(0, min(100, int(r.get("impact_score", 50)))),
                        "tags": r.get("tags", []),
                    }
            return out

    except Exception as e:
        print(f"  ⚠ Translation failed: {e}")
        return {}


async def _translate_existing_english():
    """Translate existing English news in DB that haven't been translated yet."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, title, summary FROM news WHERE lang = 'en' AND title_zh IS NULL"
    ).fetchall()
    conn.close()

    if not rows:
        return

    items = [{"id": r["id"], "title": r["title"], "summary": r["summary"] or ""} for r in rows]
    print(f"\n🌐 Translating {len(items)} existing English items...")

    BATCH = 10
    all_translations = {}
    for i in range(0, len(items), BATCH):
        batch = items[i:i + BATCH]
        result = await _translate_batch(batch)
        all_translations.update(result)
        if i + BATCH < len(items):
            await asyncio.sleep(1)  # Rate limit

    # Apply translations
    conn = sqlite3.connect(DB_PATH)
    applied = 0
    for news_id, t in all_translations.items():
        conn.execute(
            "UPDATE news SET title_zh = ?, summary_zh = ? WHERE id = ?",
            (t.get("title_zh"), t.get("summary_zh"), news_id),
        )
        applied += 1
    conn.commit()
    conn.close()
    print(f"  ✓ Applied {applied} translations")


async def refresh_news(use_llm: bool = True) -> dict:
    """Full refresh cycle: fetch → classify → translate → save."""
    init_db()
    items = await fetch_all_feeds()

    # Separate English and Chinese items
    en_items = [it for it in items if _is_english(it.get("title", ""))]
    zh_items = [it for it in items if not _is_english(it.get("title", ""))]

    # Classify Chinese items normally
    if zh_items:
        zh_items = await classify_items(zh_items, use_llm=use_llm)

    # Translate + classify English items in one LLM call
    en_translations = {}
    if en_items and use_llm:
        print(f"\n🌐 Translating + classifying {len(en_items)} English items...")
        BATCH = 10
        for i in range(0, len(en_items), BATCH):
            batch = en_items[i:i + BATCH]
            result = await _translate_batch(batch)
            en_translations.update(result)
            if i + BATCH < len(en_items):
                await asyncio.sleep(1)

    # Apply translations + classifications to English items
    for item in en_items:
        t = en_translations.get(item["id"], {})
        item["title_zh"] = t.get("title_zh")
        item["summary_zh"] = t.get("summary_zh")
        if t.get("markets"):
            item["markets"] = ",".join(t["markets"])
            item["sentiment"] = t.get("sentiment", "neutral")
            item["impact_score"] = t.get("impact_score", 50)
            item["tags"] = ",".join(t.get("tags", []))
            item["is_highlight"] = 1 if t.get("impact_score", 50) >= 60 else 0
        else:
            # Fallback: keyword classify
            from classifier import keyword_classify
            cls = keyword_classify(item["title"], item.get("summary", ""))
            item["markets"] = ",".join(cls.get("markets", ["综合"]))
            item["sentiment"] = cls.get("sentiment", "neutral")
            item["impact_score"] = cls.get("impact_score", 50)
            item["tags"] = ",".join(cls.get("tags", []))
            item["is_highlight"] = 1 if cls.get("impact_score", 50) >= 60 else 0

    # Merge and save
    all_items = en_items + zh_items
    new_count = save_news(all_items)

    # Also translate any existing untranslated items in DB
    if use_llm:
        await _translate_existing_english()

    stats = get_stats()
    return {
        "fetched": len(all_items),
        "new": new_count,
        "stats": stats,
    }


def cleanup_old_news(keep_hours=48):
    """Delete news older than keep_hours to keep DB lean."""
    conn = sqlite3.connect(DB_PATH)
    cutoff = time.time() - keep_hours * 3600
    cursor = conn.execute("DELETE FROM news WHERE CAST(fetched_at AS REAL) < ?", (cutoff,))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    if deleted > 0:
        print(f"🗑 Cleaned up {deleted} old news items")
    return deleted


async def translate_untranslated() -> int:
    """Translate existing untranslated English items. Returns count translated."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Find English items without translation
    rows = conn.execute("""
        SELECT id, title, summary FROM news
        WHERE title_zh IS NULL
        AND title IS NOT NULL
        AND title != ''
        ORDER BY fetched_at DESC
        LIMIT 50
    """).fetchall()
    conn.close()

    if not rows:
        return 0

    # Filter to English items only
    en_items = []
    for row in rows:
        if _is_english(row["title"]):
            en_items.append(dict(row))

    if not en_items:
        return 0

    # Translate in batches
    translated = 0
    batch_size = 10
    for i in range(0, len(en_items), batch_size):
        batch = en_items[i : i + batch_size]
        translations = await _translate_batch(batch)
        if translations:
            conn = sqlite3.connect(DB_PATH)
            for item_id, tr in translations.items():
                conn.execute(
                    "UPDATE news SET title_zh=?, summary_zh=? WHERE id=?",
                    (tr.get("title"), tr.get("summary"), item_id),
                )
            conn.commit()
            conn.close()
            translated += len(translations)

    return translated
