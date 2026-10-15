"""Sarvam TTS + STT (REST). Persistent connection, cached fixed phrases, parallel chunks."""
import base64, io, re, wave, httpx
from concurrent.futures import ThreadPoolExecutor
from . import config as C
from .lang import DEV

BASE = "https://api.sarvam.ai"
HDR = {"api-subscription-key": C.SARVAM_API_KEY or ""}
RATE = 16000
_http = httpx.Client(timeout=60)      # keep-alive: no new TLS handshake on every request
_cache = {}                           # text -> wav, for fixed phrases (fillers, retry, closing)

def _check(r):
    if r.is_error: raise RuntimeError(f"Sarvam {r.status_code}: {r.text}")

def warm():
    try: _http.get(BASE, timeout=5)
    except Exception: pass

def _split(text, n=450):
    parts, cur = [], ""
    for s in re.split(r"(?<=[.!?।])\s+", text.strip()):
        if len(cur) + len(s) + 1 <= n: cur = f"{cur} {s}".strip()
        else:
            if cur: parts.append(cur)
            cur = s[:n]
    return parts + ([cur] if cur else [])

def _tts_one(t):
    lang = "hi-IN" if DEV.search(t) else C.LANG
    r = _http.post(f"{BASE}/text-to-speech", headers=HDR, timeout=30, json={
        "text": t, "target_language_code": lang, "speaker": C.SARVAM_TTS_SPEAKER, "model": C.SARVAM_TTS_MODEL})
    _check(r)
    return base64.b64decode(r.json()["audios"][0])

def _tts_uncached(text):
    parts = _split(text)
    wavs = [_tts_one(parts[0])] if len(parts) == 1 else list(ThreadPoolExecutor(4).map(_tts_one, parts))
    out, w = io.BytesIO(), None
    for b in wavs:
        with wave.open(io.BytesIO(b)) as r:
            if w is None: w = wave.open(out, "wb"); w.setparams(r.getparams())
            w.writeframes(r.readframes(r.getnframes()))
    w.close()
    return out.getvalue()

def tts(text: str) -> bytes:
    return _cache[text] if text in _cache else _tts_uncached(text)

def prime(texts):
    """Pre-synthesize fixed phrases so they play instantly later."""
    def one(t):
        try: _cache[t] = _tts_uncached(t)
        except Exception as e: print("prime failed:", t[:20], e)
    with ThreadPoolExecutor(4) as ex: list(ex.map(one, [t for t in dict.fromkeys(texts) if t not in _cache]))

def _wav(pcm: bytes) -> bytes:
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE); w.writeframes(pcm)
    return b.getvalue()

def _stt_one(chunk):
    data = {"model": C.SARVAM_STT_MODEL, "language_code": C.STT_LANGUAGE}
    if C.SARVAM_STT_MODEL.startswith("saaras") and C.STT_MODE: data["mode"] = C.STT_MODE
    r = _http.post(f"{BASE}/speech-to-text", headers=HDR, timeout=60,
                   files={"file": ("turn.wav", _wav(chunk), "audio/wav")}, data=data)
    _check(r)
    j = r.json()
    return (j.get("transcript") or "").strip(), j.get("language_code")

def stt(pcm: bytes):
    """16kHz mono PCM -> (text, detected_language_code). Pieces of 25s (REST limit) are sent in parallel."""
    step = RATE * 2 * 25
    chunks = [c for c in (pcm[i:i + step] for i in range(0, len(pcm), step)) if len(c) >= RATE * 2 * 0.3]
    res = [_stt_one(chunks[0])] if len(chunks) == 1 else list(ThreadPoolExecutor(4).map(_stt_one, chunks))
    texts, langs = [t for t, _ in res if t], [l for _, l in res if l]
    return " ".join(texts), (langs[0] if langs else None)