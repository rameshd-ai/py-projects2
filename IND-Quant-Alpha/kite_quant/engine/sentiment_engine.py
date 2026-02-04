"""
News fetch + FinBERT/VADER scoring; 24h blacklist on strong negative.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timedelta
from typing import Any

import requests

# Optional: FinBERT (heavy). Fallback: VADER + TextBlob
try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    VADER_AVAILABLE = True
except ImportError:
    VADER_AVAILABLE = False

try:
    from textblob import TextBlob
    TEXTBLOB_AVAILABLE = True
except ImportError:
    TEXTBLOB_AVAILABLE = False

# FinBERT optional (transformers + torch) — loaded lazily
_finbert_pipe = None


def _get_finbert():
    global _finbert_pipe, FINBERT_AVAILABLE
    if _finbert_pipe is not None:
        return _finbert_pipe
    try:
        from transformers import pipeline
        _finbert_pipe = pipeline("sentiment-analysis", model="ProsusAI/finbert")
        FINBERT_AVAILABLE = True
        return _finbert_pipe
    except Exception:
        return None


FINBERT_AVAILABLE = False  # set on first successful _get_finbert() call


def _score_vader(text: str) -> float:
    if not VADER_AVAILABLE:
        return _score_textblob(text)
    v = SentimentIntensityAnalyzer()
    s = v.polarity_scores(text)
    return s["compound"]


def _score_textblob(text: str) -> float:
    if not TEXTBLOB_AVAILABLE:
        return 0.0
    return float(TextBlob(text).sentiment.polarity)


def _score_finbert(text: str) -> float:
    pipe = _get_finbert()
    if pipe is None or not text.strip():
        return _score_vader(text)
    try:
        out = pipe(text[:512])[0]
        label = out.get("label", "").upper()
        score = out.get("score", 0.5)
        if "POSITIVE" in label:
            return score
        if "NEGATIVE" in label:
            return -score
        return 0.0
    except Exception:
        return _score_vader(text)


def score_headline(text: str, use_finbert: bool = True) -> float:
    """Single headline score in [-1, 1]. Prefer FinBERT when available."""
    if use_finbert and _get_finbert() is not None:
        return _score_finbert(text)
    return _score_vader(text)


def fetch_news(symbol: str, query: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
    """Fetch latest headlines (News API or fallback)."""
    api_key = os.getenv("NEWS_API_KEY")
    query = query or f"{symbol} stock NSE India"
    headlines = []

    if api_key:
        try:
            url = "https://newsapi.org/v2/everything"
            params = {
                "q": query,
                "apiKey": api_key,
                "pageSize": limit,
                "sortBy": "publishedAt",
                "language": "en",
            }
            r = requests.get(url, params=params, timeout=10)
            r.raise_for_status()
            data = r.json()
            for a in data.get("articles", [])[:limit]:
                title = (a.get("title") or "").strip()
                if title:
                    headlines.append({"title": title, "source": a.get("source", {}).get("name", "")})
        except Exception:
            pass

    if not headlines:
        headlines.append({"title": f"No news fetched for {symbol}", "source": "N/A"})

    return headlines


def aggregate_sentiment(headlines: list[dict[str, Any]], use_finbert: bool = True) -> tuple[float, bool]:
    """
    Score each headline, return (aggregate_score, blacklist_24h).
    Blacklist if strong negative (e.g. bad earnings, legal).
    """
    if not headlines:
        return 0.0, False
    scores = []
    blacklist = False
    negative_triggers = (
        r"earnings?\s*(miss|loss|fall|drop|plunge)",
        r"legal\s*(action|case|probe|investigation)",
        r"fraud|scam|default|bankruptcy",
        r"profit\s*warning|cut\s*guidance",
        r"sec\s*investigation|sebi\s*order",
    )
    for h in headlines:
        title = h.get("title", "")
        s = score_headline(title, use_finbert=use_finbert)
        scores.append(s)
        if s < -0.6:
            for pat in negative_triggers:
                if re.search(pat, title, re.I):
                    blacklist = True
                    break
    avg = sum(scores) / len(scores) if scores else 0.0
    return round(avg, 4), blacklist


def get_sentiment_for_symbol(symbol: str, limit: int = 10) -> dict[str, Any]:
    """Fetch news, score, return aggregate and blacklist."""
    headlines = fetch_news(symbol, limit=limit)
    score, blacklist = aggregate_sentiment(headlines)
    return {
        "symbol": symbol,
        "score": score,
        "blacklist_24h": blacklist,
        "headlines": headlines,
        "buy_ok": score > 0.2,
        "buy_strong": score > 0.7,
    }
