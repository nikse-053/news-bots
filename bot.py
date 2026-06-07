import time
import json
import os
import feedparser
import requests
import schedule
import urllib3
from datetime import datetime, timezone, timedelta
 
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
 
from PIL import Image, ImageDraw, ImageFont
import io, math
 
# Реальні спрощені контури регіонів України (lon, lat пари)
# Джерело: спрощені GeoJSON дані
REGION_SHAPES = {
    "Вінницька область": [
        (28.1,49.9),(29.8,49.8),(30.1,48.9),(29.2,48.4),(27.7,48.5),(27.2,49.0),(27.8,49.6)
    ],
    "Волинська область": [
        (23.5,52.3),(25.3,52.4),(25.8,51.5),(24.7,51.1),(23.3,51.3),(23.0,51.9)
    ],
    "Дніпропетровська область": [
        (33.2,49.4),(35.4,49.2),(35.8,47.9),(34.5,47.3),(32.8,47.5),(32.3,48.3),(33.0,49.0)
    ],
    "Донецька область": [
        (36.5,49.2),(38.9,48.3),(39.2,47.5),(38.0,47.1),(36.3,47.4),(35.7,48.3),(36.2,48.9)
    ],
    "Житомирська область": [
        (27.4,51.8),(29.8,51.9),(30.4,50.8),(29.3,50.2),(27.5,50.3),(26.8,50.9),(27.1,51.5)
    ],
    "Закарпатська область": [
        (22.2,48.7),(23.9,49.0),(24.5,48.5),(23.8,47.9),(22.5,47.9),(22.0,48.2)
    ],
    "Запорізька область": [
        (34.5,48.1),(36.5,47.9),(36.9,46.7),(35.6,46.0),(34.0,46.3),(33.5,47.1),(34.1,47.8)
    ],
    "Івано-Франківська область": [
        (23.7,49.4),(25.2,49.5),(25.5,48.8),(24.8,48.2),(23.5,48.2),(23.0,48.7),(23.4,49.2)
    ],
    "Київська область": [
        (29.2,51.6),(31.8,51.7),(32.3,50.6),(31.0,50.0),(29.0,50.1),(28.3,50.7),(28.9,51.3)
    ],
    "Кіровоградська область": [
        (30.3,49.5),(32.5,49.4),(33.0,48.3),(32.0,47.7),(29.9,47.9),(29.3,48.6),(29.9,49.2)
    ],
    "Луганська область": [
        (38.0,49.5),(39.8,48.8),(40.2,48.0),(39.0,47.6),(37.0,47.9),(36.4,48.8),(37.5,49.3)
    ],
    "Львівська область": [
        (22.6,50.8),(24.7,50.8),(25.3,49.9),(24.4,49.3),(22.8,49.2),(22.0,49.7),(22.3,50.4)
    ],
    "Миколаївська область": [
        (30.0,48.0),(32.3,47.8),(32.8,46.8),(31.5,46.2),(29.8,46.4),(29.2,47.3),(29.7,47.8)
    ],
    "Одеська область": [
        (27.5,47.7),(30.0,48.1),(30.5,46.9),(29.5,45.5),(28.0,45.3),(27.0,45.8),(27.0,46.9)
    ],
    "Полтавська область": [
        (32.5,50.4),(34.8,50.3),(35.3,49.2),(34.1,48.6),(32.2,48.8),(31.7,49.6),(32.2,50.2)
    ],
    "Рівненська область": [
        (25.2,51.8),(27.2,51.9),(27.8,51.0),(26.7,50.5),(25.0,50.5),(24.5,51.1),(24.9,51.6)
    ],
    "Сумська область": [
        (33.3,52.4),(35.4,52.1),(35.8,51.0),(34.5,50.5),(32.5,50.7),(31.9,51.5),(32.9,52.1)
    ],
    "Тернопільська область": [
        (24.8,50.2),(26.5,50.1),(27.0,49.4),(26.1,48.9),(24.5,49.0),(23.9,49.5),(24.5,50.0)
    ],
    "Харківська область": [
        (35.4,50.7),(37.6,50.5),(38.3,49.4),(37.0,48.8),(35.0,49.0),(34.3,49.9),(35.0,50.5)
    ],
    "Херсонська область": [
        (32.8,47.2),(34.7,47.0),(35.2,46.0),(33.9,45.5),(32.2,45.7),(31.5,46.5),(32.3,47.0)
    ],
    "Хмельницька область": [
        (26.1,50.5),(28.2,50.4),(28.8,49.7),(27.8,49.0),(26.2,49.1),(25.4,49.7),(25.8,50.3)
    ],
    "Черкаська область": [
        (30.2,50.0),(32.0,49.9),(32.5,49.1),(31.4,48.5),(29.7,48.7),(29.1,49.4),(29.8,49.9)
    ],
    "Чернівецька область": [
        (25.1,48.7),(26.9,48.5),(27.5,47.9),(26.7,47.5),(25.3,47.5),(24.7,48.0),(24.9,48.5)
    ],
    "Чернігівська область": [
        (30.4,52.4),(33.5,52.3),(33.9,51.1),(32.5,50.6),(30.0,50.7),(29.2,51.5),(30.0,52.1)
    ],
    "м. Київ": [
        (30.3,50.7),(30.7,50.7),(30.8,50.4),(30.5,50.3),(30.2,50.4),(30.2,50.6)
    ],
    "Крим": [
        (32.5,46.2),(35.0,45.9),(36.6,45.2),(35.8,44.4),(34.0,44.3),(32.5,44.7),(31.5,45.3),(32.0,46.0)
    ],
}
 
