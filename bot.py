import os
import time
import feedparser
import requests
import schedule

# --- НАЛАШТУВАННЯ ---
TOKEN = "8847992261:AAGlg560Vo60cV2uIYNRwfDTgUcZdPun5eQ"
CHANNEL_ID = "@novini_ua_10"

RSS_URLS = [
    "https://feeds.bbci.co.uk/ukrainian/rss.xml",
    "https://www.pravda.com.ua/rss/",
    "https://rss.unian.net/site/news_ukr.rss",
    "https://tsn.ua/rss/full.rss",
    "https://www.rbc.ua/static/rss/news_ukr.xml",
    "https://censor.net/ua/rss/news"
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
    print("🔄 Перевіряю наявність нових новин...")
    published_links = load_published_links()

    for url in RSS_URLS:
        try:
            feed = feedparser.parse(url)
            # Беремо лише останні 5 новин, щоб уникнути дублів після перезапуску
            entries = list(reversed(feed.entries))[:5]

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
                    print(f"🟢 Опубліковано: {title[:30]}...")
                    time.sleep(3) 
        except Exception as e:
            print(f"🔴 Помилка стрічки {url}: {e}")

def send_alerts_map():
    print("🚨 Формую зведення повітряних тривог...")
    try:
        response = requests.get("https://war-api.ukrzen.in.ua/alerts/api/alerts/active.json")
        if response.status_code == 200:
            data = response.json()
            alerts = data.get("alerts", [])
            if not alerts:
                message = "<b>🚨 Карта тривог України</b>\n\n🟢 <b>Наразі в усій Україні тихо.</b>"
            else:
                active_places = sorted(list(set([item.get("location_title", "Невідомий регіон") for item in alerts])))
                places_text = "\n".join([f"🔴 {loc}" for loc in active_places])
                message = f"<b>🚨 Карта тривог України</b>\n\n<b>Регіони з тривогою:</b>\n\n{places_text}\n\n⚠️ <i>Перебувайте в укриттях!</i>"
            
            send_to_telegram(message)
    except Exception as e:
        print(f"🔴 Помилка мапи тривог: {e}")

if __name__ == "__main__":
    print("🤖 Бот запущений!")
    check_news()
    send_alerts_map()
    
    schedule.every(15).minutes.do(check_news) # Збільшив інтервал до 15 хв
    schedule.every(1).hours.do(send_alerts_map)

    while True:
        schedule.run_pending()
        time.sleep(1)
