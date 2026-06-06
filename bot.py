import time
import feedparser
import requests
import schedule
import urllib3
from datetime import datetime

# Щоб не було помилок SSL з картою тривог
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TOKEN = "8847992261:AAGlg560Vo60cV2uIYNRwfDTgUcZdPun5eQ"
CHANNEL_ID = "@novini_ua_10"

# Пам'ять для заголовків (не видаляється, поки бот працює)
recent_titles = []

def send_to_telegram(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHANNEL_ID, "text": text, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Помилка відправки: {e}")

def check_news():
    global recent_titles
    urls = [
        "https://feeds.bbci.co.uk/ukrainian/rss.xml",
        "https://www.pravda.com.ua/rss/",
        "https://rss.unian.net/site/news_ukr.rss",
        "https://tsn.ua/rss/full.rss",
        "https://www.rbc.ua/static/rss/news_ukr.xml",
        "https://censor.net/ua/rss/news"
    ]
    
    for url in urls:
        try:
            feed = feedparser.parse(url)
            # Беремо лише 3 свіжі новини
            for entry in feed.entries[:3]:
                title = entry.title.strip()
                if title in recent_titles: continue
                
                msg = f"<b>📰 {title}</b>\n\n<a href='{entry.link}'>Читати повністю...</a>"
                send_to_telegram(msg)
                
                recent_titles.append(title)
                if len(recent_titles) > 50: recent_titles.pop(0) # Пам'ятаємо 50 останніх
                time.sleep(10) # Пауза, щоб не отримати бан від Telegram
        except: continue

def send_alerts_map():
    try:
        # verify=False ігнорує помилку сертифіката
        resp = requests.get("https://war-api.ukrzen.in.ua/alerts/api/alerts/active.json", verify=False, timeout=10)
        alerts = resp.json().get("alerts", [])
        msg = "<b>🚨 Карта тривог</b>\n🟢 Наразі тихо." if not alerts else "<b>🚨 Тривога в:</b>\n" + "\n".join([f"🔴 {i.get('location_title')}" for i in alerts])
        send_to_telegram(msg)
    except: pass

if __name__ == "__main__":
    schedule.every(15).minutes.do(check_news)
    schedule.every(1).hours.do(send_alerts_map)
    while True:
        schedule.run_pending()
        time.sleep(60)
