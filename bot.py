import time
import feedparser
import requests
import schedule
import urllib3
from datetime import datetime, timedelta

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

def get_current_time():
    # Повертає час у форматі "14:00"
    return datetime.now().strftime("%H:%M")

def send_to_telegram(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHANNEL_ID, "text": text, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload)
    except:
        pass

def check_news():
    global recent_titles
    limit = datetime.now() - timedelta(hours=3)
    time_str = get_current_time()
    
    for url in RSS_URLS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:3]:
                title = entry.title.strip()
                if title in recent_titles: continue
                
                if hasattr(entry, 'published_parsed'):
                    pub_time = datetime.fromtimestamp(time.mktime(entry.published_parsed))
                    if pub_time < limit: continue
                
                # Додаємо час у заголовок
                message = f"<b>📰 {title}</b>\n\n🕒 <i>Час: {time_str}</i>\n\n<a href='{entry.link}'>Читати повністю...</a>"
                send_to_telegram(message)
                
                recent_titles.append(title)
                if len(recent_titles) > 50: recent_titles.pop(0)
                time.sleep(15)
        except: continue

def send_alerts_map():
    time_str = get_current_time()
    try:
        resp = requests.get("https://war-api.ukrzen.in.ua/alerts/api/alerts/active.json", verify=False, timeout=10)
        alerts = resp.json().get("alerts", [])
        if not alerts:
            msg = f"<b>🚨 Карта тривог ({time_str})</b>\n🟢 Наразі тихо."
        else:
            locs = sorted(list(set([i.get("location_title") for i in locs if i.get("location_title")]))) # виправив логіку
            msg = f"<b>🚨 Тривога станом на {time_str}:</b>\n\n" + "\n".join([f"🔴 {l}" for l in locs])
        send_to_telegram(msg)
    except: pass

if __name__ == "__main__":
    schedule.every(15).minutes.do(check_news)
    schedule.every(1).hours.do(send_alerts_map)
    while True:
        schedule.run_pending()
        time.sleep(60)
