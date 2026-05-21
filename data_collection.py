from pathlib import Path
import time
import json
from dotenv import load_dotenv
import os
import requests
import pandas as pd

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


# ── 2. Group stage standings ──────────────────────────────────────────────────
 
def fetch_standings():
    """
    Group standings table.
    Returns list of groups, each with a table of teams ranked by points.
    """
    print("\n[2/6] Fetching group standings...")
    data = get(f"competitions/{COMP_CODE}/standings")
    save(data, "standings.json")
 
    rows = []
    for group in data.get("standings", []):
        group_name = group.get("group", "")
        for entry in group.get("table", []):
            team = entry.get("team", {})
            rows.append({
                "group"          : group_name,
                "position"       : entry.get("position"),
                "team"           : team.get("name"),
                "team_id"        : team.get("id"),
                "played"         : entry.get("playedGames"),
                "won"            : entry.get("won"),
                "draw"           : entry.get("draw"),
                "lost"           : entry.get("lost"),
                "goals_for"      : entry.get("goalsFor"),
                "goals_against"  : entry.get("goalsAgainst"),
                "goal_diff"      : entry.get("goalDifference"),
                "points"         : entry.get("points"),
            })
 
    df = pd.DataFrame(rows)
    df.to_csv(OUTPUT_DIR / "standings.csv", index=False)
    print(f"  {len(rows)} team-group rows saved")
    return df
 
 # ── 3. All fixtures ───────────────────────────────────────────────────────────
 
def fetch_matches():
    """
    Full fixture list — all 104 matches.
    Includes status (SCHEDULED / IN_PLAY / FINISHED), scores, referees.
    """
    print("\n[3/6] Fetching all fixtures...")
    data = get(f"competitions/{COMP_CODE}/matches")
    save(data, "matches_raw.json")
 
    rows = []
    for m in data.get("matches", []):
        home = m.get("homeTeam", {})
        away = m.get("awayTeam", {})
        score = m.get("score", {})
        ft    = score.get("fullTime", {})
 
        rows.append({
            "match_id"     : m.get("id"),
            "utc_date"     : m.get("utcDate"),
            "status"       : m.get("status"),
            "stage"        : m.get("stage"),          # GROUP_STAGE / ROUND_OF_32 etc.
            "group"        : m.get("group"),
            "matchday"     : m.get("matchday"),
            "home_team"    : home.get("name"),
            "home_team_id" : home.get("id"),
            "away_team"    : away.get("name"),
            "away_team_id" : away.get("id"),
            "home_score"   : ft.get("home"),
            "away_score"   : ft.get("away"),
            "winner"       : score.get("winner"),     # HOME_TEAM / AWAY_TEAM / DRAW
            "venue"        : m.get("venue"),
        })
 
    df = pd.DataFrame(rows)
    df["utc_date"] = pd.to_datetime(df["utc_date"])
    df.to_csv(OUTPUT_DIR / "matches.csv", index=False)
    print(f"  {len(rows)} matches saved")
    return df
 
def fetch_teams():
    """
    Squad data for all 48 teams: players, positions, nationalities, shirt numbers.
    One API call per team — uses most of your daily quota; run once and cache.
    """
    print("\n[4/6] Fetching team squads (48 calls, ~5 mins)...")
    teams_data = get(f"competitions/{COMP_CODE}/teams")
    save(teams_data, "teams_list.json")
 
    team_rows   = []
    player_rows = []
 
    for team in teams_data.get("teams", []):
        tid   = team.get("id")
        tname = team.get("name")
        team_rows.append({
            "team_id"    : tid,
            "name"       : tname,
            "short_name" : team.get("shortName"),
            "tla"        : team.get("tla"),           # Three-letter abbreviation
            "founded"    : team.get("founded"),
            "venue"      : team.get("venue"),
            "coach"      : team.get("coach", {}).get("name"),
            "coach_nationality": team.get("coach", {}).get("nationality"),
        })
 
        # Individual squad details
        detail = get(f"teams/{tid}")
        for p in detail.get("squad", []):
            player_rows.append({
                "team_id"     : tid,
                "team"        : tname,
                "player_id"   : p.get("id"),
                "name"        : p.get("name"),
                "position"    : p.get("position"),
                "nationality" : p.get("nationality"),
                "dob"         : p.get("dateOfBirth"),
                "shirt_number": p.get("shirtNumber"),
            })
 
    pd.DataFrame(team_rows).to_csv(OUTPUT_DIR / "teams.csv", index=False)
    df_players = pd.DataFrame(player_rows)
    df_players["age"] = (
        pd.Timestamp.now() - pd.to_datetime(df_players["dob"])
    ).dt.days / 365.25
    df_players.to_csv(OUTPUT_DIR / "squads.csv", index=False)
 
    print(f"  {len(team_rows)} teams, {len(player_rows)} players saved")
    return df_players
 
 
data = fetch_competition()
standings = fetch_standings()
matches = fetch_matches()
teams = fetch_teams()