def geo_to_px(lon, lat, W, H, lon_min=22.0, lon_max=40.5, lat_min=44.2, lat_max=52.5):
    x = int((lon - lon_min) / (lon_max - lon_min) * W)
    y = int((lat_max - lat) / (lat_max - lat_min) * H)
    return x, y
 
def generate_alert_map(active_regions: list) -> bytes:
    W, H = 960, 640
    img = Image.new("RGB", (W, H), (15, 15, 25))
    draw = ImageDraw.Draw(img)
 
    active_lower = [r.lower() for r in active_regions]
 
    for region_name, coords in REGION_SHAPES.items():
        pts = [geo_to_px(lon, lat, W, H) for lon, lat in coords]
        is_alert = any(
            region_name.lower() in a or a in region_name.lower()
            for a in active_lower
        )
 
        if is_alert:
            fill    = (200, 30, 30)
            outline = (255, 80, 80)
            glow    = (160, 20, 20)
        else:
            fill    = (35, 70, 45)
            outline = (55, 100, 65)
            glow    = None
 
        # Малюємо регіон
        if glow:
            # Ефект свічення для тривожних регіонів
            big_pts = pts  # спрощено
            draw.polygon(pts, fill=glow, outline=None)
        draw.polygon(pts, fill=fill, outline=outline)
 
        # Центр і назва
        cx = sum(p[0] for p in pts) // len(pts)
        cy = sum(p[1] for p in pts) // len(pts)
        short = (region_name
                 .replace(" область", "")
                 .replace("м. ", ""))
 
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
        except Exception:
            font = ImageFont.load_default()
 
        draw.text((cx+1, cy+1), short, fill=(0,0,0,200), font=font, anchor="mm")
        draw.text((cx, cy), short, fill=(230,230,230), font=font, anchor="mm")
 
    # Легенда
    try:
        font_b = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 15)
    except Exception:
        font_b = ImageFont.load_default()
 
    legend_y = H - 38
    draw.rectangle([15, legend_y, 35, legend_y+20], fill=(200,30,30), outline=(255,80,80))
    draw.text((42, legend_y+10), "Тривога", fill=(255,255,255), font=font_b, anchor="lm")
    draw.rectangle([120, legend_y, 140, legend_y+20], fill=(35,70,45), outline=(55,100,65))
    draw.text((147, legend_y+10), "Тихо", fill=(255,255,255), font=font_b, anchor="lm")
 
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()
 
 
 
 
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
 
 
from PIL import Image, ImageDraw, ImageFont
import io
 
# Реальні спрощені контури регіонів (longitude, latitude)
 
 
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
        return json.loads(val)
    except Exception as e:
        print(f"[Redis GET '{key}'] {e}")
        return default
 
def r_set(key, value):
    if not UPSTASH_URL:
        return
    try:
        requests.post(
            f"{UPSTASH_URL}/set/{key}",
            headers={
                "Authorization": f"Bearer {UPSTASH_TOKEN}",
                "Content-Type": "application/json",
            },
            json={"value": json.dumps(value, ensure_ascii=False)},
            timeout=5,
        )
    except Exception as e:
        print(f"[Redis SET '{key}'] {e}")
 
