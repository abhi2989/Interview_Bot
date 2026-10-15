"""Google OAuth for creating Meet links and sending invitation emails.
ONE-TIME, run on your PC (not in Docker):   pip install google-auth-oauthlib   then   python -m src.google_auth
Needs data/client_secret.json (OAuth client of type 'Desktop app'). Saves data/token.json (refresh token).
Inside Docker only access_token() is used (plain HTTPS, no Google libraries needed)."""
import json, time
import httpx

SCOPES = ["https://www.googleapis.com/auth/meetings.space.created",
          "https://www.googleapis.com/auth/gmail.send"]
SECRET, TOKEN = "data/client_secret.json", "data/token.json"
_cache = {}

def _read_secret():
    """Read client_secret.json, tolerating a BOM / UTF-16 (PowerShell often writes these), with clear errors."""
    raw = open(SECRET, "rb").read()
    if not raw.strip():
        raise SystemExit(f"{SECRET} is EMPTY. Download the real file: Google Cloud Console -> APIs & Services -> "
                         "Credentials -> your Desktop app client -> Download JSON, then save it as " + SECRET)
    cfg = None
    for enc in ("utf-8-sig", "utf-16"):
        try: cfg = json.loads(raw.decode(enc)); break
        except (UnicodeError, json.JSONDecodeError): pass
    if cfg is None:
        raise SystemExit(f"{SECRET} is not valid JSON ({len(raw)} bytes, starts with {raw[:12]!r}). "
                         "It looks like a web page or a damaged file: download the JSON from Google Cloud again.")
    if "installed" not in cfg:
        raise SystemExit(f"{SECRET} has keys {list(cfg)} but needs 'installed'. Create the OAuth client with "
                         "Application type = Desktop app and download that JSON.")
    return cfg

def login():
    from google_auth_oauthlib.flow import InstalledAppFlow
    flow = InstalledAppFlow.from_client_config(_read_secret(), SCOPES)
    c = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    json.dump({"client_id": c.client_id, "client_secret": c.client_secret,
               "refresh_token": c.refresh_token}, open(TOKEN, "w"))
    print("saved", TOKEN)

def access_token() -> str:
    if _cache.get("exp", 0) > time.time() + 60: return _cache["tok"]
    t = json.load(open(TOKEN))
    r = httpx.post("https://oauth2.googleapis.com/token", timeout=20, data={
        "client_id": t["client_id"], "client_secret": t["client_secret"],
        "refresh_token": t["refresh_token"], "grant_type": "refresh_token"})
    if r.is_error: raise RuntimeError(f"Google auth {r.status_code}: {r.text}")
    j = r.json(); _cache.update(tok=j["access_token"], exp=time.time() + j["expires_in"])
    return _cache["tok"]

if __name__ == "__main__":
    login()