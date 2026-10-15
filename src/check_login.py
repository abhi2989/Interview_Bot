"""Is the saved browser profile REALLY signed in to Google? Run inside Docker:
docker run --rm --shm-size=1g -v "${PWD}/src:/app/src" -v "${PWD}/data:/app/data" -v "${PWD}/output:/app/output" --entrypoint xvfb-run interview-bot -a python -m src.check_login"""
import asyncio, glob, os
from playwright.async_api import async_playwright
from . import config as C
async def main():
    for f in glob.glob(os.path.join(C.PROFILE_DIR, "Singleton*")):       # stale lock from the previous container
        try: os.remove(f)
        except OSError: pass
    os.makedirs("output", exist_ok=True)
    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(C.PROFILE_DIR, headless=False, args=[
            "--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"])
        p = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await p.goto("https://myaccount.google.com/", wait_until="domcontentloaded")
        await p.wait_for_timeout(5000)
        url, text = p.url, (await p.inner_text("body")).replace("\n", " | ")
        await p.screenshot(path="output/login_check.png")
        await ctx.close()
    if "accounts.google.com" in url or "signin" in url.lower():
        print("NOT SIGNED IN. Google sent the browser to the sign-in page. Run the --login step again and finish signing in.")
    else:
        print("SIGNED IN. The account page shows:", text[:220])

asyncio.run(main())