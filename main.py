#!/usr/bin/env python3
"""
Hacker News to Discord Integration
=================================

Fetches the top Hacker News stories from the past 24 hours, asks Gemini for a
Japanese translation + short summary of each, and posts a formatted message to
a Discord webhook.

Design note
-----------
The AI model is **only** trusted to return translation/summary text as
structured JSON. Everything that must be correct -- article titles, URLs,
points, message layout -- is built deterministically in Python from the Hacker
News API data. This avoids the whole class of "AI didn't follow the format"
bugs (missing titles, dropped URLs, broken formatting) that come from parsing
free-form model output with regexes.
"""

import json
import os
import re
import time
from datetime import datetime, timedelta, timezone

import requests
import google.generativeai as genai


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
HN_API_URL = "https://hn.algolia.com/api/v1/search_by_date"
HN_ITEM_URL = "https://news.ycombinator.com/item?id={id}"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# How many stories end up in the digest.
MAX_ARTICLES = int(os.getenv("HN_MAX_ARTICLES", "5"))
# How many recent stories to rank before picking the top `MAX_ARTICLES`.
# `search_by_date` returns newest-first, so we need a wide pool to find the
# genuinely popular stories instead of merely the most recent ones.
CANDIDATE_POOL = int(os.getenv("HN_CANDIDATE_POOL", "100"))
LOOKBACK_HOURS = int(os.getenv("HN_LOOKBACK_HOURS", "24"))

DISCORD_MAX_CHARS = 2000
SLEEP_BETWEEN_REQUESTS = 1  # seconds, to stay under Discord's webhook rate limit
HTTP_TIMEOUT = 15
MAX_RETRIES = 3

DISCORD_WEBHOOK_ICON = (
    "https://cdn.discordapp.com/attachments/1498538598360678552/1512024949911715950/"
    "yingtu-1780565173913.jpg?ex=6a229678&is=6a2144f8&hm="
    "bccc412c7b9d0adcfe10ec5643bf49d2717f96344a86892d2fe65c0bcfb16b36"
)
DISCORD_BOT_NAME = "🔗 Hacker News"

# A single connection-pooled session for all outbound HTTP.
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "hacker-news-to-discord/2.0"})


# --------------------------------------------------------------------------- #
# Hacker News
# --------------------------------------------------------------------------- #
def _normalize_article(hit):
    """Turn a raw Algolia hit into the flat dict the rest of the code uses.

    Crucially, `url` falls back to the Hacker News discussion permalink so that
    text posts (Show HN / Ask HN, which have no external URL) never end up with
    a missing link.
    """
    object_id = str(hit.get("objectID", ""))
    hn_url = HN_ITEM_URL.format(id=object_id) if object_id else ""
    external_url = (hit.get("url") or "").strip()

    return {
        "title": (hit.get("title") or "").strip(),
        "url": external_url or hn_url,          # never empty
        "external_url": external_url,           # may be empty for text posts
        "hn_url": hn_url,
        "points": hit.get("points") or 0,
        "author": hit.get("author") or "N/A",
        "num_comments": hit.get("num_comments") or 0,
        "object_id": object_id,
    }


