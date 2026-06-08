import time
import json
import os
import io
import feedparser
import requests
import schedule
import urllib3
from PIL import Image, ImageDraw, ImageFont
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

# Контури регіонів (lon, lat)
REGION_SHAPES = {
    "Волинська область":         [(23.6,52.4),(25.3,52.5),(25.9,51.6),(24.8,51.2),(23.2,51.3),(23.0,52.0)],
    "Рівненська область":        [(25.3,52.4),(27.3,52.2),(27.7,51.2),(26.6,50.6),(25.1,50.7),(24.8,51.3)],
    "Житомирська область":       [(27.3,52.2),(30.2,52.0),(30.6,50.8),(29.4,50.2),(27.6,50.3),(27.0,51.2)],
    "Київська область":          [(30.2,52.0),(32.4,51.9),(32.8,50.7),(31.5,50.1),(29.5,50.2),(29.8,51.2)],
    "Чернігівська область":      [(30.6,52.6),(33.8,52.6),(34.2,51.2),(32.8,50.7),(30.2,52.0),(30.2,52.4)],
    "Сумська область":           [(33.8,52.6),(35.8,52.3),(36.3,51.0),(35.0,50.5),(33.0,50.6),(33.8,51.8)],
    "Харківська область":        [(35.0,50.5),(37.8,50.6),(38.4,49.3),(37.1,48.7),(34.9,48.9),(34.5,49.8)],
    "Луганська область":         [(37.8,50.0),(40.2,49.0),(40.4,48.0),(39.1,47.5),(37.0,47.9),(36.5,48.9),(37.5,49.6)],
    "Донецька область":          [(36.5,48.9),(37.0,47.9),(39.1,47.5),(39.2,47.0),(37.8,46.6),(35.8,47.2),(35.6,48.4)],
    "Запорізька область":        [(34.9,48.9),(37.1,48.7),(37.5,47.2),(36.2,46.1),(34.1,46.3),(33.5,47.3),(34.3,48.4)],
    "Херсонська область":        [(32.8,47.6),(34.9,47.5),(35.2,46.1),(34.1,46.3),(33.5,47.3),(32.0,45.8),(31.5,46.5)],
    "Миколаївська область":      [(30.2,48.2),(32.8,47.6),(32.0,46.5),(31.5,46.5),(30.0,46.1),(29.0,47.0),(29.5,47.9)],
    "Одеська область":           [(27.8,47.8),(30.2,48.2),(29.5,46.7),(29.0,45.6),(27.5,45.4),(27.0,46.5)],
    "Дніпропетровська область":  [(32.4,49.2),(35.0,49.0),(35.2,47.7),(34.1,47.0),(32.0,47.3),(31.5,48.5),(32.0,49.0)],
    "Кіровоградська область":    [(29.5,50.0),(32.4,49.2),(32.0,47.9),(30.2,47.8),(29.0,48.3),(29.2,49.4)],
    "Черкаська область":         [(29.5,50.2),(31.5,50.1),(32.0,49.0),(30.2,48.5),(29.0,48.9),(29.2,49.7)],
    "Полтавська область":        [(32.4,51.0),(35.0,50.8),(35.0,49.5),(33.0,49.0),(31.5,49.5),(31.8,50.5)],
    "Вінницька область":         [(27.6,50.3),(29.4,50.2),(30.0,49.2),(29.0,48.5),(27.2,48.7),(26.8,49.5),(27.3,50.1)],
    "Хмельницька область":       [(25.9,50.7),(27.6,50.3),(27.3,49.2),(26.2,48.9),(25.0,49.3),(25.1,50.1)],
    "Тернопільська область":     [(24.8,50.3),(26.2,50.2),(26.5,49.4),(25.5,48.9),(24.2,49.1),(24.0,49.7)],
    "Львівська область":         [(22.7,50.8),(24.8,50.8),(25.2,49.8),(24.2,49.1),(22.8,49.2),(22.2,49.8)],
    "Івано-Франківська область": [(23.7,49.5),(25.2,49.5),(25.5,48.7),(24.8,48.2),(23.5,48.1),(23.0,48.7)],
    "Закарпатська область":      [(22.2,48.7),(23.5,49.0),(24.2,48.6),(23.8,47.9),(22.6,47.9),(22.0,48.3)],
    "Чернівецька область":       [(25.2,49.0),(26.5,48.9),(27.3,47.9),(26.3,47.5),(25.0,47.6),(24.8,48.4)],
    "м. Київ":                   [(30.35,50.65),(30.75,50.65),(30.85,50.35),(30.55,50.25),(30.25,50.35),(30.25,50.55)],
    "Крим":                      [(32.5,46.2),(35.0,45.8),(36.5,45.2),(35.8,44.4),(34.0,44.3),(32.5,44.7),(31.5,45.3),(32.0,46.0)],
}