def r_get_str(key, default=""):
    """Зчитує простий рядок (не JSON)."""
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
    """Зберігає простий рядок."""
    if not UPSTASH_URL:
        return
    try:
        requests.post(
            f"{UPSTASH_URL}/set/{key}",
            headers={
                "Authorization": f"Bearer {UPSTASH_TOKEN}",
                "Content-Type": "application/json",
            },
            json={"value": value},
            timeout=5,
        )
    except Exception as e:
        print(f"[Redis SET_STR '{key}'] {e}")
 
 
# ── Стан ─────────────────────────────────────────────────────────────────────
 
def load_state():
    titles_raw = r_get("sent_titles", [])
    titles = set(titles_raw) if isinstance(titles_raw, list) else set()
 
    idx_raw = r_get("feed_index", 0)
    idx = idx_raw if isinstance(idx_raw, int) else 0
 
    alert_hash = r_get_str("alert_hash", "")
 
    print(f"[Start] Заголовків: {len(titles)}, сайт: {RSS_FEEDS[idx % len(RSS_FEEDS)][0]}, хеш тривог: '{alert_hash[:30]}'")
    return titles, idx, alert_hash
 
sent_titles, feed_index, last_alert_hash = load_state()
 
 
# ── Telegram ──────────────────────────────────────────────────────────────────
 
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
 
 
# ── Допоміжні ─────────────────────────────────────────────────────────────────
 
def normalize(title: str) -> str:
    return " ".join(title.lower().split())
 
def now_str() -> str:
    return datetime.now(KYIV_TZ).strftime("%H:%M:%S")
 
def get_max_age_minutes() -> int:
    hour = datetime.now(KYIV_TZ).hour
    return 180 if hour < 7 else 60
 
def entry_time(entry) -> datetime | None:
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
 
 
# ── Новини ────────────────────────────────────────────────────────────────────
 
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
            print(f"[{now_str()}] [{source_name}] Нема свіжих → наступний сайт")
        else:
            entry = sorted(fresh, key=lambda e: entry_time(e), reverse=True)[0]
            title = entry.get("title", "").strip()
            link  = entry.get("link",  "").strip()
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
 
    # Завжди переходимо до наступного сайту
    feed_index = (feed_index + 1) % len(RSS_FEEDS)
    r_set("feed_index", feed_index)
    print(f"[{now_str()}] → Наступний: {RSS_FEEDS[feed_index][0]}")
 
 
# ── Тривоги ───────────────────────────────────────────────────────────────────
 
def check_alerts():
    global last_alert_hash
    print(f"[{now_str()}] Перевірка тривог...")
 
    try:
        resp = requests.get(
            "https://alerts.com.ua/api/states",
            headers={"X-API-Key": "volumetric"},
            timeout=10,
        )
        resp.raise_for_status()
        states = resp.json().get("states", [])
        active = sorted([s["name"] for s in states if s.get("alert")])
        current_hash = ",".join(active)
 
        # Не відправляємо якщо нічого не змінилось
        if current_hash == last_alert_hash:
            print(f"[{now_str()}] Тривоги не змінились — пропускаємо")
            return
 
        last_alert_hash = current_hash
        r_set_str("alert_hash", current_hash)
 
        timestamp = datetime.now(KYIV_TZ).strftime("%H:%M, %d.%m.%Y")
        if not active:
            caption = f"<b>🚨 Карта тривог</b> | {timestamp}\n\n🟢 Наразі по всій Україні тихо."
        else:
            regions_text = "\n".join(f"🔴 {r}" for r in active)
            caption = f"<b>🚨 Повітряна тривога!</b> | {timestamp}\n\n{regions_text}"
 
        # Генеруємо карту
        try:
            img_bytes = generate_alert_map(active)
            tg_send_photo(img_bytes, caption)
            print(f"[{datetime.now(KYIV_TZ).strftime("%H:%M:%S")}] ✅ Карту відправлено")
        except Exception as e:
            print(f"[Map Error] {e}")
            tg_send(caption)
 
        print(f"[{now_str()}] ✅ Тривоги відправлено: {len(active)} регіонів.")
 
    except Exception as e:
        print(f"[Alerts Error] {e}")
 
 
# ── Запуск ────────────────────────────────────────────────────────────────────
 
if __name__ == "__main__":
    print("🤖 Бот запущено!")
 
    # При старті — тільки новину. Тривогу НЕ відправляємо
    # (щоб не дублювати при частих рестартах Railway)
    check_news()
 
    schedule.every(15).minutes.do(check_news)
    schedule.every(30).minutes.do(check_alerts)
 
    while True:
        schedule.run_pending()
        time.sleep(30)import time