def fetch_top_articles():
    """Fetch the top stories from the past `LOOKBACK_HOURS` hours.

    We pull a wide pool of recent stories and rank them by points locally, so
    the digest reflects the *most upvoted* stories rather than merely the newest
    ones.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    params = {
        # Empty query + tags=story means "all stories" (a non-empty query would
        # incorrectly restrict results to stories mentioning that word).
        "query": "",
        "tags": "story",
        "numericFilters": f"created_at_i>{int(cutoff.timestamp())}",
        "hitsPerPage": CANDIDATE_POOL,
    }

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = SESSION.get(HN_API_URL, params=params, timeout=HTTP_TIMEOUT)
            response.raise_for_status()
            hits = response.json().get("hits", [])

            # Keep only real stories that have a title, rank by points.
            articles = [_normalize_article(h) for h in hits if (h.get("title") or "").strip()]
            articles.sort(key=lambda a: a["points"], reverse=True)
            articles = articles[:MAX_ARTICLES]

            print(f"✓ Fetched {len(hits)} candidates, selected top {len(articles)} by points")
            return articles

        except requests.RequestException as e:
            last_error = e
            print(f"✗ HN fetch attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(2 ** attempt)

    print(f"✗ Giving up fetching articles: {last_error}")
    return []


# --------------------------------------------------------------------------- #
# Gemini: translation + summary (structured JSON only)
# --------------------------------------------------------------------------- #
def _extract_response_text(response):
    """Robustly pull text out of a Gemini response.

    `response.text` raises if the candidate finished for any reason other than
    STOP (e.g. MAX_TOKENS, SAFETY). In that case we still try to salvage
    whatever text parts are present.
    """
    try:
        text = response.text
        if text:
            return text
    except Exception:
        pass

    parts_text = []
    for candidate in getattr(response, "candidates", None) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", None) or []:
            piece = getattr(part, "text", None)
            if piece:
                parts_text.append(piece)
    return "".join(parts_text)


def _parse_json_array(raw):
    """Parse a JSON array out of the model output, tolerating code fences."""
    if not raw:
        return None
    text = raw.strip()
    # Strip ```json ... ``` fences if present.
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Last resort: grab the outermost [ ... ] block.
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, list) else None


def translate_and_summarize(articles):
    """Attach `translation` and `summary` (list of lines) to each article.

    Returns the same list, mutated in place. Articles the model failed to cover
    keep a graceful placeholder so the digest still shows the title and URL --
    a partial result is always better than dropping an article entirely.
    """
    for article in articles:
        article.setdefault("translation", "")
        article.setdefault("summary", [])

    if not articles or not GEMINI_API_KEY:
        print("✗ No articles or GEMINI_API_KEY not set; skipping translation")
        return articles

    articles_block = "\n".join(
        f'{i}. {a["title"]}' for i, a in enumerate(articles, 1)
    )
    prompt = f"""あなたは技術ニュースの翻訳者です。以下のHacker Newsの記事タイトルについて、
それぞれ日本語タイトル訳と、内容の簡潔な要約（1〜3行）を作成してください。

出力は **JSON配列のみ** とし、各要素は次の形式にしてください:
{{"index": <記事番号(整数)>, "translation": "<日本語タイトル訳>", "summary": ["要約1行目", "要約2行目"]}}

- index は下記のリスト番号と必ず一致させること。
- summary は各行を配列要素とし、1〜3要素にすること。
- 記事タイトルのみが情報源です。推測を交えて構いませんが、簡潔にすること。
- JSON以外のテキスト（前置き・コードフェンス等）は一切出力しないこと。

