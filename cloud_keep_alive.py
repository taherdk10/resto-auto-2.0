import os
import json
import urllib.request

# Environment Variables injected via GitHub Repository Secrets
GIST_ID = os.environ.get("GIST_ID")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

if not GIST_ID:
    raise ValueError("❌ Missing GIST_ID environment variable.")

GIST_RAW_URL = f"https://gist.githubusercontent.com/raw/{GIST_ID}/sessions.json"
PING_URL = "https://quickcardcampus.digi-sys.net/dashboard/admin/restaurant.php?page=reservation"

def send_alert(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram credentials not configured in secrets. Skipping alert.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }).encode("utf-8")
    
    try:
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req):
            pass
    except Exception as e:
        print(f"⚠️ Failed to send Telegram alert: {e}")

def fetch_tokens():
    try:
        req = urllib.request.Request(GIST_RAW_URL, headers={"Cache-Control": "no-cache"})
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"⚠️ Error fetching tokens from Gist: {e}")
        return {}

def ping_portal():
    tokens = fetch_tokens()
    if not tokens:
        print("❌ No active tokens found in Gist.")
        return

    for name, phpsessid in tokens.items():
        try:
            req = urllib.request.Request(
                PING_URL,
                headers={
                    "Cookie": f"PHPSESSID={phpsessid}",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                }
            )
            with urllib.request.urlopen(req) as resp:
                final_url = resp.geturl()
                if "resto.php" in final_url and "restaurant.php" not in final_url:
                    msg = f"🚨 *INSAT Session Alert*\nSession EXPIRED for account: *{name}*!\nRun `tokens.py` to refresh."
                    print(msg)
                    send_alert(msg)
                else:
                    print(f"📡 Keep-alive ping SUCCESSFUL for [{name}].")
        except Exception as e:
            print(f"⚠️ Ping request failed for {name}: {e}")

if __name__ == "__main__":
    ping_portal()