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
feed_index: int = int(redis_get("feed_index", 0) or 0)

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

# Координати центрів регіонів на карті (x, y) для полотна 800x600
REGION_COORDS = {
    "Вінницька":       (270, 310), "Волинська":       (130, 180),
    "Дніпропетровська":(460, 360), "Донецька":        (580, 340),
    "Житомирська":     (220, 230), "Закарпатська":    ( 80, 320),
    "Запорізька":      (500, 410), "Івано-Франківська":(130, 310),
    "Київська":        (310, 220), "Кіровоградська":  (370, 340),
    "Луганська":       (640, 300), "Львівська":       (120, 260),
    "Миколаївська":    (390, 420), "Одеська":         (330, 450),
    "Полтавська":      (460, 280), "Рівненська":      (175, 215),
    "Сумська":         (480, 200), "Тернопільська":   (170, 285),
    "Харківська":      (540, 240), "Херсонська":      (450, 440),
    "Хмельницька":     (210, 280), "Черкаська":       (370, 290),
    "Чернівецька":     (185, 345), "Чернігівська":    (360, 170),
    "Київ":            (320, 235), "Крим":            (430, 490),
}

def _fetch_alerts_com_ua() -> list:
    resp = requests.get(
        "https://alerts.com.ua/api/states",
        headers={"X-API-Key": "volumetric"},
        timeout=10,
    )
    resp.raise_for_status()
    states = resp.json().get("states", [])
    return [s["name"] for s in states if s.get("alert")]

def generate_map_image(active_regions: list) -> bytes:
    """Генерує PNG карту України з підсвіченими регіонами."""
    from PIL import Image, ImageDraw, ImageFont
    import io

    W, H = 800, 600
    img = Image.new("RGB", (W, H), color=(30, 30, 46))
    draw = ImageDraw.Draw(img)

    # Фон — схематичний контур України (прямокутник з закругленням)
    draw.rounded_rectangle([60, 100, 740, 540], radius=20, outline=(80, 80, 100), width=2)

    # Малюємо всі регіони
    for name, (x, y) in REGION_COORDS.items():
        # Нормалізуємо для порівняння
        is_alert = any(name.lower() in r.lower() or r.lower() in name.lower()
                      for r in active_regions)

        if is_alert:
            color = (220, 50, 50)    # червоний — тривога
            text_color = (255, 255, 255)
        else:
            color = (60, 100, 60)    # зелений — тихо
            text_color = (200, 230, 200)

        # Коло регіону
        r = 28
        draw.ellipse([x-r, y-r, x+r, y+r], fill=color, outline=(255,255,255), width=1)

        # Назва (скорочена)
        short = name.replace("ська", "").replace("ська", "")[:6]
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 10)
        except Exception:
            font = ImageFont.load_default()
        draw.text((x, y), short, fill=text_color, font=font, anchor="mm")

    # Легенда
    draw.ellipse([70, 555, 86, 571], fill=(220, 50, 50))
    draw.text((92, 563), "Тривога", fill=(255,255,255), anchor="lm",
              font=ImageFont.load_default())
    draw.ellipse([170, 555, 186, 571], fill=(60, 100, 60))
    draw.text((192, 563), "Тихо", fill=(255,255,255), anchor="lm",
              font=ImageFont.load_default())

    # Час
    ts = datetime.now(KYIV_TZ).strftime("%H:%M, %d.%m.%Y")
    draw.text((W//2, 575), ts, fill=(180,180,180), anchor="mm",
              font=ImageFont.load_default())

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()

def send_photo_to_telegram(image_bytes: bytes, caption: str):
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    try:
        resp = requests.post(url, data={
            "chat_id": CHANNEL_ID,
            "caption": caption,
            "parse_mode": "HTML",
        }, files={"photo": ("map.png", image_bytes, "image/png")}, timeout=15)
        if not resp.ok:
            print(f"[TG Photo Error] {resp.status_code}: {resp.text[:200]}")
            return False
        return True
    except Exception as e:
        print(f"[TG Photo Exception] {e}")
        return False

def send_alerts_map():
    print(f"[{now_str()}] Перевірка тривог...")
    try:
        active_regions = _fetch_alerts_com_ua()
        timestamp = datetime.now(KYIV_TZ).strftime("%H:%M, %d.%m.%Y")

        if not active_regions:
            caption = f"<b>🚨 Карта тривог</b> | {timestamp}\n\n🟢 Наразі по всій Україні тихо."
        else:
            regions_text = "\n".join(f"🔴 {r}" for r in active_regions)
            caption = f"<b>🚨 Повітряна тривога!</b> | {timestamp}\n\n{regions_text}"

        try:
            img = generate_map_image(active_regions)
            send_photo_to_telegram(img, caption)
        except Exception as e:
            print(f"[Map Gen Error] {e} — відправляємо текст")
            send_message(caption)

        print(f"[{now_str()}] ✅ Тривоги: {len(active_regions)} регіонів.")

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
