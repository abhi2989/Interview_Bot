"""Join Google Meet with Playwright (real Chromium + PulseAudio virtual devices)."""
import asyncio, os, re, time
from playwright.async_api import async_playwright
from . import config as C

JOIN_RE = re.compile(r"(Join now|Ask to join|Join anyway)", re.I)
LEAVE_RE = re.compile("Leave call", re.I)
FATAL_RE = re.compile(r"(can.t join this video call|check your meeting code|invalid video call name|meeting has ended|"
                      r"denied your request|request to join was denied|you were removed|not allowed to join)", re.I)

class MeetBot:
    async def _text(self):
        try: return (await self.page.inner_text("body", timeout=3000)).replace("\n", " | ")
        except Exception: return ""

    async def _shot(self, name):
        os.makedirs("output", exist_ok=True)
        try: await self.page.screenshot(path=f"output/{name}")
        except Exception: pass

    async def join(self, url: str, timeout_s=600):
        self.pw = await async_playwright().start()
        args = ["--use-fake-ui-for-media-stream", "--autoplay-policy=no-user-gesture-required",
                "--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"]
        opts = dict(viewport={"width": 1280, "height": 720}, permissions=["microphone", "camera"])
        signed_in = os.path.isdir(C.PROFILE_DIR) and any(os.scandir(C.PROFILE_DIR))
        self.profile = signed_in
        print("Using signed-in Google profile folder:", signed_in)
        if signed_in:       # profile created INSIDE this container by --login, so Google accepts it
            self.browser = ctx = await self.pw.chromium.launch_persistent_context(C.PROFILE_DIR, headless=False, args=args, **opts)
        else:               # anonymous guest: Meet will refuse API-created meetings
            self.browser = await self.pw.chromium.launch(headless=False, args=args)
            ctx = await self.browser.new_context(**opts)
        self.page = p = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await p.goto(url, wait_until="domcontentloaded")
        print("Opened the meeting page...")
        await p.wait_for_timeout(4000)
        await self._enter(timeout_s)

    async def _enter(self, timeout_s=600, poll_s=3, find_s=90):
        """Fill the name, press Join / Ask to join, then wait (and REPORT what we see) until we are in the call."""
        p = self.page
        name = p.get_by_placeholder(re.compile("Your name", re.I))
        if await name.count():
            if getattr(self, "profile", False):
                print("WARNING: a profile folder exists but Meet still asks for a guest name, so the Google sign-in did NOT stick. "
                      "Run the --login step again and confirm with src.check_login.")
            await name.fill(C.BOT_NAME)
        cam = p.get_by_role("button", name=re.compile("Turn off camera", re.I))
        if await cam.count(): await cam.first.click()
        clicked, deadline = None, time.monotonic() + find_s
        while time.monotonic() < deadline:
            btn = p.get_by_role("button", name=JOIN_RE)
            if await btn.count():
                clicked = (await btn.first.inner_text()).strip().replace("\n", " ")
                await btn.first.click(timeout=15000); break
            text = await self._text()
            if FATAL_RE.search(text):
                await self._shot("join_fail.png"); raise RuntimeError("Meet refused the bot. Page says: " + text[:300])
            await asyncio.sleep(2)
        if not clicked:
            await self._shot("join_fail.png")
            raise RuntimeError("No Join button found. Page says: " + (await self._text())[:300])
        print(f"Clicked '{clicked}'.")
        if "ask" in clicked.lower():
            print("The bot is WAITING TO BE ADMITTED. Open the meeting link in your own browser (signed in as the account "
                  "that created it) and click Admit.")
        t0, last, next_print = time.monotonic(), "", 0
        while time.monotonic() - t0 < timeout_s:
            if await p.get_by_role("button", name=LEAVE_RE).count():
                print("Bot is in the call."); return
            text = await self._text()
            if FATAL_RE.search(text):
                await self._shot("join_fail.png"); raise RuntimeError("Meet refused the bot. Page says: " + text[:300])
            if time.monotonic() >= next_print and text[:200] != last:
                print(f"[waiting {int(time.monotonic() - t0)}s] screen says: {text[:200]}")
                await self._shot("join_status.png"); last, next_print = text[:200], time.monotonic() + 15
            await asyncio.sleep(poll_s)
        await self._shot("join_fail.png")
        raise TimeoutError(f"Not in the call after {timeout_s}s. Last screen: {last}")

    async def auto_admit(self):
        """If the bot is the host, let in anyone who knocks (e.g. a candidate without a Google account)."""
        while True:
            try:
                for btn in await self.page.get_by_role("button", name=re.compile(r"^(Admit|Admit all)$", re.I)).all():
                    await btn.click(timeout=2000); print("Admitted someone who was waiting.")
            except Exception:
                pass
            await asyncio.sleep(3)

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