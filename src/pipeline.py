
"""One candidate turn, fully overlapped: instant filler -> (early) transcript -> LLM sentences, all in ONE stream."""
import asyncio, time
from . import sarvam, lang as L, config as C

async def reply_stream(agent, pcm, fut, res, committed, log):
    """Async generator of sentences to speak. `res` collects timings/flags; `committed` is set once the real answer starts
    (barge-in is only listened for from then on, so a thinking pause can't cancel half-processed work)."""
    t0 = time.monotonic()
    use_filler = len(pcm) / (16000 * 2) >= C.FILLER_MIN_SECONDS
    if use_filler:
        yield L.pick_filler(agent.lang)                       # cached audio: starts playing immediately
    text, api_lang = await (asyncio.wrap_future(fut) if fut else asyncio.to_thread(sarvam.stt, pcm))
    res["stt_wait_s"] = time.monotonic() - t0
    if len(text) < 3:
        res["retry"] = True; committed.set(); yield L.RETRY[agent.lang]; return
    agent.lang = L.update(agent.lang, text, api_lang)
    log(text, agent.lang)
    first = True
    async for s in agent.stream_question(text, filler=use_filler):
        if first: res["llm_first_s"] = time.monotonic() - t0; committed.set(); first = False
        yield s
    committed.set()
    res["filler"] = use_filler