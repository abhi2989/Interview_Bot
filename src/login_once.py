"""Run LOCALLY (not in Docker) once: log in to the bot's Google account, press Enter, state is saved.
Use a dedicated account named e.g. 'Aria - AI Interviewer' with a profile photo => that's the avatar."""
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(headless=False, channel="chrome", args=["--disable-blink-features=AutomationControlled"])
    c = b.new_context(); pg = c.new_page(); pg.goto("https://accounts.google.com")
    input("Log in in the browser window, then press Enter here... ")
    c.storage_state(path="data/auth.json"); b.close(); print("saved data/auth.json")
