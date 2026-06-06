import os
import time
import feedparser
import requests
import schedule
from datetime import datetime, timedelta
import time as time_module

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

def send_to_telegram(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHANNEL_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": False}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"🔴 Помилка відправки: {e}")

def check_news():
    print("🔄 Перевіряю новини (фільтр 2 години)...")
    time_limit = datetime.now() - timedelta(hours=2)

    for url in RSS_URLS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]: # Беремо 5 нових новин
                # Перевірка часу публікації
                if hasattr(entry, 'published_parsed'):
                    pub_time = datetime.fromtimestamp(time_module.mktime(entry.published_parsed))
                    if pub_time < time_limit:
                        continue 
                
                title = entry.title
                summary = getattr(entry, "summary", "")
                if len(summary) > 300: summary = summary[:300] + "..."
                
                message = f"<b>📰 {title}</b>\n\n{summary}\n\n<a href='{entry.link}'>Читати повністю...</a>"
                send_to_telegram(message)
                time.sleep(3) 
        except Exception as e:
            print(f"🔴 Помилка: {e}")

def send_alerts_map():
    print("🚨 Перевірка тривог...")
    try:
        response = requests.get("https://war-api.ukrzen.in.ua/alerts/api/alerts/active.json")
        if response.status_code == 200:
            alerts = response.json().get("alerts", [])
            if not alerts:
                message = "<b>🚨 Карта тривог</b>\n\n🟢 <b>Наразі тихо.</b>"
            else:
                places = sorted(list(set([item.get("location_title", "Регіон") for item in alerts])))
                message = f"<b>🚨 Карта тривог</b>\n\n<b>Зараз тривога в:</b>\n\n" + "\n".join([f"🔴 {p}" for p in places])
            send_to_telegram(message)
    except Exception as e:
        print(f"🔴 Помилка мапи тривог: {e}")

if __name__ == "__main__":
    print("🤖 Бот запущений!")
    # Перший запуск
    check_news()
    send_alerts_map()
    
    # Розклад
    schedule.every(15).minutes.do(check_news)
    schedule.every(1).hours.do(send_alerts_map)

    while True:
        schedule.run_pending()
        time.sleep(1)
