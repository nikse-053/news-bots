import time
import json
import os
import feedparser
import requests
import schedule
import urllib3
from datetime import datetime, timezone, timedelta

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TOKEN      = os.environ.get("TOKEN", "8847992261:AAGlg560Vo60cV2uIYNRwfDTgUcZdPun5eQ")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "@novini_ua_10")

UPSTASH_URL   = os.environ.get("UPSTASH_REDIS_REST_URL", "")
UPSTASH_TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")

# Максимальний вік новини — 2 години
def get_max_age() -> int:
    hour = datetime.now(KYIV_TZ).hour
    return 180 if hour < 7 else 60  # вночі 3г, вдень 1г

RSS_FEEDS = [
    ("BBC Україна",       "https://feeds.bbci.co.uk/ukrainian/rss.xml"),
    ("Українська правда", "https://www.pravda.com.ua/rss/"),
    ("УНІАН",             "https://rss.unian.net/site/news_ukr.rss"),
    ("ТСН",               "https://tsn.ua/rss/full.rss"),
    ("РБК Україна",       "https://www.rbc.ua/static/rss/news_ukr.xml"),
    ("Цензор",            "https://censor.net/ua/rss/news"),
]

KYIV_TZ = timezone(timedelta(hours=3))


# ── Redis ────────────────────────────────────────────────────────────────────

def redis_get(key, default):
    if not UPSTASH_URL:
        return default
    try:
        r = requests.get(
            f"{UPSTASH_URL}/get/{key}",
            headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"},
            timeout=5,
        )
        val = r.json().get("result")
        return json.loads(val) if val else default
    except Exception as e:
        print(f"[Redis GET] {e}")
        return default

def redis_set(key, value):
    if not UPSTASH_URL:
        return
    try:
        requests.post(
            f"{UPSTASH_URL}/set/{key}",
            headers={
                "Authorization": f"Bearer {UPSTASH_TOKEN}",
                "Content-Type": "application/json",
            },
            data=json.dumps({"value": json.dumps(value, ensure_ascii=False)}),
            timeout=5,
        )
    except Exception as e:
        print(f"[Redis SET] {e}")


recent_titles: set = set(redis_get("sent_titles", []))
feed_index: int = redis_get("feed_index", 0)

print(f"[Start] Пам'ять: {len(recent_titles)} заголовків, наступний сайт: {RSS_FEEDS[feed_index % len(RSS_FEEDS)][0]}")


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
        if not resp.ok:
            print(f"[TG Error] {resp.status_code}: {resp.text[:200]}")
            return False
        return True
    except Exception as e:
        print(f"[TG Exception] {e}")
        return False


# ── Допоміжні ────────────────────────────────────────────────────────────────

def parse_entry_time(entry) -> datetime | None:
    for field in ("published_parsed", "updated_parsed"):
        t = getattr(entry, field, None)
        if t:
            return datetime(*t[:6], tzinfo=timezone.utc)
    return None

def is_fresh(entry) -> bool:
    """Перевіряє чи новина не старіша за MAX_AGE_MINUTES."""
    pub = parse_entry_time(entry)
    if pub is None:
        # Якщо час відсутній — пропускаємо, щоб не слати старе
        return False
    age = datetime.now(timezone.utc) - pub
    return age.total_seconds() < get_max_age() * 60

def normalize(title: str) -> str:
    return " ".join(title.lower().split())

def now_str() -> str:
    return datetime.now(KYIV_TZ).strftime("%H:%M:%S")


# ── Новини ───────────────────────────────────────────────────────────────────

def check_news():
    global recent_titles, feed_index

    for i in range(len(RSS_FEEDS)):
        idx = (feed_index + i) % len(RSS_FEEDS)
        source_name, url = RSS_FEEDS[idx]

        print(f"[{now_str()}] Перевірка: {source_name}")

        try:
            feed = feedparser.parse(url, request_headers={"User-Agent": "Mozilla/5.0"})

            # Фільтруємо: тільки свіжі + не відправлені
            fresh = [
                e for e in feed.entries[:20]
                if is_fresh(e) and normalize(e.get("title", "")) not in recent_titles
            ]

            if not fresh:
                print(f"[{now_str()}] [{source_name}] Свіжих новин немає")
                continue

            # Беремо найсвіжішу
            entry = sorted(fresh, key=lambda e: parse_entry_time(e), reverse=True)[0]

            title = entry.get("title", "").strip()
            link  = entry.get("link",  "").strip()
            pub   = parse_entry_time(entry).astimezone(KYIV_TZ)
            time_str = pub.strftime("🕐 %H:%M, %d.%m.%Y")

            msg = (
                f"<b>📰 {title}</b>\n"
                f"{time_str}\n\n"
                f"<a href='{link}'>Читати повністю →</a>"
            )

            if send_message(msg):
                recent_titles.add(normalize(title))
                feed_index = (idx + 1) % len(RSS_FEEDS)

                redis_set("sent_titles", list(recent_titles)[-300:])
                redis_set("feed_index", feed_index)

                print(f"[{now_str()}] ✅ [{source_name}] {title[:60]}")
                print(f"[{now_str()}] → Наступний: {RSS_FEEDS[feed_index][0]}")
                return

        except Exception as e:
            print(f"[RSS Error] {source_name}: {e}")

    print(f"[{now_str()}] Свіжих новин не знайдено ні на одному сайті.")


# ── Тривоги ──────────────────────────────────────────────────────────────────

def _fetch_alerts_com_ua() -> list:
    """alerts.com.ua — повертає список назв регіонів з тривогою."""
    resp = requests.get(
        "https://alerts.com.ua/api/states",
        headers={"X-API-Key": "volumetric"},
        timeout=10,
    )
    resp.raise_for_status()
    states = resp.json().get("states", [])
    return [s["name"] for s in states if s.get("alert")]

def _fetch_ukrainealarm() -> list:
    """ukrainealarm.com — резервний API."""
    resp = requests.get(
        "https://api.ukrainealarm.com/api/v3/alerts",
        headers={"Authorization": "volumetric"},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    return [
        r.get("regionName", "?")
        for r in data
        if r.get("activeAlerts")
    ]

def send_alerts_map():
    print(f"[{now_str()}] Перевірка тривог...")

    # Кілька API по черзі — якщо один не працює, пробуємо наступний
    apis = [
        ("alerts.com.ua", lambda: _fetch_alerts_com_ua()),
        ("ukrainealarm",  lambda: _fetch_ukrainealarm()),
    ]

    for api_name, fetcher in apis:
        try:
            active_regions = fetcher()
            timestamp = datetime.now(KYIV_TZ).strftime("%H:%M, %d.%m.%Y")

            if not active_regions:
                msg = f"<b>🚨 Карта тривог</b> | {timestamp}\n\n🟢 Наразі по всій Україні тихо."
            else:
                regions = "\n".join(f"🔴 {r}" for r in active_regions)
                msg = f"<b>🚨 Повітряна тривога!</b> | {timestamp}\n\n{regions}"

            send_message(msg)
            print(f"[{now_str()}] ✅ [{api_name}] Тривоги: {len(active_regions)} регіонів.")
            return

        except Exception as e:
            print(f"[Alerts Error] {api_name}: {e}")

    print(f"[{now_str()}] ⚠️ Всі API тривог недоступні.")


# ── Запуск ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("🤖 Бот запущено!")

    check_news()
    send_alerts_map()

    schedule.every(15).minutes.do(check_news)
    schedule.every(1).hours.do(send_alerts_map)

    while True:
        schedule.run_pending()
        time.sleep(30)