import json
import os
import feedparser
import requests
import schedule
import urllib3
from datetime import datetime, timezone, timedelta
 
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
 
from PIL import Image, ImageDraw, ImageFont
import io, math
 
# Реальні спрощені контури регіонів України (lon, lat пари)
# Джерело: спрощені GeoJSON дані
REGION_SHAPES = {
    "Вінницька область": [
        (28.1,49.9),(29.8,49.8),(30.1,48.9),(29.2,48.4),(27.7,48.5),(27.2,49.0),(27.8,49.6)
    ],
    "Волинська область": [
        (23.5,52.3),(25.3,52.4),(25.8,51.5),(24.7,51.1),(23.3,51.3),(23.0,51.9)
    ],
    "Дніпропетровська область": [
        (33.2,49.4),(35.4,49.2),(35.8,47.9),(34.5,47.3),(32.8,47.5),(32.3,48.3),(33.0,49.0)
    ],
    "Донецька область": [
        (36.5,49.2),(38.9,48.3),(39.2,47.5),(38.0,47.1),(36.3,47.4),(35.7,48.3),(36.2,48.9)
    ],
    "Житомирська область": [
        (27.4,51.8),(29.8,51.9),(30.4,50.8),(29.3,50.2),(27.5,50.3),(26.8,50.9),(27.1,51.5)
    ],
    "Закарпатська область": [
        (22.2,48.7),(23.9,49.0),(24.5,48.5),(23.8,47.9),(22.5,47.9),(22.0,48.2)
    ],
    "Запорізька область": [
        (34.5,48.1),(36.5,47.9),(36.9,46.7),(35.6,46.0),(34.0,46.3),(33.5,47.1),(34.1,47.8)
    ],
    "Івано-Франківська область": [
        (23.7,49.4),(25.2,49.5),(25.5,48.8),(24.8,48.2),(23.5,48.2),(23.0,48.7),(23.4,49.2)
    ],
    "Київська область": [
        (29.2,51.6),(31.8,51.7),(32.3,50.6),(31.0,50.0),(29.0,50.1),(28.3,50.7),(28.9,51.3)
    ],
    "Кіровоградська область": [
        (30.3,49.5),(32.5,49.4),(33.0,48.3),(32.0,47.7),(29.9,47.9),(29.3,48.6),(29.9,49.2)
    ],
    "Луганська область": [
        (38.0,49.5),(39.8,48.8),(40.2,48.0),(39.0,47.6),(37.0,47.9),(36.4,48.8),(37.5,49.3)
    ],
    "Львівська область": [
        (22.6,50.8),(24.7,50.8),(25.3,49.9),(24.4,49.3),(22.8,49.2),(22.0,49.7),(22.3,50.4)
    ],
    "Миколаївська область": [
        (30.0,48.0),(32.3,47.8),(32.8,46.8),(31.5,46.2),(29.8,46.4),(29.2,47.3),(29.7,47.8)
    ],
    "Одеська область": [
        (27.5,47.7),(30.0,48.1),(30.5,46.9),(29.5,45.5),(28.0,45.3),(27.0,45.8),(27.0,46.9)
    ],
    "Полтавська область": [
        (32.5,50.4),(34.8,50.3),(35.3,49.2),(34.1,48.6),(32.2,48.8),(31.7,49.6),(32.2,50.2)
    ],
    "Рівненська область": [
        (25.2,51.8),(27.2,51.9),(27.8,51.0),(26.7,50.5),(25.0,50.5),(24.5,51.1),(24.9,51.6)
    ],
    "Сумська область": [
        (33.3,52.4),(35.4,52.1),(35.8,51.0),(34.5,50.5),(32.5,50.7),(31.9,51.5),(32.9,52.1)
    ],
    "Тернопільська область": [
        (24.8,50.2),(26.5,50.1),(27.0,49.4),(26.1,48.9),(24.5,49.0),(23.9,49.5),(24.5,50.0)
    ],
    "Харківська область": [
        (35.4,50.7),(37.6,50.5),(38.3,49.4),(37.0,48.8),(35.0,49.0),(34.3,49.9),(35.0,50.5)
    ],
    "Херсонська область": [
        (32.8,47.2),(34.7,47.0),(35.2,46.0),(33.9,45.5),(32.2,45.7),(31.5,46.5),(32.3,47.0)
    ],
    "Хмельницька область": [
        (26.1,50.5),(28.2,50.4),(28.8,49.7),(27.8,49.0),(26.2,49.1),(25.4,49.7),(25.8,50.3)
    ],
    "Черкаська область": [
        (30.2,50.0),(32.0,49.9),(32.5,49.1),(31.4,48.5),(29.7,48.7),(29.1,49.4),(29.8,49.9)
    ],
    "Чернівецька область": [
        (25.1,48.7),(26.9,48.5),(27.5,47.9),(26.7,47.5),(25.3,47.5),(24.7,48.0),(24.9,48.5)
    ],
    "Чернігівська область": [
        (30.4,52.4),(33.5,52.3),(33.9,51.1),(32.5,50.6),(30.0,50.7),(29.2,51.5),(30.0,52.1)
    ],
    "м. Київ": [
        (30.3,50.7),(30.7,50.7),(30.8,50.4),(30.5,50.3),(30.2,50.4),(30.2,50.6)
    ],
    "Крим": [
        (32.5,46.2),(35.0,45.9),(36.6,45.2),(35.8,44.4),(34.0,44.3),(32.5,44.7),(31.5,45.3),(32.0,46.0)
    ],
}
 
