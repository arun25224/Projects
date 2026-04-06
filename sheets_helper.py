import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
import logging
import string
import os
import json

# Fetch secrets from Hugging Face Environment
SERVICE_ACCOUNT_JSON = os.getenv("GCP_SERVICE_ACCOUNT")
ATTENDANCE_SHEET_ID = os.getenv("ATTENDANCE_SHEET_ID") 
CLAIMS_SHEET_ID = os.getenv("CLAIMS_SHEET_ID") 

SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

def get_gspread_client():
    """Authenticates and returns a gspread client using the service account[cite: 39]."""
    if not SERVICE_ACCOUNT_JSON:
        raise ValueError("GCP_SERVICE_ACCOUNT secret is missing.")
    creds_dict = json.loads(SERVICE_ACCOUNT_JSON)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
    return gspread.authorize(creds)

def col_index_to_letter(n: int) -> str:
    """Converts a 1-based column index to an A1-notation column letter[cite: 39, 40]."""
    result = ""
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        result = string.ascii_uppercase[remainder] + result
    return result

def update_attendance(uploaded_df: pd.DataFrame, event_id: str, event_name: str) -> dict:
    """Matches emails from the uploaded Wooclap file against the master sheet[cite: 42]."""
    client = get_gspread_client()
    sh = client.open_by_key(ATTENDANCE_SHEET_ID)
    ws = sh.worksheet("Members") # Adjust to your actual tab name

    master_df = pd.DataFrame(ws.get_all_records())
    master_df.columns = master_df.columns.str.strip()

    if 'Email' not in master_df.columns:
        raise ValueError("Master sheet is missing an 'Email' column[cite: 44].")

    email_col = next((c for c in uploaded_df.columns if 'email' in c.lower()), None)
    if email_col is None:
        raise ValueError("Uploaded file is missing an 'Email' column[cite: 45].")
    if email_col != 'Email':
        uploaded_df = uploaded_df.rename(columns={email_col: 'Email'})

    uploaded_emails = set(uploaded_df['Email'].str.strip().str.lower().dropna())
    master_emails = master_df['Email'].str.strip().str.lower()

    attendance_values = master_emails.apply(lambda email: 1 if email in uploaded_emails else 0).tolist()
    col_header = f"{event_id}_{event_name.replace(' ', '_')}"
    next_col = len(master_df.columns) + 1

    col_letter = col_index_to_letter(next_col)
    all_values = [[col_header]] + [[v] for v in attendance_values]
    ws.update(f'{col_letter}1', all_values)

    return {"matched": sum(attendance_values), "total": len(master_df), "column_name": col_header}

def append_claim(claim_dict: dict):
    """Appends a new claim row to the Claims Master Sheet."""
    client = get_gspread_client()
    sh = client.open_by_key(CLAIMS_SHEET_ID)
    ws = sh.sheet1 # Opens the first tab

    # Convert dict to a list of values ordered by your columns
    row_values = list(claim_dict.values())
    ws.append_row(row_values)
