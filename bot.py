# -*- coding: utf-8 -*-
import asyncio
import os
import random
import requests
from datetime import datetime
from instagrapi import Client
from instagrapi.exceptions import LoginRequired, PleaseWaitFewMinutes, ClientError

# ================== TELEGRAM ==================
TG_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT = os.getenv("TG_CHAT_ID")

def tg(msg: str):
    if not TG_TOKEN or not TG_CHAT:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT, "text": msg},
            timeout=5
        )
    except:
        pass

# ================== LOAD CONFIG ==================
MESSAGES = os.getenv("MESSAGES", "").split("|")
ACCOUNT_NAMES = os.getenv("ACCOUNTS", "").split(",")

ACCOUNTS = []
for name in ACCOUNT_NAMES:
    name = name.strip().upper()
    if not name:
        continue
    session = os.getenv(f"{name}_SESSION")
    gcs = [gc.strip() for gc in os.getenv(f"{name}_GCS", "").split(",") if gc.strip()]
    if session and gcs:
        ACCOUNTS.append({
            "name": name,
            "session": session,
            "gcs": gcs  # List of direct thread URLs
        })

if not ACCOUNTS or not MESSAGES:
    raise RuntimeError("Missing ENV config: ACCOUNTS, MESSAGES, and per-account _SESSION and _GCS required")

num_accounts = len(ACCOUNTS)

# Calculate shorter delay per message so each account gets ~40-45s effective delay
base_delay_min = 40 / num_accounts
base_delay_max = 45 / num_accounts
# Minimum reasonable delay to avoid instant bans (adjust if needed)
short_delay_min = max(8, base_delay_min - 2)  # e.g., for 4 acc: ~9-13s
short_delay_max = base_delay_max + 2

# ================== MAIN LOOP ==================
async def main():
    tg("🤖 Bot started (sequential mode)")
    print("🤖 Bot started (sequential mode)")

    cl = Client()
    cl.delay_range = [1, 5]  # Small built-in delays for safety

    current_acc_index = 0

    while True:
        acc = ACCOUNTS[current_acc_index]

        try:
            # Switch session: set new sessionid (this "logs out" old and "logs in" new)
            cl.login_by_sessionid(acc["session"])
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log = f"✅ {now} | Switched to {acc['name']}"
            print(log)
            tg(log)

            # Send to all group chats for this account
            for gc_url in acc["gcs"]:
                try:
                    thread_id = gc_url.split("/direct/t/")[-1].split("/")[0].strip()

                    msg = random.choice(MESSAGES)

                    cl.direct_send(text=msg, thread_ids=[thread_id])

                    sent = 1
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    log = f"✅ {now} | {acc['name']} | SENT | Thread: {thread_id}"
                    print(log)
                    tg(log)

                    # Short delay after each individual message
                    await asyncio.sleep(random.uniform(short_delay_min, short_delay_max))

                except PleaseWaitFewMinutes:
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    err = f"⚠️ {now} | {acc['name']} | RATE LIMIT | Waiting 10-15 min"
                    print(err)
                    tg(err)
                    await asyncio.sleep(random.uniform(600, 900))
                except LoginRequired:
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    err = f"❌ {now} | {acc['name']} | SESSION EXPIRED"
                    print(err)
                    tg(err)
                    # Skip to next account or stop if critical
                    break
                except ClientError as e:
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    err = f"⚠️ {now} | {acc['name']} | CLIENT ERROR | {e}"
                    print(err)
                    tg(err)
                    await asyncio.sleep(60)
                except Exception as e:
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    err = f"❌ {now} | {acc['name']} | FAIL | {e}"
                    print(err)
                    tg(err)
                    await asyncio.sleep(random.uniform(30, 60))

            # After finishing all GCs for this account, move to next
            current_acc_index = (current_acc_index + 1) % num_accounts

            # Optional extra small delay between full account cycles
            # await asyncio.sleep(random.uniform(5, 10))

        except Exception as e:
            # Fallback error for session switch
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            err = f"❌ {now} | Switch failed for {acc['name']} | {e}"
            print(err)
            tg(err)
            current_acc_index = (current_acc_index + 1) % num_accounts
            await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(main())
