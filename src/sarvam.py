# """Sarvam TTS + STT (REST)."""
# import base64, io, re, wave, httpx
# from concurrent.futures import ThreadPoolExecutor
# from . import config as C
# BASE = "https://api.sarvam.ai"
# HDR = {"api-subscription-key": C.SARVAM_API_KEY or ""}
# RATE = 16000
# def _split(text, n=450):  # TTS has a per-request char limit
#     parts, cur = [], ""
#     for s in re.split(r"(?<=[.!?])\s+", text.strip()):
#         if len(cur) + len(s) + 1 <= n: cur = f"{cur} {s}".strip()
#         else:
#             if cur: parts.append(cur)
#             cur = s[:n]
#     return parts + ([cur] if cur else [])

# def _tts_one(t):
#     r = httpx.post(f"{BASE}/text-to-speech", headers=HDR, timeout=30, json={
#         "text": t, "target_language_code": C.LANG,
#         "speaker": C.SARVAM_TTS_SPEAKER, "model": C.SARVAM_TTS_MODEL})
#     r.raise_for_status()
#     return base64.b64decode(r.json()["audios"][0])

# def tts(text: str) -> bytes:
#     """Text -> one WAV (chunks fetched in parallel, joined in order)."""
#     with ThreadPoolExecutor(4) as ex:
#         wavs = list(ex.map(_tts_one, _split(text)))
#     out, w = io.BytesIO(), None
#     for b in wavs:
#         with wave.open(io.BytesIO(b)) as r:
#             if w is None: w = wave.open(out, "wb"); w.setparams(r.getparams())
#             w.writeframes(r.readframes(r.getnframes()))
#     w.close()
#     return out.getvalue()

# def _wav(pcm: bytes) -> bytes:
#     b = io.BytesIO()
#     with wave.open(b, "wb") as w:
#         w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE); w.writeframes(pcm)
#     return b.getvalue()

# def stt(pcm: bytes) -> str:
#     """16kHz mono PCM -> text. REST API caps clip length (~30s), so split into 25s pieces."""
#     step, texts = RATE * 2 * 25, []
#     for i in range(0, len(pcm), step):
#         chunk = pcm[i:i + step]
#         if len(chunk) < RATE * 2 * 0.3: continue
#         r = httpx.post(f"{BASE}/speech-to-text", headers=HDR, timeout=60,
#                        files={"file": ("turn.wav", _wav(chunk), "audio/wav")},
#                        data={"model": C.SARVAM_STT_MODEL, "language_code": C.LANG})
#         r.raise_for_status()
#         texts.append(r.json().get("transcript", "").strip())
#     return " ".join(t for t in texts if t)






"""Sarvam TTS + STT (REST). STT auto-detects English/Hindi/Hinglish; TTS picks the voice language per sentence."""
import base64, io, re, wave, httpx
from concurrent.futures import ThreadPoolExecutor
from . import config as C
from .lang import DEV

BASE = "https://api.sarvam.ai"
HDR = {"api-subscription-key": C.SARVAM_API_KEY or ""}
RATE = 16000

def _check(r):
    if r.is_error: raise RuntimeError(f"Sarvam {r.status_code}: {r.text}")

def _split(text, n=450):  # TTS has a per-request char limit
    parts, cur = [], ""
    for s in re.split(r"(?<=[.!?।])\s+", text.strip()):
        if len(cur) + len(s) + 1 <= n: cur = f"{cur} {s}".strip()
        else:
            if cur: parts.append(cur)
            cur = s[:n]
    return parts + ([cur] if cur else [])

def _tts_one(t):
    lang = "hi-IN" if DEV.search(t) else C.LANG        # Devanagari (Hindi / Hinglish) -> Hindi voice model
    r = httpx.post(f"{BASE}/text-to-speech", headers=HDR, timeout=30, json={
        "text": t, "target_language_code": lang,
        "speaker": C.SARVAM_TTS_SPEAKER, "model": C.SARVAM_TTS_MODEL})
    _check(r)
    return base64.b64decode(r.json()["audios"][0])

def tts(text: str) -> bytes:
    """Text -> one WAV (chunks fetched in parallel, joined in order)."""
    with ThreadPoolExecutor(4) as ex:
        wavs = list(ex.map(_tts_one, _split(text)))
    out, w = io.BytesIO(), None
    for b in wavs:
        with wave.open(io.BytesIO(b)) as r:
            if w is None: w = wave.open(out, "wb"); w.setparams(r.getparams())
            w.writeframes(r.readframes(r.getnframes()))
    w.close()
    return out.getvalue()

def _wav(pcm: bytes) -> bytes:
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE); w.writeframes(pcm)
    return b.getvalue()

def stt(pcm: bytes):
    """16kHz mono PCM -> (text, detected_language_code). Real-time REST caps clips at ~30s, so 25s pieces."""
    step, texts, langs = RATE * 2 * 25, [], []
    for i in range(0, len(pcm), step):
        chunk = pcm[i:i + step]
        if len(chunk) < RATE * 2 * 0.3: continue
        data = {"model": C.SARVAM_STT_MODEL, "language_code": C.STT_LANGUAGE}
        if C.SARVAM_STT_MODEL.startswith("saaras") and C.STT_MODE: data["mode"] = C.STT_MODE
        r = httpx.post(f"{BASE}/speech-to-text", headers=HDR, timeout=60,
                       files={"file": ("turn.wav", _wav(chunk), "audio/wav")}, data=data)
        _check(r)
        j = r.json()
        texts.append((j.get("transcript") or "").strip())
        if j.get("language_code"): langs.append(j["language_code"])
    return " ".join(t for t in texts if t), (langs[0] if langs else None)