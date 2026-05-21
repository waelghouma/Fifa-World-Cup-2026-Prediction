from pathlib import Path
import time
import json
from dotenv import load_dotenv
import os
import requests

load_dotenv()
API_KEY = os.getenv("API_KEY")

BASE_URL  = "https://api.football-data.org/v4"
COMP_CODE = "WC" 
OUTPUT_DIR = Path("wc2026_data") 
OUTPUT_DIR.mkdir(exist_ok=True)
HEADERS = {"X-Auth-Token": API_KEY}


def get(endpoint: str, params: dict = None) -> dict:
    """Make an authenticated GET request. Respects the 10 req/min free-tier limit."""
    url = f"{BASE_URL}/{endpoint}"
    response = requests.get(url, headers=HEADERS, params=params)
 
    if response.status_code == 429:
        print("  Rate limit hit — waiting 60s...")
        time.sleep(60)
        return get(endpoint, params)
 
    if response.status_code != 200:
        print(f"  Error {response.status_code}: {response.text}")
        return {}
 
    time.sleep(6)  # Stay safely under 10 req/min
    return response.json()

def save(data: dict | list, filename: str):
    """Save raw JSON and return it for chaining."""
    path = OUTPUT_DIR / filename
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  Saved → {path}")
    return data
 
 
def fetch_competition():
    """Tournament info: name, current season, dates."""
    print("\n[1/6] Fetching competition metadata...")
    data = get(f"competitions/{COMP_CODE}")
    save(data, "competition.json")
 
    if data:
        season = data.get("currentSeason", {})
        print(f"  Tournament : {data.get('name')}")
        print(f"  Start date : {season.get('startDate')}")
        print(f"  End date   : {season.get('endDate')}")
    return data