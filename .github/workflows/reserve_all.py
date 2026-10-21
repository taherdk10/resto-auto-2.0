import os
import json
import urllib.request
from playwright.sync_api import sync_playwright

TARGET_URL = "https://quickcardcampus.digi-sys.net/dashboard/admin/restaurant.php?page=reservation"

# Read directly from environment secrets
GIST_ID = os.environ.get("GIST_ID")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send_alert(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram credentials not configured in environment. Skipping alert.")
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
    """Fetches tokens from Gist if GIST_ID is provided, otherwise reads local sessions.json."""
    if GIST_ID:
        gist_url = f"https://gist.githubusercontent.com/raw/{GIST_ID}/sessions.json"
        try:
            req = urllib.request.Request(gist_url, headers={"Cache-Control": "no-cache"})
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"⚠️ Error fetching tokens from Gist: {e}")

    try:
        with open("sessions.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print("❌ No tokens found locally or in Gist.")
        return {}

def reserve_for_account(page, account_name):
    print(f"\n📌 Processing: {account_name}")
    page.goto(TARGET_URL)
    page.wait_for_timeout(3000)

    # Check for session expiration redirect
    if "resto.php" in page.url and "restaurant.php" not in page.url:
        msg = f"🚨 *INSAT Reservation Alert*\nSession expired for *{account_name}*! Run `tokens.py` locally to refresh."
        print(f"❌ {msg}")
        send_alert(msg)
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
        msg = f"✅ *Meals Booked!*\nReserved *{selected_count}* new meal(s) for *{account_name}*!"
        print(f"🎉 {msg}")
        send_alert(msg)
    else:
        print(f"ℹ️ All available meals were already booked for {account_name}.")
    
    return True

def run_reserve_all():
    tokens = fetch_tokens()
    if not tokens:
        send_alert("❌ Missing session tokens! Run `tokens.py` locally.")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for name, phpsessid in tokens.items():
            context = browser.new_context()
            context.add_cookies([{
                "name": "PHPSESSID",
                "value": phpsessid,
                "url": "https://quickcardcampus.digi-sys.net"
            }])

            page = context.new_page()
            try:
                reserve_for_account(page, name)
            except Exception as e:
                print(f"❌ Error processing {name}: {e}")
            finally:
                context.close()

        browser.close()

if __name__ == "__main__":
    run_reserve_all()
