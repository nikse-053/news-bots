import time
import feedparser
import requests
import schedule
import os
from datetime import datetime, timezone, timedelta

# Налаштування
TOKEN = os.environ.get("TOKEN", "8847992261:AAGlg560Vo60cV2uIYNRwfDTgUcZdPun5eQ")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "@novini_ua_10")
ALERTS_API_KEY = os.environ.get("ALERTS_API_KEY", "") 

KYIV_TZ = timezone(timedelta(hours=3))
last_alert_states = set()

def tg_send(text: str):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={"chat_id": CHANNEL_ID, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        time.sleep(1) # Затримка для обходу лімітів Telegram
    except Exception as e:
        print(f"TG Error: {e}")

def check_alerts():
    global last_alert_states
    try:
        # Використовуємо офіційне API
        headers = {"Authorization": f"Bearer {ALERTS_API_KEY}"} if ALERTS_API_KEY else {}
        resp = requests.get("https://api.ukrainealarm.com/api/v3/alerts", headers=headers, timeout=10, verify=False)
        
        if resp.ok:
            data = resp.json()
            # Беремо тільки активні тривоги
            current_active = {r["regionName"] for r in data if r.get("activeAlerts")}
            
            # Шукаємо нові тривоги
            new_alerts = current_active - last_alert_states
            # Шукаємо ті, що закінчились
            ended_alerts = last_alert_states - current_active
            
            if new_alerts or ended_alerts:
                ts = datetime.now(KYIV_TZ).strftime("%H:%M")
                msg = [f"<b>🚨 Статус тривог</b> | {ts}"]
                
                if new_alerts:
                    msg.append(f"\n🔴 <b>Початок тривоги:</b>\n" + "\n".join(new_alerts))
                if ended_alerts:
                    msg.append(f"\n🟢 <b>Відбій:</b>\n" + "\n".join(ended_alerts))
                
                tg_send("\n".join(msg))
                last_alert_states = current_active
                
    except Exception as e:
        print(f"Alerts Error: {e}")

if __name__ == "__main__":
    print("🤖 Бот запущено (текстовий режим)!")
    schedule.every(30).seconds.do(check_alerts)
    
    while True:
        schedule.run_pending()
        time.sleep(10)
