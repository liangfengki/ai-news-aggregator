import json
import hashlib
import sqlite3
import re
import time
import os
from typing import Optional

import httpx

from sources import MARKET_KEYWORDS, BULLISH_KEYWORDS, BEARISH_KEYWORDS

# ── LLM Configuration ──────────────────────────────────────
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = "deepseek/deepseek-chat-v3-0324"

DB_PATH = "data/news.db"

# ── Classification Cache ───────────────────────────────────

def _cache_key(title: str, summary: str) -> str:
    raw = f"{title}|||{summary}"
    return hashlib.md5(raw.encode()).hexdigest()


def init_classifier_cache():
    """Create classification cache table if not exists."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS classification_cache (
            cache_key TEXT PRIMARY KEY,
            markets TEXT,
            sentiment TEXT,
            impact_score INTEGER,
            tags TEXT,
            reasoning TEXT,
            classified_at REAL
        )
    """)
    conn.commit()
    conn.close()


def get_cached_classification(title: str, summary: str) -> Optional[dict]:
    """Get cached classification result."""
    key = _cache_key(title, summary)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM classification_cache WHERE cache_key = ?", (key,)
    ).fetchone()
    conn.close()
    if row:
        return {
            "markets": row["markets"].split(",") if row["markets"] else ["综合"],
            "sentiment": row["sentiment"],
            "impact_score": row["impact_score"],
            "tags": row["tags"].split(",") if row["tags"] else [],
            "reasoning": row["reasoning"] or "",
        }
    return None


def cache_classification(title: str, summary: str, result: dict):
    """Cache a classification result."""
    key = _cache_key(title, summary)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT OR REPLACE INTO classification_cache
        (cache_key, markets, sentiment, impact_score, tags, reasoning, classified_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        key,
        ",".join(result.get("markets", [])),
        result.get("sentiment", "neutral"),
        result.get("impact_score", 50),
        ",".join(result.get("tags", [])),
        result.get("reasoning", ""),
        time.time(),
    ))
    conn.commit()
    conn.close()


# ── LLM Classification ─────────────────────────────────────

async def llm_classify_batch(items: list[dict]) -> list[dict]:
    """
    Classify a batch of news items using LLM.
    items: list of {"title": str, "summary": str}
    Returns: list of classification dicts
    """
    if not items:
        return []

    # Build prompt
    items_text = ""
    for i, item in enumerate(items):
        title = item.get("title", "")[:200]
        summary = item.get("summary", "")[:300]
        items_text += f"\n[{i}] 标题: {title}\n摘要: {summary}\n"

    prompt = f"""你是一个金融新闻分析助手。请分析以下{len(items)}条新闻，为每条返回结构化分类结果。

新闻列表：
{items_text}

请返回一个 JSON 数组，每个元素包含：
- index: 新闻序号
- markets: 受影响的市场数组，从 ["A股","港股","美股","币圈","综合"] 中选择
- sentiment: 情绪 "bullish"/"bearish"/"neutral"
- impact_score: 影响力评分 0-100（50=一般新闻，70+=重要，90+=重大）
- tags: 主题标签数组（如 ["AI","货币政策","贸易"]）
- reasoning: 一句话分析理由

只返回 JSON 数组，不要其他文字。"""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
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
                    "max_tokens": 2000,
                },
            )

            if resp.status_code != 200:
                print(f"  ⚠ LLM API error: {resp.status_code} {resp.text[:200]}")
                return []

            data = resp.json()
            content = data["choices"][0]["message"]["content"]

            # Extract JSON from response (handle markdown code blocks)
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if not json_match:
                print(f"  ⚠ LLM response not JSON: {content[:200]}")
                return []

            results = json.loads(json_match.group())

            # Normalize results
            normalized = []
            for r in results:
                normalized.append({
                    "markets": r.get("markets", ["综合"]),
                    "sentiment": r.get("sentiment", "neutral"),
                    "impact_score": max(0, min(100, int(r.get("impact_score", 50)))),
                    "tags": r.get("tags", []),
                    "reasoning": r.get("reasoning", ""),
                })

            return normalized

    except Exception as e:
        print(f"  ⚠ LLM classification failed: {e}")
        return []


# ── Keyword Classification (fallback) ──────────────────────