def geo_to_px(lon, lat, W, H, lon_min=22.0, lon_max=40.5, lat_min=44.2, lat_max=52.5):
    x = int((lon - lon_min) / (lon_max - lon_min) * W)
    y = int((lat_max - lat) / (lat_max - lat_min) * H)
    return x, y
 
def generate_alert_map(active_regions: list) -> bytes:
    W, H = 960, 640
    img = Image.new("RGB", (W, H), (15, 15, 25))
    draw = ImageDraw.Draw(img)
 
    active_lower = [r.lower() for r in active_regions]
 
    for region_name, coords in REGION_SHAPES.items():
        pts = [geo_to_px(lon, lat, W, H) for lon, lat in coords]
        is_alert = any(
            region_name.lower() in a or a in region_name.lower()
            for a in active_lower
        )
 
        if is_alert:
            fill    = (200, 30, 30)
            outline = (255, 80, 80)
            glow    = (160, 20, 20)
        else:
            fill    = (35, 70, 45)
            outline = (55, 100, 65)
            glow    = None
 
        # Малюємо регіон
        if glow:
            # Ефект свічення для тривожних регіонів
            big_pts = pts  # спрощено
            draw.polygon(pts, fill=glow, outline=None)
        draw.polygon(pts, fill=fill, outline=outline)
 
        # Центр і назва
        cx = sum(p[0] for p in pts) // len(pts)
        cy = sum(p[1] for p in pts) // len(pts)
        short = (region_name
                 .replace(" область", "")
                 .replace("м. ", ""))
 
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
        except Exception:
            font = ImageFont.load_default()
 
        draw.text((cx+1, cy+1), short, fill=(0,0,0,200), font=font, anchor="mm")
        draw.text((cx, cy), short, fill=(230,230,230), font=font, anchor="mm")
 
    # Легенда
    try:
        font_b = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 15)
    except Exception:
        font_b = ImageFont.load_default()
 
    legend_y = H - 38
    draw.rectangle([15, legend_y, 35, legend_y+20], fill=(200,30,30), outline=(255,80,80))
    draw.text((42, legend_y+10), "Тривога", fill=(255,255,255), font=font_b, anchor="lm")
    draw.rectangle([120, legend_y, 140, legend_y+20], fill=(35,70,45), outline=(55,100,65))
    draw.text((147, legend_y+10), "Тихо", fill=(255,255,255), font=font_b, anchor="lm")
 
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()
 
 
 
 
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
 
 
from PIL import Image, ImageDraw, ImageFont
import io
 
# Реальні спрощені контури регіонів (longitude, latitude)
 
 
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
        return json.loads(val)
    except Exception as e:
        print(f"[Redis GET '{key}'] {e}")
        return default
 
def r_set(key, value):
    if not UPSTASH_URL:
        return
    try:
        requests.post(
            f"{UPSTASH_URL}/set/{key}",
            headers={
                "Authorization": f"Bearer {UPSTASH_TOKEN}",
                "Content-Type": "application/json",
            },
            json={"value": json.dumps(value, ensure_ascii=False)},
            timeout=5,
        )
    except Exception as e:
        print(f"[Redis SET '{key}'] {e}")
 
