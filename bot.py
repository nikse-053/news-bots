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

RSS_FEEDS = [
    "https://feeds.bbci.co.uk/ukrainian/rss.xml",
    "https://www.pravda.com.ua/rss/",
    "https://rss.unian.net/site/news_ukr.rss",
    "https://tsn.ua/rss/full.rss",
    "https://www.rbc.ua/static/rss/news_ukr.xml",
    "https://censor.net/ua/rss/news",
]

KYIV_TZ = timezone(timedelta(hours=3))


# ── Redis: читання ───────────────────────────────────────────────────────────
def redis_get() -> set:
    if not UPSTASH_URL:
        print("[Redis] URL не вказано — пам'ять лише в оперативній")
        return set()
    try:
        r = requests.get(
            f"{UPSTASH_URL}/get/sent_titles",
            headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"},
            timeout=5,
        )
        val = r.json().get("result")
        if val:
            titles = set(json.loads(val))
            print(f"[Redis] ✅ Завантажено {len(titles)} заголовків")
            return titles
    except Exception as e:
        print(f"[Redis GET] ⚠️ {e}")
    return set()


# ── Redis: запис ─────────────────────────────────────────────────────────────
def redis_set(titles: set):
    if not UPSTASH_URL:
        return
    try:
        payload = json.dumps(list(titles)[-300:], ensure_ascii=False)
        r = requests.post(
            f"{UPSTASH_URL}/set/sent_titles",
            headers={
                "Authorization": f"Bearer {UPSTASH_TOKEN}",
                "Content-Type": "application/json",
            },
            data=json.dumps({"value": payload}),
            timeout=5,
        )
        if r.ok:
            print(f"[Redis] ✅ Збережено {len(titles)} заголовків")
        else:
            print(f"[Redis SET] ⚠️ {r.status_code}: {r.text[:100]}")
    except Exception as e:
        print(f"[Redis SET] ⚠️ {e}")


# Завантажуємо пам'ять при старті
recent_titles: set = redis_get()


# ── Telegram ─────────────────────────────────────────────────────────────────
def send_message(text: str) -> bool:
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHANNEL_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if not resp.ok:
            print(f"[TG Error] {resp.status_code}: {resp.text[:200]}")
            return False
        return True
    except Exception as e:
        print(f"[TG Exception] {e}")
        return False


# ── Допоміжні ────────────────────────────────────────────────────────────────
def parse_entry_time(entry):
    for field in ("published_parsed", "updated_parsed"):
        t = getattr(entry, field, None)
        if t:
            return datetime(*t[:6], tzinfo=timezone.utc).astimezone(KYIV_TZ)
    return None

def normalize(title: str) -> str:
    return " ".join(title.lower().split())

def now_str() -> str:
    return datetime.now(KYIV_TZ).strftime("%H:%M:%S")


# ── Новини ───────────────────────────────────────────────────────────────────
def check_news():
    global recent_titles
    print(f"[{now_str()}] Перевірка новин...")

    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url, request_headers={"User-Agent": "Mozilla/5.0"})
            for entry in feed.entries[:5]:
                title = entry.get("title", "").strip()
                link  = entry.get("link",  "").strip()
                if not title or not link:
                    continue

                key = normalize(title)
                if key in recent_titles:
                    continue

                pub_time = parse_entry_time(entry)
                time_str = pub_time.strftime("🕐 %H:%M, %d.%m.%Y") if pub_time else ""

                msg = (
                    f"<b>📰 {title}</b>\n"
                    f"{time_str}\n\n"
                    f"<a href='{link}'>Читати повністю →</a>"
                )

                if send_message(msg):
                    recent_titles.add(key)
                    redis_set(recent_titles)
                    print(f"[{now_str()}] ✅ Відправлено: {title[:70]}")
                    return  # одна новина за раз

        except Exception as e:
            print(f"[RSS Error] {url}: {e}")

    print(f"[{now_str()}] Нових новин не знайдено.")


# ── Тривоги ──────────────────────────────────────────────────────────────────
def send_alerts_map():
    print(f"[{now_str()}] Перевірка тривог...")
    try:
        resp = requests.get(
            "https://war-api.ukrzen.in.ua/alerts/api/alerts/active.json",
            verify=False, timeout=10,
        )
        resp.raise_for_status()
        alerts = resp.json().get("alerts", [])
        timestamp = datetime.now(KYIV_TZ).strftime("%H:%M, %d.%m.%Y")

        if not alerts:
            msg = f"<b>🚨 Карта тривог</b> | {timestamp}\n\n🟢 Наразі по всій Україні тихо."
        else:
            regions = "\n".join(f"🔴 {a.get('location_title', '?')}" for a in alerts)
            msg = f"<b>🚨 Повітряна тривога!</b> | {timestamp}\n\n{regions}"

        send_message(msg)
        print(f"[{now_str()}] ✅ Тривоги: {len(alerts)} регіонів.")

    except Exception as e:
        print(f"[Alerts Error] {e}")


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
