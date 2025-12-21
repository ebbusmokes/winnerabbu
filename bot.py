# -*- coding: utf-8 -*-
import asyncio, os, random, requests
from datetime import datetime
from urllib.parse import unquote
from playwright.async_api import async_playwright

# ================== TELEGRAM ==================
TG_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

BOT_RUNNING = True

def tg(msg):
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

async def telegram_listener():
    global BOT_RUNNING
    offset = 0
    tg("🤖 Bot ONLINE\nCommands: /start /stop /status")

    while True:
        try:
            r = requests.get(
                f"https://api.telegram.org/bot{TG_TOKEN}/getUpdates",
                params={"offset": offset},
                timeout=10
            ).json()

            for u in r.get("result", []):
                offset = u["update_id"] + 1
                msg = u.get("message", {})
                chat_id = msg.get("chat", {}).get("id")
                text = msg.get("text", "")

                if str(chat_id) != str(TG_CHAT_ID):
                    continue

                if text == "/start":
                    BOT_RUNNING = True
                    tg("▶️ BOT STARTED")

                elif text == "/stop":
                    BOT_RUNNING = False
                    tg("⏸ BOT STOPPED")

                elif text == "/status":
                    tg(
                        f"📊 STATUS\n"
                        f"Running: {BOT_RUNNING}\n"
                        f"✅ Success: {SUCCESS}\n"
                        f"❌ Fail: {FAIL}"
                    )
        except:
            pass

        await asyncio.sleep(3)

# ================== LOGGING ==================
SUCCESS = 0
FAIL = 0
LOCK = asyncio.Lock()

def log_event(ok, acc, tid, err=None):
    global SUCCESS, FAIL
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if ok:
        SUCCESS += 1
        msg = f"[{now}] ✅ {acc} sent to {tid}"
    else:
        FAIL += 1
        msg = f"[{now}] ❌ {acc} FAILED to {tid} ({err})"

    print(msg)
    tg(msg)

# ================== CONFIG ==================
MIN_DELAY = 40
MAX_DELAY = 45
MESSAGES_PER_GC = 1
RESTART_AFTER = 60

# ================== LOAD ACCOUNTS ==================
# ENV FORMAT:
# ACCOUNTS = acc1,acc2
# ACC1_SESSION=xxxx
# ACC1_THREADS=url1,url2
# ACC1_MESSAGE=hello

account_names = os.getenv("ACCOUNTS", "").split(",")

ACCOUNTS = []
for name in account_names:
    name = name.strip()
    if not name:
        continue
    ACCOUNTS.append({
        "name": name,
        "session": unquote(os.getenv(f"{name.upper()}_SESSION")),
        "threads": os.getenv(f"{name.upper()}_THREADS").split(","),
        "message": os.getenv(f"{name.upper()}_MESSAGE")
    })

if not ACCOUNTS:
    raise RuntimeError("No accounts configured")

# ================== WORKER ==================
async def worker(acc):
    sent = 0

    while True:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()

            await context.add_cookies([{
                "name": "sessionid",
                "value": acc["session"],
                "domain": ".instagram.com",
                "path": "/",
                "secure": True,
                "httpOnly": True
            }])

            page = await context.new_page()

            try:
                await page.goto(acc["threads"][0], timeout=60000)
                await page.locator(
                    'div[role="textbox"][contenteditable="true"]'
                ).wait_for(timeout=30000)

                cycle = 0
                while cycle < RESTART_AFTER:
                    if not BOT_RUNNING:
                        await asyncio.sleep(5)
                        continue

                    for tid in acc["threads"]:
                        if cycle >= RESTART_AFTER:
                            break

                        try:
                            await page.goto(tid, timeout=30000)
                            await page.locator(
                                'div[role="textbox"][contenteditable="true"]'
                            ).wait_for(timeout=30000)

                            await page.evaluate(
                                """(t)=>{
                                    const e=document.querySelector('div[role="textbox"][contenteditable="true"]');
                                    if(e){e.focus();document.execCommand('insertText',false,t);}
                                }""",
                                acc["message"]
                            )

                            await page.keyboard.press("Enter")
                            log_event(True, acc["name"], tid)

                        except Exception as e:
                            log_event(False, acc["name"], tid, str(e))

                        sent += 1
                        cycle += 1
                        await asyncio.sleep(random.uniform(0.3, 0.6))

            finally:
                await context.close()
                await browser.close()

            await asyncio.sleep(random.uniform(2, 4))

# ================== MAIN ==================
async def main():
    asyncio.create_task(telegram_listener())
    tasks = [asyncio.create_task(worker(acc)) for acc in ACCOUNTS]
    await asyncio.gather(*tasks)

asyncio.run(main())
