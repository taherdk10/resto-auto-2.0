import os
import json
import time
import urllib.request
from playwright.sync_api import sync_playwright

TARGET_URL = "https://quickcardcampus.digi-sys.net/dashboard/admin/restaurant.php?page=reservation"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

GIST_ID = os.environ.get("GIST_ID")
ADMIN_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# Dual Bot Tokens (Falls back to TELEGRAM_BOT_TOKEN if single bot is used)
BOT1_TOKEN = os.environ.get("TELEGRAM_BOT1_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")  # System & Session Alerts
BOT2_TOKEN = os.environ.get("TELEGRAM_BOT2_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")  # Reservation Successes

def send_telegram(bot_token, message, target_chat_id):
    if not bot_token or not target_chat_id:
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
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

def send_system_alert(message, target_chat_id):
    """Routes warnings, errors, and expired token alerts through Bot 1."""
    send_telegram(BOT1_TOKEN, message, target_chat_id)

def send_success_alert(message, target_chat_id):
    """Routes successful meal booking confirmations through Bot 2."""
    send_telegram(BOT2_TOKEN, message, target_chat_id)

def fetch_tokens():
    if not GIST_ID:
        print("❌ Missing GIST_ID environment variable.")
        return {}

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

def reserve_for_account(page, account_name, user_chat_id):
    print(f"\n📌 Processing: {account_name}")
    
    # Wait for DOM content to load rather than full page assets, with extended timeout
    page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(3000)

    if "resto.php" in page.url and "restaurant.php" not in page.url:
        err_msg = f"🚨 *INSAT Reservation Alert*\nSession EXPIRED for *{account_name}*! Run `tokens.py` locally to refresh."
        print(f"❌ {err_msg}")
        
        # Sent via Bot 1 (System Alerts)
        send_system_alert(err_msg, ADMIN_CHAT_ID)
        if user_chat_id and user_chat_id != ADMIN_CHAT_ID:
            send_system_alert(err_msg, user_chat_id)
        return False

    checkboxes = page.query_selector_all("input[type='checkbox']")
    if not checkboxes:
        print(f"⚠️ No meal checkboxes found for {account_name}.")
        return True

    selected_count = 0
    for cb in checkboxes:
        if not cb.is_checked():
            cb.check()
            selected_count += 1

    submit_btn = page.query_selector("button[type='submit'], input[type='submit'], button:has-text('Enregistrer'), button:has-text('Valider')")
    if submit_btn and selected_count > 0:
        submit_btn.click()
        page.wait_for_timeout(2000)
        
        success_msg = f"✅ *Meals Booked!*\nReserved *{selected_count}* new meal(s) for *{account_name}*!"
        print(f"🎉 {success_msg}")
        
        # Sent via Bot 2 (Reservation Successes)
        recipient = user_chat_id if user_chat_id else ADMIN_CHAT_ID
        send_success_alert(success_msg, recipient)
    else:
        print(f"ℹ️ All available meals were already booked for {account_name}.")
    
    return True

def run_reserve_all():
    tokens = fetch_tokens()
    if not tokens:
        send_system_alert("❌ Missing session tokens in Gist! Please run `tokens.py`.", ADMIN_CHAT_ID)
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        account_list = list(tokens.items())
        for idx, (name, data) in enumerate(account_list):
            if isinstance(data, dict):
                phpsessid = data.get("phpsessid")
                user_chat_id = data.get("chat_id")
            else:
                phpsessid = data
                user_chat_id = ""

            context = browser.new_context(user_agent=USER_AGENT)
            context.add_cookies([{
                "name": "PHPSESSID",
                "value": phpsessid,
                "url": "https://quickcardcampus.digi-sys.net"
            }])

            page = context.new_page()
            try:
                reserve_for_account(page, name, user_chat_id)
            except Exception as e:
                err_msg = f"⚠️ Script error processing *{name}*: {e}"
                print(f"❌ {err_msg}")
                # Sent via Bot 1 (System Alerts)
                send_system_alert(err_msg, ADMIN_CHAT_ID)
            finally:
                context.close()

            # Throttle requests by sleeping 3 seconds between accounts
            if idx < len(account_list) - 1:
                time.sleep(3)

        browser.close()

if __name__ == "__main__":
    run_reserve_all()
