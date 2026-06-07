import time
import feedparser
import requests
import schedule
import os
import urllib3
from datetime import datetime, timezone, timedelta

# Ігноруємо помилки SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TOKEN = os.environ.get("TOKEN", "8847992261:AAGlg560Vo60cV2uIYNRwfDTgUcZdPun5eQ")
CHANNEL_ID = "@novini_ua_10"

# Список джерел
RSS_FEEDS = [
    "https://feeds.bbci.co.uk/ukrainian/rss.xml",
    "https://www.pravda.com.ua/rss/",
    "https://rss.unian.net/site/news_ukr.rss"
]

def send_tg(text):
    try:
        # verify=False ігнорує помилку сертифіката, про яку ти питав
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                      json={"chat_id": CHANNEL_ID, "text": text, "parse_mode": "HTML"}, 
                      timeout=10, verify=False)
        time.sleep(1) # Затримка, щоб не отримати бан (429 Error)
    except Exception as e:
        print(f"TG Error: {e}")

def job():
    print("Перевірка новин...")
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            if feed.entries:
                entry = feed.entries[0]
                send_tg(f"<b>{entry.title}</b>\n<a href='{entry.link}'>Читати</a>")
                break 
        except Exception as e:
            print(f"RSS Error: {e}")

if __name__ == "__main__":
    print("Бот запущено!")
    schedule.every(15).minutes.do(job)
    
    # "Бронебійний" цикл
    while True:
        try:
            schedule.run_pending()
        except Exception as e:
            print(f"Критична помилка: {e}")
        time.sleep(30)
