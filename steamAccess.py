"""
steamAccess.py

Terminal script that takes a Steam username (vanity URL name) as a CLI arg,
resolves it to a SteamID64, then fetches and prints their game library.

Usage:
    export STEAM_API_KEY="your_key_here"
    or
    $env:STEAM_API_KEY="your_key_here"

    python steam_lookup.py --username coolname

Get an API key from: https://steamcommunity.com/dev/apikey
"""

import argparse
import os
import sys

import requests
import sqlite3

import time

RESOLVE_VANITY_URL = "https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/"
GET_OWNED_GAMES_URL = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"

PLAYER_DATABASE = "database.db"


def get_games(steam_id: str):
    player_connection = sqlite3.connect(PLAYER_DATABASE)
             
    player_connection.row_factory = sqlite3.Row
    player_cursor = player_connection.cursor()
    sql_query = "SELECT * FROM games WHERE steamid = ?"
    data = [steam_id]
    player_cursor.execute(sql_query,data)

   
    rows = [dict(row) for row in  player_cursor.fetchall()]

    return rows

def reset_games(steam_id: str):
    player_connection = sqlite3.connect(PLAYER_DATABASE)
         
         # Create a cursor object to execute SQL commands
    player_cursor = player_connection.cursor()
    sql_query = "DELETE FROM games WHERE steamid = ?"
    player_cursor.execute(sql_query, (steam_id,))

    player_connection.commit()
    player_connection.close()

def add_games(steam_id: str, games):
    unix_time = time.time()
    player_connection = sqlite3.connect(PLAYER_DATABASE)
             
             # Create a cursor object to execute SQL commands
    player_cursor = player_connection.cursor()
    try:
        for i in games:
            sql_query = "INSERT OR REPLACE INTO games (steamid,appid, name, playtime_forever,last_fetched) VALUES (?, ?, ?, ?, ?)"
            data = (steam_id,i.get("appid",0),i.get("name","Unknown"),i.get("playtime_forever", 0),unix_time)
            player_cursor.execute(sql_query, data)
        player_connection.commit()
    finally:
        player_connection.close()

def add_player(steam_id: str):
    unix_time = time.time()
    player_connection = sqlite3.connect(PLAYER_DATABASE)
    
    # Create a cursor object to execute SQL commands
    player_cursor = player_connection.cursor()

    try:
        sql_query = "INSERT OR REPLACE INTO players (steamid, last_fetched) VALUES (?, ?)"
        data = (steam_id, unix_time)
        player_cursor.execute(sql_query, data)
        player_connection.commit()
    finally:
        player_connection.close()

def reset_db():
    player_connection = sqlite3.connect(PLAYER_DATABASE)
    
    # Create a cursor object to execute SQL commands
    player_cursor = player_connection.cursor()
    sql_query = "DELETE FROM players"
    player_cursor.execute(sql_query)
    sql_query_2 = "DELETE FROM games"
    player_cursor.execute(sql_query_2)

def create_db():
    player_connection = sqlite3.connect(PLAYER_DATABASE)

    # Create a cursor object to execute SQL commands
    player_cursor = player_connection.cursor()

    # Create a sample table
    player_cursor.execute("""
        CREATE TABLE IF NOT EXISTS players (
            steamid TEXT PRIMARY KEY,
            last_fetched INTEGER
        )
    """)

    player_cursor.execute("""
        CREATE TABLE IF NOT EXISTS games (
            steamid TEXT KEY,
            name TEXT,
            appid INTEGER,
            playtime_forever INTEGER,
            last_fetched TIMESTAMP,

            PRIMARY KEY (steamid, appid),
            FOREIGN KEY (steamid) REFERENCES players (steamid)
    
        )
    """)



def resolve_vanity_url(api_key: str, username: str) -> str:
    """Convert a Steam vanity username (e.g. 'coolname') into a SteamID64."""
    params = {
        "key": api_key,
        "vanityurl": username,
    }
    response = requests.get(RESOLVE_VANITY_URL, params=params, timeout=10)
    response.raise_for_status()
    data = response.json().get("response", {})

    if data.get("success") != 1:
        raise ValueError(
            f"Could not resolve username '{username}'. "
            "Check the spelling, or the user may not have a custom URL set."
        )

    return data["steamid"]


def get_owned_games(api_key: str, steamid: str) -> list[dict]:
    """Fetch the list of owned games (appid, name, playtime) for a SteamID64."""
    params = {
        "key": api_key,
        "steamid": steamid,
        "include_appinfo": True,
        "include_played_free_games": True,
    }
    response = requests.get(GET_OWNED_GAMES_URL, params=params, timeout=10)
    response.raise_for_status()
    data = response.json().get("response", {})

    if "games" not in data:
        raise ValueError(
            "No games returned. This profile's game details are likely set to "
            "private, or the account owns no games."
        )

    return data["games"]


def compare_libraries(game_lists: list):
    playAGames =[]
    for i in game_lists[0]:
        playAGames.append(i.get("name"))
    sharedGames = []
    for i in game_lists[1]:
        if(i.get("name") in playAGames):
            sharedGames.append(i)
    if(len(game_lists) <= 2):
        return sharedGames
    else:
        game_lists.pop()
        game_lists[0] = sharedGames
        return compare_libraries(game_lists)
def main():
    parser = argparse.ArgumentParser(description="Look up a Steam user's game library.")
    parser.add_argument('-u', '--username', nargs='+')           # positional argument
    parser.add_argument('-i', '--id', nargs='+')      # option that takes a value
    args = parser.parse_args()
    #print(args)
    if not args.id and not args.username:
        parser.error("You must specify at least one --username or --id")
    api_key = os.environ.get("STEAM_API_KEY")
    if not api_key:
        print("Error: STEAM_API_KEY environment variable not set.", file=sys.stderr)
        print('Set it with: export STEAM_API_KEY="your_key_here"', file=sys.stderr)
        sys.exit(1)
    create_db()

    steamIds: list = list(args.id) if args.id is not None else []
    if(args.username is not None):
        usernames = list(args.username)
        for i in usernames:
            steamid = resolve_vanity_url(api_key, i)
            steamIds.append(steamid)

    gameLists = []
    try:
        for i in steamIds:
            games = get_games(i)
            if(not games):
                games = get_owned_games(api_key, i)
                
            
            games.sort(key=lambda x: x.get("playtime_forever", 0), reverse=True)
            add_games(i, games)
            gameLists.append(games)
            if(len(steamIds) == 1):
                print(f"Found {len(games)} games:\n")
                for game in games:
                    name = game.get("name", "Unknown")
                    playtime_hours = game.get("playtime_forever", 0) / 60
                    print(f"  {name:<45} {playtime_hours:>7.1f} hrs")
           # print(get_games(i))

    except (requests.RequestException, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if(len(gameLists) > 1):
        sharedGames = compare_libraries(gameLists)
        for game in sharedGames:
            name = game.get("name", "Unknown")
            print(str(name))
            


if __name__ == "__main__":
    main()