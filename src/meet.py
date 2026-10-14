# """Join Google Meet with Playwright (real Chromium, virtual audio devices)."""
# import asyncio, os, re
# from playwright.async_api import async_playwright
# from . import config as C

# JOIN_RE = re.compile(r"(Join now|Ask to join|Join anyway)", re.I)

# class MeetBot:
#     async def join(self, url: str, timeout_s=600):
#         self.pw = await async_playwright().start()
#         self.browser = await self.pw.chromium.launch(headless=False, args=[
#             "--use-fake-ui-for-media-stream", "--autoplay-policy=no-user-gesture-required",
#             "--disable-blink-features=AutomationControlled", "--no-sandbox"])
#         state = C.STORAGE_STATE if os.path.exists(C.STORAGE_STATE) else None
#         print("Using saved Google login:", bool(state))
#         ctx = await self.browser.new_context(storage_state=state, viewport={"width": 1280, "height": 720},
#                                              permissions=["microphone", "camera"])
#         self.page = p = await ctx.new_page()
#         await p.goto(url, wait_until="domcontentloaded")
#         await p.wait_for_timeout(4000)
#         name = p.get_by_placeholder(re.compile("Your name", re.I))
#         if await name.count():
#             await name.fill(C.BOT_NAME)
#         cam = p.get_by_role("button", name=re.compile("Turn off camera", re.I))
#         if await cam.count(): await cam.first.click()
#         try:
#             await p.get_by_role("button", name=JOIN_RE).first.click(timeout=60000)
#         except Exception:
#             os.makedirs("output", exist_ok=True)
#             await p.screenshot(path="output/join_fail.png")
#             print("URL:", p.url)
#             print("PAGE TEXT:", (await p.inner_text("body"))[:800].replace("\n", " | "))
#             raise
#         await p.get_by_role("button", name=re.compile("Leave call", re.I)).wait_for(timeout=timeout_s * 1000)

#     async def participant_count(self):
#         """Selector-based and fragile: returns None when unknown."""
#         try:
#             btn = self.page.get_by_role("button", name=re.compile(r"(Show everyone|People)", re.I)).first
#             m = re.search(r"\d+", (await btn.inner_text(timeout=1500)) + (await btn.get_attribute("aria-label") or ""))
#             return int(m.group()) if m else None
#         except Exception:
#             return None

#     async def wait_for_candidate(self, timeout_s=900):
#         for _ in range(timeout_s // 2):
#             n = await self.participant_count()
#             if n is None: await asyncio.sleep(10); return True
#             if n >= 2: await asyncio.sleep(3); return True
#             await asyncio.sleep(2)
#         return False

#     async def candidate_present(self):
#         n = await self.participant_count()
#         return n is None or n >= 2

#     async def leave(self):
#         try:
#             await self.page.get_by_role("button", name=re.compile("Leave call", re.I)).click(timeout=3000)
#         except Exception: pass
#         await self.browser.close(); await self.pw.stop()





"""Join Google Meet with Playwright (real Chromium + PulseAudio virtual devices)."""
import asyncio, os, re
from playwright.async_api import async_playwright
from . import config as C

JOIN_RE = re.compile(r"(Join now|Ask to join|Join anyway)", re.I)

class MeetBot:
    async def join(self, url: str, timeout_s=600):
        self.pw = await async_playwright().start()
        self.browser = await self.pw.chromium.launch(headless=False, args=[
            "--use-fake-ui-for-media-stream", "--autoplay-policy=no-user-gesture-required",
            "--disable-blink-features=AutomationControlled", "--no-sandbox"])
        state = C.STORAGE_STATE if os.path.exists(C.STORAGE_STATE) else None
        print("Using saved Google login:", bool(state))
        ctx = await self.browser.new_context(storage_state=state, viewport={"width": 1280, "height": 720},
                                             permissions=["microphone", "camera"])
        self.page = p = await ctx.new_page()
        await p.goto(url, wait_until="domcontentloaded")
        await p.wait_for_timeout(4000)
        name = p.get_by_placeholder(re.compile("Your name", re.I))
        if await name.count():
            await name.fill(C.BOT_NAME)
        cam = p.get_by_role("button", name=re.compile("Turn off camera", re.I))
        if await cam.count(): await cam.first.click()
        try:
            await p.get_by_role("button", name=JOIN_RE).first.click(timeout=60000)
        except Exception:
            os.makedirs("output", exist_ok=True)
            await p.screenshot(path="output/join_fail.png")
            print("URL:", p.url)
            print("PAGE TEXT:", (await p.inner_text("body"))[:800].replace("\n", " | "))
            raise
        print("Clicked join. If it says 'Ask to join', admit the bot in your meeting now...")
        await p.get_by_role("button", name=re.compile("Leave call", re.I)).wait_for(timeout=timeout_s * 1000)
        print("Bot is in the call.")

    async def participant_count(self):
        """Selector-based and fragile: returns None when unknown."""
        try:
            btn = self.page.get_by_role("button", name=re.compile(r"(Show everyone|People)", re.I)).first
            m = re.search(r"\d+", (await btn.inner_text(timeout=1500)) + (await btn.get_attribute("aria-label") or ""))
            return int(m.group()) if m else None
        except Exception:
            return None

    async def wait_for_candidate(self, timeout_s=900):
        for _ in range(timeout_s // 2):
            n = await self.participant_count()
            if n is None: await asyncio.sleep(10); return True
            if n >= 2: await asyncio.sleep(3); return True
            await asyncio.sleep(2)
        return False

    async def leave(self):
        try:
            await self.page.get_by_role("button", name=re.compile("Leave call", re.I)).click(timeout=3000)
        except Exception: pass
        await self.browser.close(); await self.pw.stop()