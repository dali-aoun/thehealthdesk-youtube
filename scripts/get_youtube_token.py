"""
One-time script — run LOCALLY to get your YouTube refresh token.
After this, save the output as GitHub secrets and never run again.
"""
import os
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# Download client_secrets.json from Google Cloud Console first
flow = InstalledAppFlow.from_client_secrets_file("client_secrets.json", SCOPES)
creds = flow.run_local_server(port=8080)

print("\n" + "="*60)
print("SAVE THESE AS GITHUB SECRETS:")
print("="*60)
print(f"YT_CLIENT_ID     = {creds.client_id}")
print(f"YT_CLIENT_SECRET = {creds.client_secret}")
print(f"YT_REFRESH_TOKEN = {creds.refresh_token}")
print("="*60)
