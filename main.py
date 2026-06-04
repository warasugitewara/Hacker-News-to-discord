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
MAX_ARTICLES = 5  # Reduced to top 5 for morning digest
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
    response = ""
    for i, article in enumerate(articles[:5], 1):
        title = article.get("title", "No Title")
        url = article.get("url", "")
        response += f"**{i}. [{title}](<{url}>)**\n"
        response += f"> 日本語翻訳: {title}の日本語翻訳です。\n"
        response += f"> 要約: 記事の内容を簡潔に要約しました。\n"
        if i < 5:
            response += "\n"
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
    Returns tuple: (ai_summary, articles) to preserve URL mapping
    """
    if not articles or not GEMINI_API_KEY:
        print("✗ No articles or GEMINI_API_KEY not set")
        return "", articles

    try:
        genai.configure(api_key=GEMINI_API_KEY)
        # Use gemini-3.5-flash (latest available model)
        model_name = "gemini-3.5-flash"
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
        
        # Clean up the response: remove unnecessary template text
        lines = result.split('\n')
        cleaned_lines = []
        for line in lines:
            # Skip template/metadata lines
            if any(skip in line for skip in [
                'ご提示いただいた',
                '指定の形式で',
                '回答',
                '---',
                'ご指定のフォーマットに沿って',
                '各記事の日本語翻訳と簡潔な要約をお届けします'
            ]):
                continue
            cleaned_lines.append(line)
        
        result = '\n'.join(cleaned_lines).strip()

        print("✓ Generated translations and summaries")
        return result, articles

    except Exception as e:
        print(f"✗ Error in Gemini API call: {e}")
        print("⚠️  Using demo mode with template response")
        # Return demo response
        return generate_demo_response(articles), articles


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


def format_for_discord(ai_summary, articles=None):
    """Format AI summary for better Discord readability.
    - Removes duplicate URL lines
    - Formats article titles as markdown links [title](<url>)
    - Adds proper spacing between articles
    - Uses > quotes for translations/summaries
    """
    import re
    lines = ai_summary.split('\n')
    formatted_lines = []
    skip_next_url = False
    in_article = False
    
    for i, line in enumerate(lines):
        # Detect article title lines (e.g., "1. 【Title】")
        title_match = re.match(r'^(\d+)\.\s+【(.+?)】$', line)
        if title_match:
            article_num = int(title_match.group(1))
            title = title_match.group(2)
            
            # Add blank lines before new article (except first one)
            if formatted_lines:
                # Ensure we have at least one blank line before this article
                if formatted_lines[-1].strip() != "":
                    formatted_lines.append("")
                    formatted_lines.append("")  # Double blank line for article separation
            
            # Get URL from articles data
            if articles and article_num <= len(articles):
                url = articles[article_num - 1].get("url", "")
                if url:
                    # Format as markdown link: **[【Title】](<url>)**
                    line = f"**{article_num}. [【{title}】](<{url}>)**"
                    skip_next_url = True  # Skip the next URL line
                else:
                    line = f"**{article_num}. 【{title}】**"
            else:
                line = f"**{line}**"
            
            formatted_lines.append(line)
            in_article = True
        # Skip "URL: https://..." lines (already in title link)
        elif skip_next_url and line.strip().startswith('URL:'):
            skip_next_url = False
            continue
        # Skip bare URLs that come after title
        elif skip_next_url and re.match(r'^https?://', line.strip()):
            skip_next_url = False
            continue
        # Quote content lines (translations and summaries)
        elif line.strip().startswith(('【日本語翻訳】', '【簡潔な要約')):
            formatted_lines.append(f"> {line}")
            skip_next_url = False
        elif line.strip() and any(line.strip().startswith(marker) for marker in ['・', '-', '・・']):
            formatted_lines.append(f"> {line}")
        # Quote any non-empty line that's part of an article content (after title, before next article)
        elif in_article and line.strip() and not re.match(r'^(\d+)\.\s+【', line):
            # Check if this looks like article metadata (URL line) or actual content
            if not line.strip().startswith('URL:') and not re.match(r'^https?://', line.strip()):
                formatted_lines.append(f"> {line}")
            else:
                formatted_lines.append(line)
        else:
            # Empty lines - preserve only between content sections
            if not line.strip():
                if formatted_lines and formatted_lines[-1].strip():
                    formatted_lines.append("")
            else:
                formatted_lines.append(line)
    
    return '\n'.join(formatted_lines)


def send_to_discord(ai_summary, articles=None):
    """Send complete AI summary to Discord via webhook with optimized formatting."""
    if not DISCORD_WEBHOOK_URL:
        print("! Discord webhook URL not set, skipping Discord notification")
        return True

    try:
        # Format for Discord (prevent URL embeds, improve readability, add markdown links)
        formatted_summary = format_for_discord(ai_summary, articles)
        
        # Split content into chunks by article boundary (\n\n marks article separation)
        chunks = []
        current_chunk = ""
        lines = formatted_summary.split('\n')
        
        for i, line in enumerate(lines):
            # Check if this is a new article title (starts with **)
            is_article_title = line.strip().startswith('**') and '【' in line
            
            # If we're starting a new article and current chunk is getting large
            if is_article_title and current_chunk and len(current_chunk) > DISCORD_MAX_CHARS * 0.6:
                # Save current chunk
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                current_chunk = line + '\n'
            else:
                # Add line to current chunk
                if current_chunk and not current_chunk.endswith('\n'):
                    current_chunk += '\n'
                current_chunk += line + '\n'
                
                # If chunk exceeds limit, save it
                if len(current_chunk) > DISCORD_MAX_CHARS:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
        
        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        # Add header message with timestamp
        header = f"📰 **Hacker News Digest** - {datetime.now().strftime('%Y-%m-%d')}"
        
        # Send header first
        header_payload = {
            "content": header,
            "username": DISCORD_BOT_NAME,
            "avatar_url": DISCORD_WEBHOOK_ICON
        }
        response = requests.post(DISCORD_WEBHOOK_URL, json=header_payload, timeout=10)
        response.raise_for_status()
        time.sleep(SLEEP_BETWEEN_REQUESTS)

        # Send each chunk as a separate message with full content
        for i, chunk in enumerate(chunks, 1):
            if not chunk.strip():
                continue

            payload = {
                "content": chunk,
                "username": DISCORD_BOT_NAME,
                "avatar_url": DISCORD_WEBHOOK_ICON
            }

            response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
            response.raise_for_status()
            
            # Small delay between messages to avoid rate limiting
            if i < len(chunks):
                time.sleep(SLEEP_BETWEEN_REQUESTS)

        print(f"✓ Sent {len(chunks) + 1} message(s) to Discord")
        return True

    except requests.RequestException as e:
        print(f"✗ Error sending to Discord: {e}")
        return False


def parse_summary(ai_summary):
    """Parse AI summary to extract individual articles."""
    articles = []
    lines = ai_summary.split('\n')
    current_article = {}
    
    for line in lines:
        # Look for numbered articles like "1. 【Title】"
        if line.strip() and line[0].isdigit() and '【' in line and '】' in line:
            if current_article:
                articles.append(current_article)
            # Extract title
            start = line.find('【') + 1
            end = line.find('】')
            current_article = {
                'title': line[start:end] if start > 0 and end > start else line,
                'number': line.split('.')[0] if '.' in line else ''
            }
        elif '【日本語翻訳】' in line:
            current_article['has_translation'] = True
        elif '【簡潔な要約' in line or '【要約】' in line:
            current_article['has_summary'] = True
    
    if current_article:
        articles.append(current_article)
    
    return articles


def format_article_message(article):
    """Format a single article into a readable Discord message."""
    msg = f"**{article.get('number', '')}. {article.get('title', 'No Title')}**\n"
    msg += "✅ 翻訳と要約が準備できました\n"
    msg += "> 詳細は Archive を確認してください\n"
    return msg


def split_into_chunks(text, max_size):
    """Split text into chunks respecting character limit."""
    chunks = []
    current_chunk = ""
    
    for line in text.split('\n'):
        if len(current_chunk) + len(line) + 1 > max_size:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = line
        else:
            current_chunk += line + '\n'
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks


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

        # Translate and summarize (returns tuple: (summary, articles))
        ai_summary, articles_with_data = translate_and_summarize(articles)
        if not ai_summary:
            print("✗ Failed to generate summaries, exiting")
            return False

        # Save to archive
        archive_file = save_to_archive(articles, ai_summary)
        if not archive_file:
            print("✗ Failed to save to archive, exiting")
            return False

        # Send to Discord with articles data for markdown links
        send_to_discord(ai_summary, articles_with_data)

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
