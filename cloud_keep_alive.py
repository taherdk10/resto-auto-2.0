import os
import json
import time
import socket
import urllib.request
import urllib.error

# ==========================================
# FORCE IPv4 TO PREVENT [Errno 101] ERRORS
# ==========================================
old_getaddrinfo = socket.getaddrinfo
def new_getaddrinfo(*args, **kwargs):
    responses = old_getaddrinfo(*args, **kwargs)
    return [response for response in responses if response[0] == socket.AF_INET]
socket.getaddrinfo = new_getaddrinfo

# ==========================================
# CONFIGURATION
# ==========================================
GIST_ID = os.environ.get("GIST_ID")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

TARGET_URL = "https://quickcardcampus.digi-sys.net/dashboard/admin/restaurant.php?page=reservation"
MAX_RETRIES = 3
REQUEST_TIMEOUT = 20  # Seconds to wait for slow SSL handshakes


def send_telegram_alert(message, chat_id=None):
    target_chat = chat_id or TELEGRAM_CHAT_ID
    if not TELEGRAM_BOT_TOKEN or not target_chat:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id": target_chat,
        "text": message,
        "parse_mode": "Markdown"
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"Failed to send Telegram alert: {e}")


def fetch_sessions():
    url = f"https://api.github.com/gists/{GIST_ID}"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "INSAT-KeepAlive",
            "Cache-Control": "no-cache"
        }
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        data = json.loads(response.read().decode("utf-8"))
        return json.loads(data["files"]["sessions.json"]["content"])


def ping_account(name, phpsessid, user_chat_id):
    req = urllib.request.Request(
        TARGET_URL,
        headers={
            "Cookie": f"PHPSESSID={phpsessid}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Connection": "keep-alive"
        }
    )

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
                final_url = response.geturl()
                html = response.read().decode("utf-8", errors="ignore")

                # Check if redirected to login or if login form is present
                if "login" in final_url.lower() or 'id="pseudo"' in html:
                    print(f"🚨 Session EXPIRED for {name}!")
                    send_telegram_alert(
                        f"🚨 *INSAT Session Alert*\nSession EXPIRED for account: *{name}*!\nRun `tokens.py` locally to refresh.",
                        user_chat_id
                    )
                    return False

                print(f"✅ Ping OK for {name} (Attempt {attempt})")
                return True

        except Exception as e:
            print(f"⚠️ Attempt {attempt}/{MAX_RETRIES} failed for {name}: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(3 * attempt)  # Wait 3s, then 6s before retrying
            else:
                print(f"❌ All {MAX_RETRIES} ping attempts failed for {name} due to network timeout.")
                return False


def main():
    if not GIST_ID:
        print("❌ GIST_ID environment variable is missing.")
        return

    try:
        sessions = fetch_sessions()
    except Exception as e:
        print(f"❌ Failed to fetch sessions from Gist: {e}")
        return

    for name, info in sessions.items():
        phpsessid = info.get("phpsessid")
        chat_id = info.get("chat_id")
        if phpsessid:
            ping_account(name, phpsessid, chat_id)
            time.sleep(1.5)  # Small pause between accounts so server doesn't rate-limit


if __name__ == "__main__":
    main()
