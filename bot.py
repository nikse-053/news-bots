import os
import time
import feedparser
import requests
import schedule
from datetime import datetime, timedelta
import time as time_module

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
    payload = {"chat_id": CHANNEL_ID, "text": text, "parse_mode": "HTML"}
    try:
        response = requests.post(url, json=payload)
        # Якщо забагато запитів - чекаємо
        if response.status_code == 429:
            retry_after = response.json().get("parameters", {}).get("retry_after", 30)
            time.sleep(retry_after)
    except Exception as e:
        print(f"🔴 Помилка: {e}")

def check_news():
    print("🔄 Перевірка новин...")
    # Публікуємо лише те, що вийшло за останні 2 години
    time_limit = datetime.now() - timedelta(hours=2)

    for url in RSS_URLS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:3]: # Обмежили до 3 новини за раз
                if hasattr(entry, 'published_parsed'):
                    pub_time = datetime.fromtimestamp(time_module.mktime(entry.published_parsed))
                    if pub_time < time_limit: continue
                
                title = entry.title
                message = f"<b>📰 {title}</b>\n\n<a href='{entry.link}'>Читати повністю...</a>"
                send_to_telegram(message)
                time.sleep(5) # Пауза між повідомленнями, щоб не отримати бан
        except Exception as e:
            print(f"🔴 Помилка RSS: {e}")

def send_alerts_map():
    print("🚨 Формую мапу тривог...")
    try:
        # verify=False ігнорує помилку сертифіката
        response = requests.get("https://war-api.ukrzen.in.ua/alerts/api/alerts/active.json", verify=False)
        if response.status_code == 200:
            alerts = response.json().get("alerts", [])
            message = "<b>🚨 Карта тривог</b>\n\n🟢 Тихо." if not alerts else "<b>🚨 Тривога в:</b>\n" + "\n".join([f"🔴 {item.get('location_title')}" for item in alerts])
            send_to_telegram(message)
    except Exception as e:
        print(f"🔴 Помилка мапи: {e}")

if __name__ == "__main__":
    schedule.every(30).minutes.do(check_news)
    schedule.every(1).hours.do(send_alerts_map)
    while True:
        schedule.run_pending()
        time.sleep(1)
