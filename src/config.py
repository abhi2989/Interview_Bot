
import os
from dotenv import load_dotenv
load_dotenv()
e = os.getenv
GROQ_API_KEY = e("GROQ_API_KEY")
GROQ_MODEL = e("GROQ_MODEL", "openai/gpt-oss-120b")            # evaluation + report (quality)
GROQ_FAST_MODEL = e("GROQ_FAST_MODEL", "openai/gpt-oss-20b")   # live spoken questions (speed)
SARVAM_API_KEY = e("SARVAM_API_KEY")
SARVAM_TTS_MODEL = e("SARVAM_TTS_MODEL", "bulbul:v3"); SARVAM_TTS_SPEAKER = e("SARVAM_TTS_SPEAKER", "shubh")
SARVAM_STT_MODEL = e("SARVAM_STT_MODEL", "saaras:v3")          # saaras:v3 supports mode=codemix (Hinglish)
STT_LANGUAGE = e("STT_LANGUAGE", "unknown")                    # unknown = auto-detect English/Hindi/etc.
STT_MODE = e("STT_MODE", "codemix")                            # Hindi words in Devanagari, English words in English
LANG = e("INTERVIEW_LANGUAGE", "en-IN")                        # TTS language for English sentences
BOT_NAME = e("BOT_NAME", "Aria (AI Interviewer)")
MAX_QUESTIONS = int(e("MAX_QUESTIONS", "8")); MAX_MINUTES = int(e("MAX_MINUTES", "20"))
SILENCE_MS = int(e("END_OF_TURN_SILENCE_MS", "800")); MIN_SPEECH_MS = int(e("MIN_SPEECH_MS", "250"))
STORAGE_STATE = e("GOOGLE_STORAGE_STATE", "data/auth.json")
# --- candidate invitations ---
MEET_ACCESS = e("MEET_ACCESS", "OPEN")                         # OPEN = anyone with the link joins without knocking
WAIT_MINUTES = int(e("WAIT_MINUTES", "20"))                    # how long the bot waits for the candidate
TZ_OFFSET = e("TZ_OFFSET", "+05:30"); TZ_LABEL = e("TZ_LABEL", "IST")
# --- speed ---
EARLY_STT_MS = int(e("EARLY_STT_MS", "450"))          # start transcribing after this much silence, before the turn is "final" (0 = off)
FILLER_MIN_SECONDS = float(e("FILLER_MIN_SECONDS", "2.0"))   # instant "Okay." only after answers at least this long