import os
import json
import urllib.request

GIST_ID = os.environ.get("GIST_ID")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")  # YOUR Admin Chat ID secret

if not GIST_ID:
    raise ValueError("❌ Missing GIST_ID environment variable.")

GIST_RAW_URL = f"https://gist.githubusercontent.com/raw/{GIST_ID}/sessions.json"
PING_URL = "https://quickcardcampus.digi-sys.net/dashboard/admin/restaurant.php?page=reservation"

def send_telegram(message, target_chat_id):
    """Sends Telegram message only if target_chat_id is valid and non-empty."""
    if not TELEGRAM_BOT_TOKEN or not target_chat_id:
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id": target_chat_id,
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
    if not GIST_ID:
        print("❌ Missing GIST_ID environment variable.")
        return {}

    # Hits GitHub API directly to bypass 5-minute raw Gist CDN caching
    api_url = f"https://api.github.com/gists/{GIST_ID}"
    try:
        req = urllib.request.Request(
            api_url, 
            headers={
                "User-Agent": "INSAT-Bot",
                "Accept": "application/vnd.github.v3+json",
                "Cache-Control": "no-cache"
            }
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data["files"]["sessions.json"]["content"]
            return json.loads(content)
    except Exception as e:
        print(f"⚠️ Error fetching tokens from Gist API: {e}")
        return {}

def ping_portal():
    tokens = fetch_tokens()
    if not tokens:
        print("❌ No active tokens found in Gist.")
        return

    for name, data in tokens.items():
        # Handle both dict structure and legacy string structure
        if isinstance(data, dict):
            phpsessid = data.get("phpsessid")
            user_chat_id = data.get("chat_id")
        else:
            phpsessid = data
            user_chat_id = ""

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
                    msg = f"🚨 *INSAT Session Alert*\nSession EXPIRED for account: *{name}*!\nRun `tokens.py` locally to refresh."
                    print(msg)
                    
                    # ALWAYS notify YOU (Admin)
                    send_telegram(msg, ADMIN_CHAT_ID)
                    
                    # Notify user too IF they provided a Chat ID
                    if user_chat_id and user_chat_id != ADMIN_CHAT_ID:
                        send_telegram(msg, user_chat_id)
                else:
                    print(f"📡 Keep-alive ping SUCCESSFUL for [{name}].")
        except Exception as e:
            print(f"⚠️ Ping request failed for {name}: {e}")

if __name__ == "__main__":
    ping_portal()
