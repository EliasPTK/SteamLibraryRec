"""
steamAccess.py

Terminal script that takes a Steam username or id as a CLI arg,
resolves it to a SteamID64, then fetches and prints their game library.

Usage:
    export STEAM_API_KEY="your_key_here"
    or
    $env:STEAM_API_KEY="your_key_here"

    python steam_lookup.py --username SteamUserName
    or
    python steam_lookup.py --id SteamUserID
    or
    python steam_lookup.py --id SteamUserId --username SteamUserName

    Note that username only works if a Steam user has set up a vanity steam name

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
STORE_APP_DETAILS_URL = "https://store.steampowered.com/api/appdetails"

PLAYER_DATABASE = "database.db"

"""
Input: steam_id: str, the id of a steam user as a string
Output: A dictionary containing all games a user owns

Purpose: To obtain all games that a user owns, plus some additional information
like playtime, and the last time this information was cached
"""
def get_games(steam_id: str):
    player_connection = sqlite3.connect(PLAYER_DATABASE)
             
    player_connection.row_factory = sqlite3.Row
    try:
        player_cursor = player_connection.cursor()
        sql_query = "SELECT * FROM games WHERE steamid = ?"
        data = [steam_id]
        player_cursor.execute(sql_query,data)
        rows = [dict(row) for row in  player_cursor.fetchall()]
        
        return rows
        
    finally:
        player_connection.close()

   
"""
Input: steam_id: str, the id of a steam user as a string
Output: None

Purpose: Deletes all cached information of the game's a user owns in the database
"""
def reset_games(steam_id: str):
    player_connection = sqlite3.connect(PLAYER_DATABASE)
         
         # Create a cursor object to execute SQL commands
    try:
        player_cursor = player_connection.cursor()
        sql_query = "DELETE FROM games WHERE steamid = ?"
        player_cursor.execute(sql_query, (steam_id,))

        player_connection.commit()
    finally:
        player_connection.close()
    
"""
Input: app_id: int, the application id of a game
Output: None

Purpose: If the game is not already in the database, all information on it, including genre
is added
"""
def add_single_game(app_id: int):
    res = get_single_game(app_id)
    if(not res):
        gameGenres = get_game_genres(app_id)

        player_connection = sqlite3.connect(PLAYER_DATABASE)
            
        # Create a cursor object to execute SQL commands
        player_cursor = player_connection.cursor()
    
        try:
            sql_query = "INSERT OR REPLACE INTO gameFacts (appid, genre, categories) VALUES (?, ?, ?)"
            data = (app_id, str(gameGenres[0]),str(gameGenres[1]))
            player_cursor.execute(sql_query, data)
            player_connection.commit()
        finally:
            player_connection.close()
        
"""
Input: app_id: int, the application id of a game
Output: A dictionary containing information on the inputted game

Purpose: To access information about a game that is stored in the database
"""
def get_single_game(app_id: int):
    player_connection = sqlite3.connect(PLAYER_DATABASE)
                 
    player_connection.row_factory = sqlite3.Row
    try:
        player_cursor = player_connection.cursor()
        sql_query = "SELECT * FROM gameFacts WHERE appid = ?"
        data = [app_id]
        player_cursor.execute(sql_query,data)
        rows = [dict(row) for row in  player_cursor.fetchall()]
        return rows
    finally:
        player_connection.close()
        
"""
Input: steam_id: the id of a steam user as a string, games: a list of all games
Output: None

Purpose: To add all the games that a user owns to the database as owned by them
"""
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

    for i in games:
            add_single_game(i.get("appid"))
    
"""
Input: steam_id: the id of a steam user as a string
Output: None

Purpose: Add information on a steam user to the database
"""
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

"""
Input: None
Output: None

Purpose: Deletes everything currently in the database
"""
def reset_db():
    player_connection = sqlite3.connect(PLAYER_DATABASE)
    
    # Create a cursor object to execute SQL commands
    try:
        player_cursor = player_connection.cursor()
        sql_query = "DELETE FROM players"
        player_cursor.execute(sql_query)
        sql_query_2 = "DELETE FROM games"
        player_cursor.execute(sql_query_2)

        sql_query_3 = "DELETE FROM gameFacts"
        player_cursor.execute(sql_query_3)
        player_connection.commit()
    finally:
        player_connection.close()

"""
Input: None
Output: None

Purpose: Creates all neccesary databases
"""
def create_db():
    player_connection = sqlite3.connect(PLAYER_DATABASE)

    try:
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

        player_cursor.execute("""
                CREATE TABLE IF NOT EXISTS gameFacts (
                    appid INTEGER PRIMARY KEY,
                    genre TEXT,
                    categories TEXT
                    
            
                )
            """)
    finally:
        player_cursor.close()

"""
Input: appid: int, the application id of a game
Output: A list containing the genres and categories a game falls into

Purpose: Used to access information on a game from the steam web store
"""
def get_game_genres(appid: int) -> list[str]:
    time.sleep(1)
    params = {"appids": appid}
    response = requests.get(STORE_APP_DETAILS_URL, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()
    app_data = data.get(str(appid))
    if app_data is None or not app_data.get("success"):
        return ["Null",["Null"]]

    details = app_data["data"]
    genres = [g["description"] for g in details.get("genres", [])]
    categories = [c["description"] for c in details.get("categories", [])]
    

    return [genres, categories]


"""
Input: api_key: str, the api_key of the application, username: str, the username of the user
Output: json, Information on that user

Purpose: Used to access information on a user from the steam web api
"""
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

"""
Input: api_key: str, the api_key of the application, steamid: str, the id of the user
Output: all games that the user owns

Purpose: Used to access information on the games a user owns from the steam web api
"""
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

"""
Input: game_lists, a list of games owned by users
Output: A list of all games that the users share
Purpose: Used to find the games that inputted users own
"""
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
                    facts = get_single_game(game.get("appid"))[0]
                   
                    genre = facts.get("genre","Null")
                    
                    print(f"  {name:<45} {genre} {playtime_hours:>7.1f} hrs")
                    
        

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