LON_MIN, LON_MAX = 22.0, 40.5
LAT_MIN, LAT_MAX = 44.2, 52.7


def geo_to_px(lon, lat, W, H):
    x = int((lon - LON_MIN) / (LON_MAX - LON_MIN) * (W - 60) + 30)
    y = int((LAT_MAX - lat) / (LAT_MAX - LAT_MIN) * (H - 100) + 30)
    return x, y


def generate_alert_map(active_regions: list) -> bytes:
    W, H = 1000, 680
    img = Image.new("RGB", (W, H), (13, 17, 23))
    draw = ImageDraw.Draw(img)
    active_lower = [r.lower() for r in active_regions]

    def is_active(name):
        n = name.lower()
        return any(n in a or a in n for a in active_lower)

    for region_name, coords in REGION_SHAPES.items():
        pts = [geo_to_px(lon, lat, W, H) for lon, lat in coords]
        alert = is_active(region_name)
        fill    = (180, 25, 25) if alert else (28, 58, 38)
        outline = (255, 70, 70) if alert else (45, 90, 58)
        draw.polygon(pts, fill=fill)
        draw.line(pts + [pts[0]], fill=outline, width=2)

    try:
        font_sm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
        font_md = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 13)
    except Exception:
        font_sm = font_md = ImageFont.load_default()

    for region_name, coords in REGION_SHAPES.items():
        pts = [geo_to_px(lon, lat, W, H) for lon, lat in coords]
        alert = is_active(region_name)
        cx = sum(p[0] for p in pts) // len(pts)
        cy = sum(p[1] for p in pts) // len(pts)
        short = region_name.replace(" область", "").replace("м. ", "")
        col = (255, 200, 200) if alert else (170, 210, 175)
        draw.text((cx+1, cy+1), short, fill=(0, 0, 0), font=font_sm, anchor="mm")
        draw.text((cx, cy), short, fill=col, font=font_sm, anchor="mm")

    lx, ly = 20, H - 55
    draw.rounded_rectangle([lx, ly, lx+230, ly+45], radius=8, fill=(20, 25, 35), outline=(60, 70, 80))
    draw.rectangle([lx+10, ly+10, lx+28, ly+28], fill=(180, 25, 25), outline=(255, 70, 70))
    draw.text((lx+36, ly+19), "Тривога", fill=(255, 230, 230), font=font_md, anchor="lm")
    draw.rectangle([lx+120, ly+10, lx+138, ly+28], fill=(28, 58, 38), outline=(45, 90, 58))
    draw.text((lx+146, ly+19), "Тихо", fill=(200, 230, 200), font=font_md, anchor="lm")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


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
        data = resp.json()
        val = data.get("result")
        if val is None:
            return default
        # Upstash повертає рядок — парсимо JSON
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
        # Upstash REST API: GET /set/key/value
        serialized = json.dumps(value, ensure_ascii=False)
        import urllib.parse
        encoded = urllib.parse.quote(serialized)
        resp = requests.get(
            f"{UPSTASH_URL}/set/{key}/{encoded}",
            headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"},
            timeout=5,
        )
        if resp.ok:
            print(f"[Redis SET '{key}'] OK")
        else:
            print(f"[Redis SET '{key}'] Error: {resp.status_code} {resp.text[:100]}")
    except Exception as e:
        print(f"[Redis SET '{key}'] {e}")


def r_get_str(key, default=""):
    if not UPSTASH_URL:
        return default
    try:
        resp = requests.get(
            f"{UPSTASH_URL}/get/{key}",
            headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"},
            timeout=5,
        )
        val = resp.json().get("result")
        return val if val is not None else default
    except Exception as e:
        print(f"[Redis GET_STR '{key}'] {e}")
        return default


