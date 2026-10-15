"""English / Hindi / Hinglish handling: detection from the candidate's transcript + canned phrases."""
import re

DEV = re.compile(r"[\u0900-\u097F]")
LATIN_HI = set("""hai hain hu hoon nahi nahin kya kaise kyun kyu aap aapka aapke main mera meri mere mujhe hum humne toh
tha thi the karna karta karti kiya kiye kar raha rahi rahe liye se ko ke ki ka ek par aur lekin bhi abhi bahut accha acha
theek thoda matlab jaise yeh ye woh wo iska uska isme usme kaam samajh bataiye bolo haan ji""".split())

def detect(text, api_lang=None):
    """Return 'en' | 'hi' | 'hinglish' | None (not enough signal)."""
    letters = [c for c in text if c.isalpha()]
    if len(letters) < 3: return None
    dev = sum(1 for c in letters if DEV.match(c)) / len(letters)
    words = re.findall(r"[a-z]+", text.lower())
    latin_share = 1 - dev
    if dev > 0.15 and latin_share > 0.15: return "hinglish"          # Devanagari + English words
    if dev >= 0.85: return "hi"
    if dev > 0: return "hinglish" if latin_share > 0.15 else "hi"
    hi_words = sum(w in LATIN_HI for w in words)                       # Hindi written in Roman letters
    if hi_words >= 2 or (words and hi_words / len(words) >= 0.2): return "hinglish"
    if api_lang and api_lang.startswith("hi") and len(words) >= 3: return "hinglish"
    return "en"

def update(current, text, api_lang=None):
    """Follow the candidate's language; ignore one-word answers like 'yes' or 'haan'."""
    if len(text.split()) < 3: return current
    return detect(text, api_lang) or current

RETRY = {
    "en": "Sorry, I didn't catch that. Could you please say it again?",
    "hi": "माफ़ कीजिए, मैं सुन नहीं पाया। क्या आप दोबारा बोल सकते हैं?",
    "hinglish": "Sorry, मैं ठीक से सुन नहीं पाया। क्या आप please दोबारा बोल सकते हैं?",
}
CLOSING = {
    "en": "Thank you for your time. That's all the questions I have. The hiring team will be in touch. Goodbye!",
    "hi": "आपके समय के लिए धन्यवाद। मेरे सवाल यहीं ख़त्म होते हैं। हायरिंग टीम जल्द ही आपसे संपर्क करेगी। नमस्ते!",
    "hinglish": "आपके time के लिए thank you। मेरे questions यहीं ख़त्म होते हैं। Hiring team जल्द ही आपसे contact करेगी। Goodbye!",
}

# "please repeat" requests (English / Hinglish / Hindi): the bot repeats its last question without calling the LLM
REPEAT_RE = re.compile(r"(repeat|say (that )?again|once again|come again|pardon|didn'?t (get|catch|understand|hear)|can'?t hear|"
                       r"not clear|dobara|dubara|phir se|fir se|samajh nahi|samjha nahi|समझ नहीं|दोबारा|दुबारा|फिर से|फ़िर से|क्या कहा)", re.I)
REPEAT = {"en": "Sure, let me say that again.", "hi": "ज़रूर, मैं दोबारा पूछता हूँ।", "hinglish": "Sure, मैं दोबारा पूछता हूँ।"}

# Instant spoken reactions, pre-synthesized at startup so they play with zero delay after the candidate stops
import random
FILLERS = {"en": ["Okay.", "Right.", "I see.", "Alright."],
           "hi": ["जी।", "ठीक है।", "अच्छा।", "समझ गया।"],
           "hinglish": ["Okay, ठीक है।", "Right, अच्छा।", "I see, ठीक है।"]}
_last = {"v": None}
def pick_filler(lang):
    choices = [f for f in FILLERS.get(lang, FILLERS["en"]) if f != _last["v"]] or FILLERS["en"]
    _last["v"] = random.choice(choices); return _last["v"]
PRIME = [f for v in FILLERS.values() for f in v] + list(RETRY.values()) + list(REPEAT.values()) + list(CLOSING.values())