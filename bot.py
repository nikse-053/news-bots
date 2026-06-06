import os
import time
import feedparser
import requests
import schedule

# --- НАЛАШТУВАННЯ ---
TOKEN = "8847992261:AAGlg560Vo60cV2uIYNRwfDTgUcZdPun5eQ"
CHANNEL_ID = "@novini_ua_10"

# Розширений список джерел новин (6 сайтів)
RSS_URLS = [
    "https://feeds.bbci.co.uk/ukrainian/rss.xml",     # BBC Україна
    "https://www.pravda.com.ua/rss/",                 # Українська Правда
    "https://rss.unian.net/site/news_ukr.rss",         # УНІАН
    "https://tsn.ua/rss/full.rss",                    # ТСН
    "https://www.rbc.ua/static/rss/news_ukr.xml",     # РБК-Україна
    "https://censor.net/ua/rss/news"                  # Цензор.НЕТ
]

DB_FILE = "published_news.txt"


def load_published_links():
    if not os.path.exists(DB_FILE):
        return set()
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f.readlines())


def save_published_link(link):
    with open(DB_FILE, "a", encoding="utf-8") as f:
        f.write(link + "\n")


def send_to_telegram(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHANNEL_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": False}
    try:
        response = requests.post(url, json=payload)
        if response.status_code != 200:
            print(f"🔴 Помилка Telegram API: {response.text}")
    except Exception as e:
        print(f"🔴 Помилка відправки: {e}")


def check_news():
    print("🔄 Перевіряю наявність нових новин з усіх джерел...")
    published_links = load_published_links()

    for url in RSS_URLS:
        try:
            feed = feedparser.parse(url)
            entries = reversed(feed.entries)

            for entry in entries:
                link = entry.link

                if link not in published_links:
                    title = entry.title
                    summary = getattr(entry, "summary", "")
                    
                    if len(summary) > 300:
                        summary = summary[:300] + "..."

                    message = f"<b>📰 {title}</b>\n\n{summary}\n\n<a href='{link}'>Читати повністю...</a>"

                    send_to_telegram(message)
                    save_published_link(link)
                    print(f"🟢 Опубліковано новину: {title[:30]}...")
                    time.sleep(3) 
        except Exception as e:
            print(f"🔴 Помилка при читанні стрічки {url}: {e}")


def send_alerts_map():
    print("🚨 Формую зведення повітряних тривог...")
    try:
        # Отримуємо дані про активні тривоги
        response = requests.get("https://war-api.ukrzen.in.ua/alerts/api/alerts/active.json")
        if response.status_code == 200:
            data = response.json()
            alerts = data.get("alerts", [])
            
            if not alerts:
                message = "<b>🚨 Карта тривог України</b>\n\n🟢 <b>Наразі в усій Україні тихо. Активних тривог немає!</b>"
            else:
                active_places = []
                for item in alerts:
                    # Беремо назву області або міста
                    location = item.get("location_title", "Невідомий регіон")
                    active_places.append(f"🔴 {location}")
                
                # Прибираємо дублікати, якщо є
                active_places = sorted(list(set(active_places)))
                places_text = "\n".join(active_places)
                
                message = f"<b>🚨 Карта тривог України (Зведення за годину)</b>\n\n<b>Регіони, де зараз оголошено повітряну тривогу:</b>\n\n{places_text}\n\n⚠️ <i>Перебувайте в укриттях!</i>"
            
            send_to_telegram(message)
            print("🟢 Зведення тривог успішно надіслано в канал!")
        else:
            print("🔴 Не вдалося отримати дані про тривоги")
    except Exception as e:
        print(f"🔴 Помилка при отриманні мапи тривог: {e}")


if __name__ == "__main__":
    print("🤖 Бот із новинами та картою тривог успішно запущений!")
    
    # Перший запуск при включенні
    check_news()
    send_alerts_map()
    
    # Розклад для хостингу
    schedule.every(5).minutes.do(check_news)       # Перевірка новин кожні 5 хвилин
    schedule.every(1).hours.do(send_alerts_map)    # Зведення тривог рівно раз на годину

    while True:
        schedule.run_pending()
        time.sleep(1)