def r_set_str(key, value: str):
    if not UPSTASH_URL:
        return
    try:
        import urllib.parse
        encoded = urllib.parse.quote(value)
        resp = requests.get(
            f"{UPSTASH_URL}/set/{key}/{encoded}",
            headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"},
            timeout=5,
        )
        if not resp.ok:
            print(f"[Redis SET_STR '{key}'] Error: {resp.status_code}")
    except Exception as e:
        print(f"[Redis SET_STR '{key}'] {e}")


# ── Стан ─────────────────────────────────────────────────────────────────────

def load_state():
    titles_raw = r_get("sent_titles", [])
    titles = set(titles_raw) if isinstance(titles_raw, list) else set()
    idx_raw = r_get("feed_index", 0)
    idx = idx_raw if isinstance(idx_raw, int) else 0
    alert_hash = r_get_str("alert_hash", "")
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
        print(f"[TG text] {e}")
        return False


def tg_send_photo(img_bytes: bytes, caption: str) -> bool:
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendPhoto",
            data={"chat_id": CHANNEL_ID, "caption": caption, "parse_mode": "HTML"},
            files={"photo": ("map.png", img_bytes, "image/png")},
            timeout=15,
        )
        return resp.ok
    except Exception as e:
        print(f"[TG photo] {e}")
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
    print(f"[{now_str()}] Перевірка тривог...")

    ALERTS_KEY = os.environ.get("ALERTS_API_KEY", "")
    active = None

    # 1. ukrainealarm.com — офіційний API
    if ALERTS_KEY:
        try:
            resp = requests.get(
                "https://api.ukrainealarm.com/api/v3/alerts",
                headers={"Authorization": ALERTS_KEY},
                timeout=10,
            )
            if resp.ok:
                data = resp.json()
                active = sorted([
                    r.get("regionName", "?")
                    for r in data
                    if r.get("activeAlerts")
                ])
                print(f"[{now_str()}] ukrainealarm OK")
        except Exception as e:
            print(f"[Alerts ukrainealarm] {e}")

    # 2. Якщо немає ключа або помилка — беремо з Telegram каналу @air_alert_ua через RSS
    if active is None:
        try:
            resp = requests.get(
                "https://alerts.com.ua/api/states",
                headers={"X-API-Key": "yourApiKey34421337"},
                timeout=8,
            )
            if resp.ok:
                states = resp.json().get("states", [])
                active = sorted([s["name"] for s in states if s.get("alert")])
                print(f"[{now_str()}] alerts.com.ua OK")
        except Exception as e:
            print(f"[Alerts alerts.com.ua] {e}")

    if active is None:
        print(f"[{now_str()}] Всі API тривог недоступні")
        return

    current_hash = ",".join(active)
    if current_hash == last_alert_hash:
        print(f"[{now_str()}] Тривоги не змінились — пропускаємо")
        return

    last_alert_hash = current_hash
    r_set_str("alert_hash", current_hash)

    timestamp = datetime.now(KYIV_TZ).strftime("%H:%M, %d.%m.%Y")
    if not active:
        caption = f"🟢 Відбій тривоги | {timestamp}\n\nПо всій Україні тихо."
    else:
        regions_text = "\n".join(f"🔴 {r}" for r in active)
        caption = f"🔴 Повітряна тривога! | {timestamp}\n\n{regions_text}"

    tg_send(caption)

    print(f"[{now_str()}] ✅ Тривоги: {len(active)} регіонів.")


# ── Запуск ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("🤖 Бот запущено!")

    # Тест карти при старті
    if os.environ.get("TEST_ALERTS") == "true":
        print("🧪 Тестова карта тривог...")
        test_regions = ["Харківська область", "Сумська область", "Донецька область"]
        try:
            img = generate_alert_map(test_regions)
            caption = "<b>ТЕСТ карти тривог</b>\n\nХарківська, Сумська, Донецька обл."
            tg_send_photo(img, caption)
            print("✅ Тестова карта відправлена!")
        except Exception as e:
            print(f"❌ Помилка: {e}")

    check_news()
    schedule.every(15).minutes.do(check_news)
    schedule.every(2).minutes.do(check_alerts)
    while True:
        schedule.run_pending()
        time.sleep(30) 
