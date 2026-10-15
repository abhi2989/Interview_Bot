"""PulseAudio audio: always-on ear (parec + VAD + speculative early STT) and a streaming speaker with barge-in."""
import asyncio, collections, os, queue, subprocess, tempfile, threading, time, webrtcvad
from concurrent.futures import ThreadPoolExecutor
from . import config as C, sarvam

RATE, FRAME_MS = 16000, 30
FB = RATE * FRAME_MS // 1000 * 2
ONSET, BARGE, PRE = 5, 10, 15      # speech frames to start a turn / to interrupt the bot / pre-roll kept
_pool = ThreadPoolExecutor(4)

class Ear:
    """Runs parec in the background for the whole call; frames are tagged speech / non-speech."""
    def __init__(self):
        self.q = queue.Queue(maxsize=4000); self.vad = webrtcvad.Vad(2)
        self.p = subprocess.Popen(["parec", "-d", "meeting_out.monitor", "--format=s16le",
                                   f"--rate={RATE}", "--channels=1", "--latency-msec=30"],
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self):
        while True:
            f = self.p.stdout.read(FB)
            if len(f) < FB: break
            item = (f, self.vad.is_speech(f, RATE))
            try: self.q.put_nowait(item)
            except queue.Full:
                try: self.q.get_nowait()
                except queue.Empty: pass
                self.q.put_nowait(item)

    def flush(self):
        while True:
            try: self.q.get_nowait()
            except queue.Empty: break

    def _scan(self, onset, deadline=None, stop=None):
        pre, consec = collections.deque(maxlen=PRE), 0
        while True:
            if stop is not None and stop.is_set(): return None
            if deadline is not None and time.monotonic() > deadline: return None
            try: f, sp = self.q.get(timeout=0.1)
            except queue.Empty: continue
            pre.append(f); consec = consec + 1 if sp else 0
            if consec >= onset: return list(pre)

    def wait_onset(self, timeout=45): return self._scan(ONSET, deadline=time.monotonic() + timeout)
    def watch(self, stop):            return self._scan(BARGE, stop=stop)

    @staticmethod
    def _trim(buf, silence, keep=6):                 # drop trailing silence (less audio to upload and transcribe)
        cut = max(0, silence - keep) * FB
        return bytes(buf[:len(buf) - cut]) if cut else bytes(buf)

    def collect(self, pre, max_seconds=180):
        """Returns (pcm, stt_future). Transcription starts EARLY_STT_MS into the pause, hidden behind the rest of
        the end-of-turn wait; if the candidate keeps talking, that speculative transcript is discarded."""
        buf, voiced, silence, fut = bytearray(b"".join(pre)), ONSET, 0, None
        while len(buf) < max_seconds * RATE * 2:
            try: f, sp = self.q.get(timeout=1)
            except queue.Empty: continue
            buf.extend(f)
            if sp:
                voiced += 1; silence = 0; fut = None
            else:
                silence += 1
                if (fut is None and 0 < C.EARLY_STT_MS < C.SILENCE_MS and silence * FRAME_MS >= C.EARLY_STT_MS
                        and voiced * FRAME_MS >= 1000):
                    fut = _pool.submit(sarvam.stt, self._trim(buf, silence))
                if silence * FRAME_MS >= C.SILENCE_MS: break
        if voiced * FRAME_MS < C.MIN_SPEECH_MS: return None, None
        return self._trim(buf, silence), fut

class Speaker:
    """Takes an async stream of sentences: synthesizes ahead while playing; stops instantly on barge-in."""
    proc = None
    play_starts = []

    async def _play(self, wav):
        fd, path = tempfile.mkstemp(suffix=".wav"); os.write(fd, wav); os.close(fd)
        try:
            self.proc = await asyncio.create_subprocess_exec("paplay", "--device=bot_mic", path)
            await self.proc.wait()
        except asyncio.CancelledError:
            self._kill(); raise
        finally:
            os.remove(path)

    def _kill(self):
        if self.proc and self.proc.returncode is None: self.proc.kill()

    async def say(self, sentences, ear, can_barge=None):
        """Returns (spoken_text, pre_frames); pre_frames is not None if the candidate interrupted.
        If can_barge (an asyncio.Event) is given, interruption is only listened for after it is set."""
        q, spoken, stop = asyncio.Queue(), [], threading.Event()
        self.play_starts = []

        async def produce():
            async for s in sentences:
                await q.put((s, asyncio.create_task(asyncio.to_thread(sarvam.tts, s))))
            await q.put(None)

        async def play():
            while (item := await q.get()) is not None:
                s, task = item
                wav = await task
                spoken.append(s); self.play_starts.append(time.monotonic())
                await self._play(wav)

        async def watcher():
            if can_barge is not None: await can_barge.wait()
            return await asyncio.to_thread(ear.watch, stop)

        prod, pl, watch = asyncio.create_task(produce()), asyncio.create_task(play()), asyncio.create_task(watcher())
        waiters = {pl, watch, prod}
        while True:
            await asyncio.wait(waiters, return_when=asyncio.FIRST_COMPLETED)
            if watch.done() or pl.done(): break
            if prod.done():
                if prod.exception(): break           # LLM/TTS failed mid-turn: don't hang
                waiters.discard(prod)
        hit = watch.done() and not watch.cancelled() and watch.exception() is None and watch.result() is not None
        if hit:                                                   # candidate interrupted
            self._kill(); pl.cancel(); prod.cancel()
            await asyncio.gather(pl, prod, return_exceptions=True)
            return " ".join(spoken), watch.result()
        stop.set(); watch.cancel(); await asyncio.gather(watch, return_exceptions=True)
        if prod.done() and prod.exception():
            self._kill(); pl.cancel(); await asyncio.gather(pl, return_exceptions=True)
            raise prod.exception()
        await asyncio.gather(prod, pl)
        return " ".join(spoken), None