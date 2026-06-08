import time
import json
import os
import urllib.parse
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

KYIV_TZ = timezone(timedelta(hours=3))

RSS_FEEDS = [
    ("BBC Україна",       "https://feeds.bbci.co.uk/ukrainian/rss.xml"),
    ("Українська правда", "https://www.pravda.com.ua/rss/"),
    ("УНІАН",             "https://rss.unian.net/site/news_ukr.rss"),
    ("ТСН",               "https://tsn.ua/rss/full.rss"),
    ("РБК Україна",       "https://www.rbc.ua/static/rss/news_ukr.xml"),
    ("Цензор",            "https://censor.net/ua/rss/news"),
]


# ── Redis ─────────────────────────────────────────────────────────────────────

def r_get(key, default):
    if not UPSTASH_URL:
        return default
    try:
        resp = requests.get(
            f"{UPSTASH_URL}/get/{key}",
            headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"},
            timeout=5,
        )
        val = resp.json().get("result")
        if val is None:
            return default
        if isinstance(val, str):
            try:
                return json.loads(val)
            except Exception:
                return val
        return val
    except Exception as e:
        print(f"[Redis GET '{key}'] {e}")
        return default

def r_set(key, value):
    if not UPSTASH_URL:
        return
    try:
        serialized = json.dumps(value, ensure_ascii=False)
        encoded = urllib.parse.quote(serialized)
        resp = requests.get(
            f"{UPSTASH_URL}/set/{key}/{encoded}",
            headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"},
            timeout=5,
        )
        if not resp.ok:
            print(f"[Redis SET '{key}'] Error: {resp.status_code}")
    except Exception as e:
        print(f"[Redis SET '{key}'] {e}")


# ── Стан ─────────────────────────────────────────────────────────────────────

def load_state():
    titles_raw = r_get("sent_titles", [])
    titles = set(titles_raw) if isinstance(titles_raw, list) else set()
    idx_raw = r_get("feed_index", 0)
    idx = idx_raw if isinstance(idx_raw, int) else 0
    alert_hash = r_get("alert_hash", "")
    if not isinstance(alert_hash, str):
        alert_hash = ""
    print(f"[Start] Заголовків: {len(titles)}, сайт: {RSS_FEEDS[idx % len(RSS_FEEDS)][0]}")
    return titles, idx, alert_hash

sent_titles, feed_index, last_alert_hash = load_state()


# ── Telegram ─────────────────────────────────────────────────────────────────

def tg_send(text: str) -> bool:
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={"chat_id": CHANNEL_ID, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        return resp.ok
    except Exception as e:
        print(f"[TG] {e}")
        return False


# ── Допоміжні ────────────────────────────────────────────────────────────────

def normalize(title: str) -> str:
    return " ".join(title.lower().split())

def now_str() -> str:
    return datetime.now(KYIV_TZ).strftime("%H:%M:%S")

def get_max_age_minutes() -> int:
    return 180 if datetime.now(KYIV_TZ).hour < 7 else 60

def entry_time(entry):
    for field in ("published_parsed", "updated_parsed"):
        t = getattr(entry, field, None)
        if t:
            return datetime(*t[:6], tzinfo=timezone.utc)
    return None

def is_fresh(entry) -> bool:
    pub = entry_time(entry)
    if pub is None:
        return False
    return (datetime.now(timezone.utc) - pub).total_seconds() < get_max_age_minutes() * 60


# ── Новини ───────────────────────────────────────────────────────────────────

def check_news():
    global sent_titles, feed_index
    source_name, url = RSS_FEEDS[feed_index % len(RSS_FEEDS)]
    print(f"[{now_str()}] Перевірка: {source_name}")
    try:
        feed = feedparser.parse(url, request_headers={"User-Agent": "Mozilla/5.0"})
        fresh = [
            e for e in feed.entries[:20]
            if is_fresh(e) and normalize(e.get("title", "")) not in sent_titles
        ]
        if not fresh:
            print(f"[{now_str()}] [{source_name}] Нема свіжих")
        else:
            entry = sorted(fresh, key=lambda e: entry_time(e), reverse=True)[0]
            title = entry.get("title", "").strip()
            link  = entry.get("link", "").strip()
            pub   = entry_time(entry).astimezone(KYIV_TZ)
            msg = (
                f"<b>📰 {title}</b>\n"
                f"🕐 {pub.strftime('%H:%M, %d.%m.%Y')}\n\n"
                f"<a href='{link}'>Читати повністю →</a>"
            )
            if tg_send(msg):
                sent_titles.add(normalize(title))
                r_set("sent_titles", list(sent_titles)[-300:])
                print(f"[{now_str()}] ✅ [{source_name}] {title[:60]}")
    except Exception as e:
        print(f"[RSS Error] {source_name}: {e}")

    feed_index = (feed_index + 1) % len(RSS_FEEDS)
    r_set("feed_index", feed_index)
    print(f"[{now_str()}] → Наступний: {RSS_FEEDS[feed_index][0]}")


# ── Тривоги ──────────────────────────────────────────────────────────────────

def check_alerts():
    global last_alert_hash
    try:
        resp = requests.get(
            "https://alerts.com.ua/api/states",
            headers={"X-API-Key": "yourApiKey34421337"},
            timeout=10,
        )
        if not resp.ok:
            return
        states = resp.json().get("states", [])
        active = sorted([s["name"] for s in states if s.get("alert")])
        current_hash = ",".join(active)

        if current_hash == last_alert_hash:
            return

        last_alert_hash = current_hash
        r_set("alert_hash", current_hash)

        timestamp = datetime.now(KYIV_TZ).strftime("%H:%M, %d.%m.%Y")
        if not active:
            msg = f"🟢 Відбій тривоги | {timestamp}\n\nПо всій Україні тихо."
        else:
            regions = "\n".join(f"🔴 {r}" for r in active)
            msg = f"🔴 Повітряна тривога! | {timestamp}\n\n{regions}"

        tg_send(msg)
        print(f"[{now_str()}] ✅ Тривоги: {len(active)} регіонів.")

    except Exception as e:
        print(f"[Alerts Error] {e}")


# ── Запуск ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import threading
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        def log_message(self, *args):
            pass  # Тихий режим

    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"🌐 Health server on port {port}")

    print("🤖 Бот запущено!")
    check_news()
    schedule.every(15).minutes.do(check_news)
    schedule.every(2).minutes.do(check_alerts)
    while True:
        schedule.run_pending()
        time.sleep(30)   
