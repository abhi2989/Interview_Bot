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

def login():
    from google_auth_oauthlib.flow import InstalledAppFlow
    flow = InstalledAppFlow.from_client_secrets_file(SECRET, SCOPES)
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