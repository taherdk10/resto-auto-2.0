import os
import json
import urllib.request
from playwright.sync_api import sync_playwright

TARGET_URL = "https://quickcardcampus.digi-sys.net/dashboard/admin/restaurant.php?page=reservation"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

GIST_ID = os.environ.get("GIST_ID")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send_telegram(message, target_chat_id):
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
    page.goto(TARGET_URL)
    page.wait_for_timeout(3000)

    if "resto.php" in page.url and "restaurant.php" not in page.url:
        err_msg = f"🚨 *INSAT Reservation Alert*\nSession EXPIRED for *{account_name}*! Run `tokens.py` locally to refresh."
        print(f"❌ {err_msg}")
        
        send_telegram(err_msg, ADMIN_CHAT_ID)
        if user_chat_id and user_chat_id != ADMIN_CHAT_ID:
            send_telegram(err_msg, user_chat_id)
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
        send_telegram(success_msg, user_chat_id)
    else:
        print(f"ℹ️ All available meals were already booked for {account_name}.")
    
    return True

def run_reserve_all():
    tokens = fetch_tokens()
    if not tokens:
        send_telegram("❌ Missing session tokens in Gist! Please run `tokens.py`.", ADMIN_CHAT_ID)
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for name, data in tokens.items():
            if isinstance(data, dict):
                phpsessid = data.get("phpsessid")
                user_chat_id = data.get("chat_id")
            else:
                phpsessid = data
                user_chat_id = ""

            # Force exact Windows User-Agent in Linux GitHub runner
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
                send_telegram(err_msg, ADMIN_CHAT_ID)
            finally:
                context.close()

        browser.close()

if __name__ == "__main__":
    run_reserve_all()