def r_get_str(key, default=""):
    """Зчитує простий рядок (не JSON)."""
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
    """Зберігає простий рядок."""
    if not UPSTASH_URL:
        return
    try:
        requests.post(
            f"{UPSTASH_URL}/set/{key}",
            headers={
                "Authorization": f"Bearer {UPSTASH_TOKEN}",
                "Content-Type": "application/json",
            },
            json={"value": value},
            timeout=5,
        )
    except Exception as e:
        print(f"[Redis SET_STR '{key}'] {e}")
 
 
# ── Стан ─────────────────────────────────────────────────────────────────────
 
def load_state():
    titles_raw = r_get("sent_titles", [])
    titles = set(titles_raw) if isinstance(titles_raw, list) else set()
 
    idx_raw = r_get("feed_index", 0)
    idx = idx_raw if isinstance(idx_raw, int) else 0
 
    alert_hash = r_get_str("alert_hash", "")
 
    print(f"[Start] Заголовків: {len(titles)}, сайт: {RSS_FEEDS[idx % len(RSS_FEEDS)][0]}, хеш тривог: '{alert_hash[:30]}'")
    return titles, idx, alert_hash
 
sent_titles, feed_index, last_alert_hash = load_state()
 
 
# ── Telegram ──────────────────────────────────────────────────────────────────
 
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
 
 
# ── Допоміжні ─────────────────────────────────────────────────────────────────
 
def normalize(title: str) -> str:
    return " ".join(title.lower().split())
 
def now_str() -> str:
    return datetime.now(KYIV_TZ).strftime("%H:%M:%S")
 
def get_max_age_minutes() -> int:
    hour = datetime.now(KYIV_TZ).hour
    return 180 if hour < 7 else 60
 
def entry_time(entry) -> datetime | None:
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
 
 
# ── Новини ────────────────────────────────────────────────────────────────────
 
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
            print(f"[{now_str()}] [{source_name}] Нема свіжих → наступний сайт")
        else:
            entry = sorted(fresh, key=lambda e: entry_time(e), reverse=True)[0]
            title = entry.get("title", "").strip()
            link  = entry.get("link",  "").strip()
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
 
    # Завжди переходимо до наступного сайту
    feed_index = (feed_index + 1) % len(RSS_FEEDS)
    r_set("feed_index", feed_index)
    print(f"[{now_str()}] → Наступний: {RSS_FEEDS[feed_index][0]}")
 
 
# ── Тривоги ───────────────────────────────────────────────────────────────────
 
def check_alerts():
    global last_alert_hash
    print(f"[{now_str()}] Перевірка тривог...")
 
    try:
        resp = requests.get(
            "https://alerts.com.ua/api/states",
            headers={"X-API-Key": "volumetric"},
            timeout=10,
        )
        resp.raise_for_status()
        states = resp.json().get("states", [])
        active = sorted([s["name"] for s in states if s.get("alert")])
        current_hash = ",".join(active)
 
        # Не відправляємо якщо нічого не змінилось
        if current_hash == last_alert_hash:
            print(f"[{now_str()}] Тривоги не змінились — пропускаємо")
            return
 
        last_alert_hash = current_hash
        r_set_str("alert_hash", current_hash)
 
        timestamp = datetime.now(KYIV_TZ).strftime("%H:%M, %d.%m.%Y")
        if not active:
            caption = f"<b>🚨 Карта тривог</b> | {timestamp}\n\n🟢 Наразі по всій Україні тихо."
        else:
            regions_text = "\n".join(f"🔴 {r}" for r in active)
            caption = f"<b>🚨 Повітряна тривога!</b> | {timestamp}\n\n{regions_text}"
 
        # Генеруємо карту
        try:
            img_bytes = generate_alert_map(active)
            tg_send_photo(img_bytes, caption)
            print(f"[{datetime.now(KYIV_TZ).strftime("%H:%M:%S")}] ✅ Карту відправлено")
        except Exception as e:
            print(f"[Map Error] {e}")
            tg_send(caption)
 
        print(f"[{now_str()}] ✅ Тривоги відправлено: {len(active)} регіонів.")
 
    except Exception as e:
        print(f"[Alerts Error] {e}")
 
 
# ── Запуск ────────────────────────────────────────────────────────────────────
 
if __name__ == "__main__":
    print("🤖 Бот запущено!")
 
    # При старті — тільки новину. Тривогу НЕ відправляємо
    # (щоб не дублювати при частих рестартах Railway)
    check_news()
 
    schedule.every(15).minutes.do(check_news)
    schedule.every(30).minutes.do(check_alerts)
 
    while True:
        schedule.run_pending()
        time.sleep(30)
