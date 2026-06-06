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
        if val is None:
            return default
        parsed = json.loads(val)
        # Якщо збережено як {"value": "..."} — розпаковуємо
        if isinstance(parsed, dict) and "value" in parsed:
            return json.loads(parsed["value"])
        return parsed
    except Exception as e:
        print(f"[Redis GET] {e}")
        return default

def redis_set(key, value):
    if not UPSTASH_URL:
        return
    try:
        # Зберігаємо через GET-запит /set/key/value — найпростіший формат Upstash REST
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
if not isinstance(feed_index, int):
    feed_index = 0

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

    # Беремо ТІЛЬКИ поточний сайт — без переходу до інших
    source_name, url = RSS_FEEDS[feed_index % len(RSS_FEEDS)]
    print(f"[{now_str()}] Перевірка: {source_name}")

    try:
        feed = feedparser.parse(url, request_headers={"User-Agent": "Mozilla/5.0"})

        fresh = [
            e for e in feed.entries[:20]
            if is_fresh(e) and normalize(e.get("title", "")) not in recent_titles
        ]

        if not fresh:
            print(f"[{now_str()}] [{source_name}] Свіжих новин немає — переходимо до наступного сайту")
            # Навіть якщо нема новин — переходимо до наступного сайту
            feed_index = (feed_index + 1) % len(RSS_FEEDS)
            redis_set("feed_index", feed_index)
            return

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
            feed_index = (feed_index + 1) % len(RSS_FEEDS)

            redis_set("sent_titles", list(recent_titles)[-300:])
            redis_set("feed_index", feed_index)

            print(f"[{now_str()}] ✅ [{source_name}] {title[:60]}")
            print(f"[{now_str()}] → Наступний: {RSS_FEEDS[feed_index][0]}")

    except Exception as e:
        print(f"[RSS Error] {source_name}: {e}")
        feed_index = (feed_index + 1) % len(RSS_FEEDS)
        redis_set("feed_index", feed_index)


# ── Тривоги ──────────────────────────────────────────────────────────────────

def send_alerts_map():
    print(f"[{now_str()}] Перевірка тривог...")
    timestamp = datetime.now(KYIV_TZ).strftime("%H:%M, %d.%m.%Y")

    try:
        # Отримуємо список регіонів з тривогою
        resp = requests.get(
            "https://alerts.com.ua/api/states",
            headers={"X-API-Key": "volumetric"},
            timeout=10,
        )
        resp.raise_for_status()
        states = resp.json().get("states", [])
        active = [s["name"] for s in states if s.get("alert")]

        if not active:
            caption = f"<b>🚨 Карта тривог</b> | {timestamp}\n\n🟢 Наразі по всій Україні тихо."
        else:
            regions_text = "\n".join(f"🔴 {r}" for r in active)
            caption = f"<b>🚨 Повітряна тривога!</b> | {timestamp}\n\n{regions_text}"

        # Завантажуємо готову карту як картинку
        map_url = f"https://alerts.in.ua/map.png?t={int(time.time())}"
        img_resp = requests.get(map_url, timeout=15)

        if img_resp.ok and img_resp.headers.get("content-type", "").startswith("image"):
            url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
            requests.post(url, data={
                "chat_id": CHANNEL_ID,
                "caption": caption,
                "parse_mode": "HTML",
            }, files={"photo": ("map.png", img_resp.content, "image/png")}, timeout=15)
        else:
            send_message(caption)

        print(f"[{now_str()}] ✅ Тривоги відправлено: {len(active)} регіонів.")

    except Exception as e:
        print(f"[Alerts Error] {e}")
        try:
            send_message(f"<b>🚨 Карта тривог</b> | {timestamp}\n\n⚠️ Не вдалось завантажити карту.")
        except Exception:
            pass


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
