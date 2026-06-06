import time
import feedparser
import requests
import schedule
import urllib3
from datetime import datetime, timedelta

# Вимикаємо помилки SSL для карти тривог
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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

recent_titles = []

def send_to_telegram(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHANNEL_ID, "text": text, "parse_mode": "HTML"}
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 429: # Якщо Телеграм каже "забагато запитів"
            time.sleep(30)
    except: pass

def check_news():
    global recent_titles
    limit = datetime.now() - timedelta(hours=3)
    
    for url in RSS_URLS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:3]:
                title = entry.title.strip()
                if title in recent_titles: continue
                
                if hasattr(entry, 'published_parsed'):
                    pub_time = datetime.fromtimestamp(time.mktime(entry.published_parsed))
                    if pub_time < limit: continue
                
                message = f"<b>📰 {title}</b>\n\n🕒 <i>{datetime.now().strftime('%H:%M')}</i>\n\n<a href='{entry.link}'>Читати...</a>"
                send_to_telegram(message)
                recent_titles.append(title)
                if len(recent_titles) > 50: recent_titles.pop(0)
                time.sleep(15) 
        except: continue

def send_alerts_map():
    try:
        resp = requests.get("https://war-api.ukrzen.in.ua/alerts/api/alerts/active.json", verify=False, timeout=10)
        alerts = resp.json().get("alerts", [])
        msg = f"<b>🚨 Карта тривог ({datetime.now().strftime('%H:%M')})</b>\n\n"
        msg += "🟢 Наразі тихо." if not alerts else "<b>Тривога в:</b>\n" + "\n".join([f"🔴 {i.get('location_title')}" for i in alerts if i.get('location_title')])
        send_to_telegram(msg)
    except: pass

if __name__ == "__main__":
    check_news()
    send_alerts_map()
    schedule.every(15).minutes.do(check_news)
    schedule.every(1).hours.do(send_alerts_map)
    while True:
        schedule.run_pending()
        time.sleep(60)
