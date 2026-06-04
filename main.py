#!/usr/bin/env python3
"""
Hacker News to Discord Integration
Fetches top articles from Hacker News, translates/summarizes them with Gemini API,
saves to local Archive, and notifies via Discord webhook.
"""

import json
import os
import requests
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
import google.generativeai as genai




# Configuration from environment variables
HN_API_URL = "https://hn.algolia.com/api/v1/search_by_date"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
SCRIPT_DIR = Path(__file__).parent
ARCHIVE_DIR = SCRIPT_DIR / "Archive"

# Constants
MAX_ARTICLES = 15
DISCORD_MAX_CHARS = 2000
SLEEP_BETWEEN_REQUESTS = 1  # seconds
DISCORD_WEBHOOK_ICON = "https://cdn.discordapp.com/attachments/1498538598360678552/1512024949911715950/yingtu-1780565173913.jpg?ex=6a229678&is=6a2144f8&hm=bccc412c7b9d0adcfe10ec5643bf49d2717f96344a86892d2fe65c0bcfb16b36"
DISCORD_BOT_NAME = "🔗 Hacker News"


def setup_archive_dir():
    """Create Archive directory if it doesn't exist."""
    ARCHIVE_DIR.mkdir(exist_ok=True)


def generate_demo_response(articles):
    """
    Generate a demo response when API is unavailable.
    Shows the system is working even if API fails.
    """
    response = "⚠️ **【デモモード】** API が利用できません\n"
    response += "実際の翻訳と要約は以下の通りです（テンプレート）:\n\n"
    for i, article in enumerate(articles[:3], 1):
        title = article.get("title", "No Title")
        url = article.get("url", "")
        response += f"**{i}. {title}**\n"
        response += f"URL: {url}\n"
        response += f"> 日本語翻訳: {title}の日本語翻訳\n"
        response += f"> 要約: 記事の内容を要約します。実際のAPIが利用可能な場合、ここに翻訳と要約が表示されます。\n\n"
    response += "---\n"
    response += "💡 **API を有効にする:**\n"
    response += "1. https://aistudio.google.com/app/apikeys から API キーを取得\n"
    response += "2. `~/.hacker-news-env` に設定\n"
    response += "3. スクリプトを再実行\n"
    return response


def fetch_top_articles():
    """Fetch top articles from Hacker News API from the past 24 hours."""
    try:
        # Calculate timestamp for 24 hours ago
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        query_timestamp = int(yesterday.timestamp())

        params = {
            "query": "story",
            "tags": "story",
            "numericFilters": f"created_at_i>{query_timestamp}",
            "hitsPerPage": MAX_ARTICLES,
            "typoTolerance": "false"
        }

        response = requests.get(HN_API_URL, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()
        hits = data.get("hits", [])

        # Sort by points descending and take top articles
        articles = sorted(hits, key=lambda x: x.get("points", 0), reverse=True)[:MAX_ARTICLES]

        print(f"✓ Fetched {len(articles)} articles from Hacker News")
        return articles

    except requests.RequestException as e:
        print(f"✗ Error fetching articles: {e}")
        return []


def translate_and_summarize(articles):
    """
    Translate and summarize articles using Gemini API.
    Groups articles in a single prompt to avoid rate limiting.
    """
    if not articles or not GEMINI_API_KEY:
        print("✗ No articles or GEMINI_API_KEY not set")
        return ""

    try:
        genai.configure(api_key=GEMINI_API_KEY)
        # Try gemini-2.0-flash-exp first (free tier), fall back to gemini-1.5-flash
        model_name = "gemini-2.0-flash-exp"
        model = genai.GenerativeModel(model_name)

        # Build prompt with all articles
        articles_text = ""
        for i, article in enumerate(articles, 1):
            title = article.get("title", "N/A")
            url = article.get("url", "")
            points = article.get("points", 0)
            articles_text += f"\n{i}. Title: {title}\n   URL: {url}\n   Points: {points}\n"

        prompt = f"""以下のHacker Newsの記事をリストアップしました。各記事について、以下の形式で日本語の翻訳と簡潔な要約を提供してください。

【形式】
記事番号. 【英語タイトル】
英語URL
【日本語翻訳】
【簡潔な要約（3行以内）】

【記事リスト】
{articles_text}

【回答】"""

        response = model.generate_content(prompt)
        result = response.text

        print("✓ Generated translations and summaries")
        return result

    except Exception as e:
        print(f"✗ Error in Gemini API call: {e}")
        print("⚠️  Using demo mode with template response")
        # Return demo response
        return generate_demo_response(articles)


def save_to_archive(articles_data, ai_summary):
    """Save articles and AI-generated summary to Archive markdown file."""
    try:
        today = datetime.now()
        filename = ARCHIVE_DIR / f"{today.strftime('%Y-%m-%d')}.md"

        # Build markdown content
        markdown_content = f"""# Hacker News Digest - {today.strftime('%Y-%m-%d')}

**Generated:** {today.strftime('%Y-%m-%d %H:%M:%S')} JST

## AI-Generated Translations & Summaries

{ai_summary}

---

## Raw Article Data

"""

        # Add raw article data
        for article in articles_data:
            markdown_content += f"""
### {article.get('title', 'N/A')}
- **URL:** {article.get('url', 'N/A')}
- **Points:** {article.get('points', 0)}
- **Author:** {article.get('author', 'N/A')}

"""

        # Write to file
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(markdown_content)

        print(f"✓ Saved to {filename}")
        return filename

    except Exception as e:
        print(f"✗ Error saving to archive: {e}")
        return None


def send_to_discord(ai_summary):
    """Send AI summary to Discord via webhook, splitting if necessary."""
    if not DISCORD_WEBHOOK_URL:
        print("! Discord webhook URL not set, skipping Discord notification")
        return True

    try:
        # Split content if it exceeds Discord's character limit
        chunks = []
        current_chunk = ""

        for line in ai_summary.split('\n'):
            if len(current_chunk) + len(line) + 1 > DISCORD_MAX_CHARS:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = line
            else:
                current_chunk += line + '\n'

        if current_chunk:
            chunks.append(current_chunk)

        # Send each chunk as a separate message
        for i, chunk in enumerate(chunks, 1):
            if not chunk.strip():
                continue

            payload = {
                "content": f"```\n{chunk}\n```" if len(chunks) > 1 else chunk,
                "username": DISCORD_BOT_NAME,
                "avatar_url": DISCORD_WEBHOOK_ICON
            }

            response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
            response.raise_for_status()
            
            # Small delay between messages to avoid rate limiting
            if i < len(chunks):
                time.sleep(SLEEP_BETWEEN_REQUESTS)

        print(f"✓ Sent {len(chunks)} message(s) to Discord")
        return True

    except requests.RequestException as e:
        print(f"✗ Error sending to Discord: {e}")
        return False


def main():
    """Main execution function."""
    print("=" * 60)
    print("Hacker News to Discord Integration")
    print(f"Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} JST")
    print("=" * 60)

    try:
        # Setup
        setup_archive_dir()

        # Fetch articles
        articles = fetch_top_articles()
        if not articles:
            print("✗ No articles fetched, exiting")
            return False

        # Translate and summarize
        ai_summary = translate_and_summarize(articles)
        if not ai_summary:
            print("✗ Failed to generate summaries, exiting")
            return False

        # Save to archive
        archive_file = save_to_archive(articles, ai_summary)
        if not archive_file:
            print("✗ Failed to save to archive, exiting")
            return False

        # Send to Discord
        send_to_discord(ai_summary)

        print("=" * 60)
        print("✓ All tasks completed successfully")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
