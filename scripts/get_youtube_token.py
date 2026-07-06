"""
One-time script — get YouTube OAuth refresh token via manual browser flow.
Writes the auth URL to a temp file, waits for callback on port 8090.
"""
import sys, os, json, urllib.parse
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"  # allow http://localhost for OAuth
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from google_auth_oauthlib.flow import Flow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
PORT   = 8090
REDIRECT = f"http://localhost:{PORT}/"
URL_FILE   = Path(os.environ["TEMP"]) / "yt_auth_url.txt"
TOKEN_FILE = Path(os.environ["TEMP"]) / "yt_tokens.txt"

flow = Flow.from_client_secrets_file(
    "client_secrets.json",
    scopes=SCOPES,
    redirect_uri=REDIRECT,
)

auth_url, state = flow.authorization_url(access_type="offline", prompt="consent")

# Write URL to file so parent process can read it
URL_FILE.write_text(auth_url, encoding="utf-8")
sys.stdout.write(f"AUTH_URL={auth_url}\n")
sys.stdout.flush()

# Wait for Google to redirect back
callback_data = {}

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        callback_data["url"] = f"http://localhost:{PORT}{self.path}"
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"<h2>Authorization complete. You can close this tab.</h2>")

server = HTTPServer(("localhost", PORT), Handler)
sys.stdout.write("WAITING_FOR_CALLBACK\n"); sys.stdout.flush()
server.handle_request()   # blocks until one request received

flow.fetch_token(authorization_response=callback_data["url"])
creds = flow.credentials

TOKEN_FILE.write_text(
    f"YT_CLIENT_ID={creds.client_id}\n"
    f"YT_CLIENT_SECRET={creds.client_secret}\n"
    f"YT_REFRESH_TOKEN={creds.refresh_token}\n",
    encoding="utf-8",
)
sys.stdout.write("TOKENS_SAVED\n"); sys.stdout.flush()

print("\n" + "="*60)
print(f"YT_CLIENT_ID     = {creds.client_id}")
print(f"YT_CLIENT_SECRET = {creds.client_secret}")
print(f"YT_REFRESH_TOKEN = {creds.refresh_token}")
print("="*60)
