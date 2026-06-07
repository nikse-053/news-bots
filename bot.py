import time
import json
import os
import feedparser
import requests
import schedule
from datetime import datetime, timezone, timedelta

TOKEN      = os.environ.get("TOKEN", "8847992261:AAGlg560Vo60cV2uIYNRwfDTgUcZdPun5eQ")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "@novini_ua_10")

UPSTASH_URL   = os.environ.get("UPSTASH_REDIS_REST_URL", "")
UPSTASH_TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")

KYIV_TZ = timezone(timedelta(hours=3))

def get_max_age() -> int:
    hour = datetime.now(KYIV_TZ).hour
    return 180 if hour < 7 else 60

RSS_FEEDS = [
    ("BBC Україна",       "https://feeds.bbci.co.uk/ukrainian/rss.xml"),
    ("Українська правда", "https://www.pravda.com.ua/rss/"),
    ("УНІАН",             "https://rss.unian.net/site/news_ukr.rss"),
    ("ТСН",               "https://tsn.ua/rss/full.rss"),
    ("РБК Україна",       "https://www.rbc.ua/static/rss/news_ukr.xml"),
    ("Цензор",            "https://censor.net/ua/rss/news"),
]

# ── Redis ────────────────────────────────────────────────────────────────────

def redis_get(key, default):
    if not UPSTASH_URL: return default
    try:
        r = requests.get(
            f"{UPSTASH_URL}/get/{key}",
            headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"},
            timeout=5,
        )
        val = r.json().get("result")
        if val is None: return default
        parsed = json.loads(val)
        if isinstance(parsed, dict) and "value" in parsed:
            return json.loads(parsed["value"])
        return parsed
    except Exception as e:
        print(f"[Redis GET] {e}")
        return default

def redis_set(key, value):
    if not UPSTASH_URL: return
    try:
        encoded = requests.utils.quote(json.dumps(value, ensure_ascii=False))
        requests.get(
            f"{UPSTASH_URL}/set/{key}/{encoded}",
            headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"},
            timeout=5,
        )
    except Exception as e:
        print(f"[Redis SET] {e}")

recent_titles: set = set(redis_get("sent_titles", []))
feed_index: int = redis_get("feed_index", 0)
if not isinstance(feed_index, int): feed_index = 0

# ── Telegram ─────────────────────────────────────────────────────────────────

def send_message(text: str) -> bool:
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        resp = requests.post(url, json={
            "chat_id": CHANNEL_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        }, timeout=10)
        return resp.ok
    except Exception as e:
        print(f"[TG Exception] {e}")
        return False

# ── Новини ───────────────────────────────────────────────────────────────────

def parse_entry_time(entry) -> datetime | None:
    for field in ("published_parsed", "updated_parsed"):
        t = getattr(entry, field, None)
        if t: return datetime(*t[:6], tzinfo=timezone.utc)
    return None

def is_fresh(entry) -> bool:
    pub = parse_entry_time(entry)
    if pub is None: return False
    age = datetime.now(timezone.utc) - pub
    return age.total_seconds() < get_max_age() * 60

def normalize(title: str) -> str:
    return " ".join(title.lower().split())

def check_news():
    global recent_titles, feed_index
    source_name, url = RSS_FEEDS[feed_index % len(RSS_FEEDS)]
    
    try:
        feed = feedparser.parse(url, request_headers={"User-Agent": "Mozilla/5.0"})
        fresh = [
            e for e in feed.entries[:20]
            if is_fresh(e) and normalize(e.get("title", "")) not in recent_titles
        ]

        if not fresh:
            feed_index = (feed_index + 1) % len(RSS_FEEDS)
            redis_set("feed_index", feed_index)
            return

        entry = sorted(fresh, key=lambda e: parse_entry_time(e), reverse=True)[0]
        title = entry.get("title", "").strip()
        link  = entry.get("link",  "").strip()
        pub   = parse_entry_time(entry).astimezone(KYIV_TZ)
        
        msg = f"<b>📰 {title}</b>\n🕐 {pub.strftime('%H:%M, %d.%m.%Y')}\n\n<a href='{link}'>Читати повністю →</a>"

        if send_message(msg):
            recent_titles.add(normalize(title))
            feed_index = (feed_index + 1) % len(RSS_FEEDS)
            redis_set("sent_titles", list(recent_titles)[-300:])
            redis_set("feed_index", feed_index)
            
    except Exception as e:
        print(f"[RSS Error] {source_name}: {e}")
        feed_index = (feed_index + 1) % len(RSS_FEEDS)
        redis_set("feed_index", feed_index)

if __name__ == "__main__":
    print("🤖 Бот новин запущено!")
    check_news()
    schedule.every(15).minutes.do(check_news)
    while True:
        schedule.run_pending()
        time.sleep(30)