【記事リスト】
{articles_block}
"""

    generation_config = {
        "response_mime_type": "application/json",
        "temperature": 0.3,
        "max_output_tokens": 8192,
    }

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel(GEMINI_MODEL, generation_config=generation_config)
            response = model.generate_content(prompt)
            parsed = _parse_json_array(_extract_response_text(response))

            if not parsed:
                raise ValueError("model did not return a usable JSON array")

            # Map results back onto our articles by index.
            by_index = {}
            for item in parsed:
                if not isinstance(item, dict):
                    continue
                idx = item.get("index")
                if isinstance(idx, str) and idx.isdigit():
                    idx = int(idx)
                if isinstance(idx, int) and 1 <= idx <= len(articles):
                    by_index[idx] = item

            filled = 0
            for i, article in enumerate(articles, 1):
                item = by_index.get(i)
                if not item:
                    continue
                translation = (item.get("translation") or "").strip()
                summary = item.get("summary") or []
                if isinstance(summary, str):
                    summary = [summary]
                summary = [str(s).strip() for s in summary if str(s).strip()]
                if translation:
                    article["translation"] = translation
                if summary:
                    article["summary"] = summary
                if translation or summary:
                    filled += 1

            print(f"✓ Translated {filled}/{len(articles)} articles (attempt {attempt})")
            if filled:
                return articles
            raise ValueError("no articles were filled")

        except Exception as e:  # noqa: BLE001 - genai raises a variety of errors
            last_error = e
            print(f"✗ Gemini attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(2 ** attempt)

    print(f"⚠️  Translation unavailable ({last_error}); posting titles/links only")
    return articles


# --------------------------------------------------------------------------- #
# Formatting (deterministic)
# --------------------------------------------------------------------------- #
def _format_article_block(index, article):
    """Render one article as a Discord-ready text block.

    URLs are wrapped in <> so Discord does not generate large link embeds.
    """
    title = article["title"] or "(no title)"
    url = article["url"]
    lines = [f"**{index}. [{title}](<{url}>)**"]

    translation = article.get("translation")
    if translation:
        lines.append(f"> 🇯🇵 **{translation}**")

    for summary_line in article.get("summary", []):
        # Normalise any leading bullet the model may have added.
        clean = summary_line.lstrip("・-*• ").strip()
        if clean:
            lines.append(f"> ・{clean}")

    if not translation and not article.get("summary"):
        lines.append("> （翻訳は利用できませんでした）")

    meta = f"　▲ {article['points']} points"
    if article.get("hn_url"):
        meta += f" ・ [💬 {article['num_comments']} comments](<{article['hn_url']}>)"
    lines.append(meta)

    return "\n".join(lines)


def build_discord_messages(articles, header):
    """Build the list of message strings to post, each within Discord's limit.

    Article blocks are never split across messages, so an article's title,
    translation and summary always stay together.
    """
    blocks = [_format_article_block(i, a) for i, a in enumerate(articles, 1)]

    messages = []
    current = header
    for block in blocks:
        candidate = f"{current}\n\n{block}" if current else block
        if len(candidate) > DISCORD_MAX_CHARS and current:
            messages.append(current)
            current = block
        else:
            current = candidate
    if current:
        messages.append(current)
    return messages


# --------------------------------------------------------------------------- #
# Discord
# --------------------------------------------------------------------------- #
def _post_discord(content):
    """POST a single message to the webhook, retrying on transient failures."""
    payload = {
        "content": content,
        "username": DISCORD_BOT_NAME,
        "avatar_url": DISCORD_WEBHOOK_ICON,
    }
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = SESSION.post(DISCORD_WEBHOOK_URL, json=payload, timeout=HTTP_TIMEOUT)
            # Respect Discord's rate-limit backoff if we get one.
            if response.status_code == 429:
                retry_after = response.json().get("retry_after", SLEEP_BETWEEN_REQUESTS)
                print(f"! Rate limited, waiting {retry_after}s")
                time.sleep(float(retry_after) + 0.5)
                continue
            response.raise_for_status()
            return True
        except requests.RequestException as e:
            print(f"✗ Discord post attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(2 ** attempt)
    return False


def send_to_discord(articles):
    """Post the digest to Discord. Returns True on success."""
    if not DISCORD_WEBHOOK_URL:
        print("! Discord webhook URL not set, skipping Discord notification")
        return True

    header = f"📰 **Hacker News Digest** - {datetime.now().strftime('%Y-%m-%d')}"
    messages = build_discord_messages(articles, header)

    sent = 0
    for i, message in enumerate(messages):
        if not _post_discord(message):
            print(f"✗ Failed to send message {i + 1}/{len(messages)}")
            return False
        sent += 1
        if i < len(messages) - 1:
            time.sleep(SLEEP_BETWEEN_REQUESTS)

    print(f"✓ Sent {sent} message(s) to Discord")
    return True


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def main():
    print("=" * 60)
    print("Hacker News to Discord Integration")
    print(f"Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} JST")
    print("=" * 60)

    try:
        articles = fetch_top_articles()
        if not articles:
            print("✗ No articles fetched, exiting")
            return False

        translate_and_summarize(articles)

        ok = send_to_discord(articles)

        print("=" * 60)
        print("✓ All tasks completed" if ok else "⚠️  Completed with Discord errors")
        print("=" * 60)
        return ok

    except Exception as e:  # noqa: BLE001 - top-level safety net
        print(f"✗ Unexpected error: {e}")
        return False


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