def keyword_classify(title: str, summary: str = "") -> dict:
    """
    Keyword-based classification (fallback).
    """
    text = f"{title} {summary}".lower()
    text_original = f"{title} {summary}"

    # Detect relevant markets
    markets = []
    for market, keywords in MARKET_KEYWORDS.items():
        for kw in keywords["zh"]:
            if kw in text_original:
                markets.append(market)
                break
        if market not in markets:
            for kw in keywords["en"]:
                if kw.lower() in text:
                    markets.append(market)
                    break

    # Detect sentiment
    bullish_score = 0
    bearish_score = 0

    for kw in BULLISH_KEYWORDS["zh"]:
        if kw in text_original:
            bullish_score += 1
    for kw in BULLISH_KEYWORDS["en"]:
        if kw.lower() in text:
            bullish_score += 1

    for kw in BEARISH_KEYWORDS["zh"]:
        if kw in text_original:
            bearish_score += 1
    for kw in BEARISH_KEYWORDS["en"]:
        if kw.lower() in text:
            bearish_score += 1

    if bullish_score > bearish_score:
        sentiment = "bullish"
    elif bearish_score > bullish_score:
        sentiment = "bearish"
    else:
        sentiment = "neutral"

    base_score = min(len(markets) * 15, 40)
    sentiment_bonus = min(max(bullish_score, bearish_score) * 10, 40)
    impact_score = min(base_score + sentiment_bonus + 20, 100)

    if not markets:
        impact_score = max(impact_score - 20, 10)

    tags = list(markets)
    if sentiment != "neutral":
        tags.append("看涨" if sentiment == "bullish" else "看跌")

    topic_patterns = [
        (r"(AI|人工智能|大模型|GPT|LLM|芯片|半导体)", "AI/芯片"),
        (r"(美联储|降息|加息|利率|货币政策)", "货币政策"),
        (r"(关税|贸易战|制裁|出口管制)", "贸易"),
        (r"(IPO|上市|融资|收购|并购)", "资本市场"),
        (r"(油价|原油|天然气|能源)", "能源"),
        (r"(黄金|金价|贵金属)", "黄金"),
        (r"(房地产|楼市|房价)", "房地产"),
    ]
    for pattern, tag in topic_patterns:
        if re.search(pattern, text_original):
            tags.append(tag)

    return {
        "markets": markets if markets else ["综合"],
        "sentiment": sentiment,
        "impact_score": impact_score,
        "tags": list(set(tags)),
        "reasoning": "关键词匹配",
    }


# ── Unified Classification Interface ───────────────────────

async def classify_news(title: str, summary: str = "") -> dict:
    """
    Classify news for market impact. Tries LLM first, falls back to keywords.
    Returns: {
        "markets": ["A股", "港股", ...],
        "sentiment": "bullish" | "bearish" | "neutral",
        "impact_score": 0-100,
        "tags": ["tag1", "tag2"],
        "reasoning": "..."
    }
    """
    # Check cache first
    cached = get_cached_classification(title, summary)
    if cached:
        return cached

    # Try LLM classification
    results = await llm_classify_batch([{"title": title, "summary": summary}])
    if results:
        result = results[0]
        cache_classification(title, summary, result)
        return result

    # Fallback to keywords
    result = keyword_classify(title, summary)
    cache_classification(title, summary, result)
    return result


async def classify_news_batch(items: list[dict]) -> list[dict]:
    """
    Classify a batch of news items efficiently.
    Uses cache for known items, LLM for new ones, keywords as final fallback.
    items: list of {"title": str, "summary": str}
    """
    results = [None] * len(items)
    uncached_indices = []
    uncached_items = []

    # Check cache for each item
    for i, item in enumerate(items):
        cached = get_cached_classification(item["title"], item.get("summary", ""))
        if cached:
            results[i] = cached
        else:
            uncached_indices.append(i)
            uncached_items.append(item)

    # Batch classify uncached items (10 at a time)
    BATCH_SIZE = 10
    for batch_start in range(0, len(uncached_items), BATCH_SIZE):
        batch = uncached_items[batch_start:batch_start + BATCH_SIZE]
        batch_indices = uncached_indices[batch_start:batch_start + BATCH_SIZE]

        llm_results = await llm_classify_batch(batch)

        for j, idx in enumerate(batch_indices):
            if j < len(llm_results):
                results[idx] = llm_results[j]
            else:
                # Fallback to keywords
                item = batch[j] if j < len(batch) else uncached_items[batch_start + j]
                results[idx] = keyword_classify(
                    item.get("title", ""),
                    item.get("summary", "")
                )

            # Cache the result
            cache_classification(
                items[idx]["title"],
                items[idx].get("summary", ""),
                results[idx],
            )

    return results
