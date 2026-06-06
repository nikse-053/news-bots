import time
import json
import os
import feedparser
import requests
import schedule
import urllib3
from datetime import datetime, timezone, timedelta

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TOKEN = "8847992261:AAGlg560Vo60cV2uIYNRwfDTgUcZdPun5eQ"
CHANNEL_ID = "@novini_ua_10"
MEMORY_FILE = "sent_titles.json"  # Файл для збереження пам'яті між перезапусками

RSS_FEEDS = [
    "https://feeds.bbci.co.uk/ukrainian/rss.xml",
    "https://www.pravda.com.ua/rss/",
    "https://rss.unian.net/site/news_ukr.rss",
    "https://tsn.ua/rss/full.rss",
    "https://www.rbc.ua/static/rss/news_ukr.xml",
    "https://censor.net/ua/rss/news",
]

KYIV_TZ = timezone(timedelta(hours=3))


# ─── Пам'ять (зберігається між перезапусками) ───────────────────────────────

def load_memory() -> set:
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()

def save_memory(titles: set):
    try:
        # Зберігаємо лише останні 300 заголовків
        data = list(titles)[-300:]
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        print(f"[Memory] Помилка збереження: {e}")

recent_titles: set = load_memory()


# ─── Telegram ────────────────────────────────────────────────────────────────

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


# ─── Допоміжні функції ───────────────────────────────────────────────────────

def parse_entry_time(entry) -> datetime | None:
    for field in ("published_parsed", "updated_parsed"):
        t = getattr(entry, field, None)
        if t:
            return datetime(*t[:6], tzinfo=timezone.utc).astimezone(KYIV_TZ)
    return None

def normalize_title(title: str) -> str:
    """Нормалізуємо заголовок для порівняння — без зайвих пробілів, в нижньому регістрі."""
    return " ".join(title.lower().split())

def now_str() -> str:
    return datetime.now(KYIV_TZ).strftime("%H:%M:%S")


# ─── Основні задачі ──────────────────────────────────────────────────────────

def check_news():
    """Відправляє одну нову новину (перша знайдена з будь-якого джерела)."""
    global recent_titles
    print(f"[{now_str()}] Перевірка новин...")

    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url, request_headers={"User-Agent": "Mozilla/5.0"})
            if not feed.entries:
                continue

            for entry in feed.entries[:5]:
                title = entry.get("title", "").strip()
                link  = entry.get("link",  "").strip()
                if not title or not link:
                    continue

                key = normalize_title(title)  # порівнюємо нормалізовано
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
                    save_memory(recent_titles)
                    print(f"[{now_str()}] ✅ Відправлено: {title[:70]}")
                    return  # Одна новина за раз — виходимо

        except Exception as e:
            print(f"[RSS Error] {url}: {e}")
            continue

    print(f"[{now_str()}] Нових новин не знайдено.")


def send_alerts_map():
    """Надсилає поточну карту тривог в Україні."""
    print(f"[{now_str()}] Перевірка тривог...")
    try:
        resp = requests.get(
            "https://war-api.ukrzen.in.ua/alerts/api/alerts/active.json",
            verify=False,
            timeout=10,
        )
        resp.raise_for_status()
        alerts = resp.json().get("alerts", [])
        timestamp = datetime.now(KYIV_TZ).strftime("%H:%M, %d.%m.%Y")

        if not alerts:
            msg = f"<b>🚨 Карта тривог</b> | {timestamp}\n\n🟢 Наразі по всій Україні тихо."
        else:
            regions = "\n".join(
                f"🔴 {a.get('location_title', 'Невідомий регіон')}" for a in alerts
            )
            msg = f"<b>🚨 Повітряна тривога!</b> | {timestamp}\n\n{regions}"

        send_message(msg)
        print(f"[{now_str()}] ✅ Карту тривог відправлено ({len(alerts)} регіонів).")

    except Exception as e:
        print(f"[Alerts Error] {e}")


# ─── Запуск ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("🤖 Бот запущено!")
    print(f"   Завантажено {len(recent_titles)} заголовків з пам'яті.")

    # Одразу при старті
    check_news()
    send_alerts_map()

    # Розклад
    schedule.every(15).minutes.do(check_news)
    schedule.every(1).hours.do(send_alerts_map)

    while True:
        schedule.run_pending()
        time.sleep(30)
