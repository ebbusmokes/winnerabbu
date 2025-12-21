import time
import random
import os
import requests
from datetime import datetime
from instagrapi import Client
from flask import Flask
from threading import Thread

# ================= KEEP ALIVE (Render + UptimeRobot) =================
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is alive"

def run_web():
    app.run(host="0.0.0.0", port=10000)

Thread(target=run_web, daemon=True).start()

# ================= TELEGRAM =================
TG_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

BOT_RUNNING = True
LAST_UPDATE_ID = 0

def tg_log(msg):
    if not TG_TOKEN or not TG_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT_ID, "text": msg},
            timeout=5
        )
    except:
        pass

def telegram_listener():
    global BOT_RUNNING, LAST_UPDATE_ID
    tg_log(" Bot online. Commands: /startbot /stopbot /status")

    while True:
        try:
            r = requests.get(
                f"https://api.telegram.org/bot{TG_TOKEN}/getUpdates",
                timeout=10
            ).json()

            for u in r.get("result", []):
                uid = u["update_id"]
                if uid <= LAST_UPDATE_ID:
                    continue
                LAST_UPDATE_ID = uid

                msg = u.get("message", {})
                chat_id = msg.get("chat", {}).get("id")
                text = msg.get("text", "")

                #  LOCK TO OWNER ONLY
                if str(chat_id) != str(TG_CHAT_ID):
                    continue

                if text == "/startbot":
                    BOT_RUNNING = True
                    tg_log(" Bot STARTED")

                elif text == "/stopbot":
                    BOT_RUNNING = False
                    tg_log(" Bot STOPPED")

                elif text == "/status":
                    tg_log(" Status: RUNNING " if BOT_RUNNING else " Status: STOPPED ")
        except:
            pass

        time.sleep(3)

Thread(target=telegram_listener, daemon=True).start()

# ================= SETTINGS =================
MIN_INTERVAL = 40
MAX_INTERVAL = 45
INTERNAL_GC_DELAY = 3  # seconds between GCs

# ================= LOAD ACCOUNTS FROM ENV =================
account_names = os.getenv("ACCOUNTS", "").split(",")

ACCOUNTS = []
for name in account_names:
    name = name.strip()
    if not name:
        continue
    ACCOUNTS.append({
        "name": name,
        "sessionid": os.getenv(f"{name.upper()}_SESSION"),
        "threads": os.getenv(f"{name.upper()}_THREADS", "").split(","),
        "message": os.getenv(f"{name.upper()}_MESSAGE", "")
    })

if not ACCOUNTS:
    raise RuntimeError("No accounts configured")

# ================= LOGIN / REFRESH =================
def login_account(acc):
    cl = Client()
    cl.set_settings({"sessionid": acc["sessionid"]})
    cl.login_by_sessionid(acc["sessionid"])
    tg_log(f" Logged in {acc['name']}")
    return cl

def safe_send(cl, acc, tid):
    try:
        cl.direct_send(acc["message"], thread_ids=[tid])
        return cl
    except Exception as e:
        tg_log(f" {acc['name']} failed  refreshing | {e}")
        try:
            cl.logout()
        except:
            pass
        try:
            new_cl = login_account(acc)
            new_cl.direct_send(acc["message"], thread_ids=[tid])
            tg_log(f" {acc['name']} refreshed & sent")
            return new_cl
        except Exception as e:
            tg_log(f" {acc['name']} refresh failed | {e}")
            return None

# ================= INITIAL LOGIN =================
clients = [login_account(acc) for acc in ACCOUNTS]
tg_log(" Bot started")

# ================= MAIN LOOP =================
while True:
    if not BOT_RUNNING:
        time.sleep(5)
        continue

    interval = random.randint(MIN_INTERVAL, MAX_INTERVAL)
    gap = interval / len(ACCOUNTS)

    for i, acc in enumerate(ACCOUNTS):
        cl = clients[i]
        now = datetime.now().strftime("%H:%M:%S")

        for tid in acc["threads"]:
            tid = tid.strip()
            if not tid:
                continue

            result = safe_send(cl, acc, tid)
            if result:
                clients[i] = result
                msg = f"[{now}]  {acc['name']}  {tid}"
                print(msg)
                tg_log(msg)
            else:
                tg_log(f"[{now}]  {acc['name']} skipped")

            time.sleep(INTERNAL_GC_DELAY)

        time.sleep(gap)