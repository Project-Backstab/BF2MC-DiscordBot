"""CommonStrings.py

Collection of commonly used public static final strings and related functions.
Date: 10/16/2023
Authors: David Wolfe (Red-Thirten)
Licensed under GNU GPLv3 - See LICENSE for more details.
"""

COUNTRY_FLAGS_URL = "https://flagcdn.com/w40/<code>.png"
LANG_FLAGS_URL = "https://www.unknown.nu/flags/images/<code>-100"
GM_THUMBNAILS_URL = "https://raw.githubusercontent.com/lilkingjr1/backstab-discord-bot/main/assets/gamemode_thumbnails/<gamemode>.png"
MAP_IMAGES_URL = "https://raw.githubusercontent.com/lilkingjr1/backstab-discord-bot/main/assets/map_images/<map_name>.png"
RANK_IMAGES_URL = "https://raw.githubusercontent.com/Project-Backstab/BF2MC-DiscordBot/main/assets/rank_images/rank<rank_id>.png"
STATUS_STRINGS = {
    "online":   "SERVERS: ONLINE 🟢",
    "offline":  "SERVERS: OFFLINE 🔴",
    "unknown":  "SERVERS: UNKNOWN"
}
GM_STRINGS = {
    "conquest":         ("Conquest", 1),
    "capturetheflag":   ("Capture the Flag", 2)
}
TEAM_STRINGS = {
    "US": (":flag_us:  United States:", 1),
    "CH": (":flag_cn:  China:", 2),
    "AC": (":flag_ir:  Middle Eastern Coalition:", 3),
    "EU": (":flag_eu:  European Union:", 4)
}
MAP_STRINGS = (
    "Backstab",
    "Bridge Too Far",
    "Cold Front",
    "Dammage",
    "Deadly Pass",
    "Harbor Edge",
    "Honor",
    "Little Big Eye",
    "Missile Crisis",
    "Russian Border",
    "Special Op",
    "The Black Gold",
    "The Nest",
)
# Rank Data = (Rank Name, Rank Img URL)
RANK_DATA = (
    ("Private", RANK_IMAGES_URL.replace("<rank_id>", "01")),
    ("Private 1st Class", RANK_IMAGES_URL.replace("<rank_id>", "02")),
    ("Corporal", RANK_IMAGES_URL.replace("<rank_id>", "03")),
    ("Sergeant", RANK_IMAGES_URL.replace("<rank_id>", "04")),
    ("Sergeant 1st Class", RANK_IMAGES_URL.replace("<rank_id>", "05")),
    ("Master Sergeant", RANK_IMAGES_URL.replace("<rank_id>", "06")),
    ("Sgt. Major", RANK_IMAGES_URL.replace("<rank_id>", "07")),
    ("Command Sgt. Major", RANK_IMAGES_URL.replace("<rank_id>", "08")),
    ("Warrant Officer", RANK_IMAGES_URL.replace("<rank_id>", "09")),
    ("Chief Warrant Officer", RANK_IMAGES_URL.replace("<rank_id>", "10")),
    ("2nd Lieutenant", RANK_IMAGES_URL.replace("<rank_id>", "11")),
    ("1st Lieutenant", RANK_IMAGES_URL.replace("<rank_id>", "12")),
    ("Captain", RANK_IMAGES_URL.replace("<rank_id>", "13")),
    ("Major", RANK_IMAGES_URL.replace("<rank_id>", "14")),
    ("Lieutenant Colonel", RANK_IMAGES_URL.replace("<rank_id>", "15")),
    ("Colonel", RANK_IMAGES_URL.replace("<rank_id>", "16")),
    ("Brigadier General", RANK_IMAGES_URL.replace("<rank_id>", "17")),
    ("Major General", RANK_IMAGES_URL.replace("<rank_id>", "18")),
    ("Lieutenant General", RANK_IMAGES_URL.replace("<rank_id>", "19")),
    ("5 Star General", RANK_IMAGES_URL.replace("<rank_id>", "20"))
)
MEDALS_DATA = {
    "The_Service_Cross":            (1 << 0, "The Service Cross", "Kill 5 enemies without dying, using kit weapons only."),
    "The_Bronze_Star":              (1 << 1, "The Bronze Star", "Kill 10 enemies without dying, using land vehicle weapons."),
    "Air_Force_Cross":              (1 << 2, "Air Force Cross", "Kill 10 enemies without dying, using aerial weapons."),
    "The_Silver_Star":              (1 << 3, "The Silver Star", "Kill 20 enemies without dying, using vehicle weapons."),
    "The_Service_Cross_1st_Class":  (1 << 4, "The Service Cross, 1st Class", "Kill 10 enemies without dying, using kit weapons only."),
    "The_Bronze_Star_1st_Class":    (1 << 5, "The Bronze Star, 1st Class", "Kill 15 enemies without dying, using land vehicle weapons."),
    "Air_Force_Cross_1st_Class":    (1 << 6, "Air Force Cross, 1st Class", "Kill 15 enemies without dying, using aerial weapons."),
    "Expert_Killing":               (1 << 7, "Expert Killing", "Kill 4 enemies without dying, using one clip in a assault rifle."),
    "Expert_Shooting":              (1 << 8, "Expert Shooting", "Kill 4 enemies without dying, using one clip in a sniper rifle."),
    "Expert_Demolition":            (1 << 9, "Expert Demolition", "Destroy 4 enemy vehicles with C4 without dying."),
    "Expert_Repair":                (1 << 10, "Expert Repair", "Repair 5 friendly vehicles without dying. A third of their health must be restored."),
    "Expert_Healer":                (1 << 11, "Expert Healer", "Heal 4 friendly players without dying. A third of their health must be restored."),
    "Navy_Cross":                   (1 << 12, "Navy Cross", "Kill 30 enemies without dying, using kit weapons only."),
    "Legion_of_Merit":              (1 << 13, "Legion of Merit", "Kill 15 enemies from a secondary position in a vehicle during one game round."),
    "Legion_of_Merit_1st_Class":    (1 << 14, "Legion of Merit First Class", "Kill 30 enemies from a secondary position in a vehicle during one game round.")
}
RIBBONS_DATA = {
    "Games_Played_50":      ("50 Games Played", "Participate in 50 game sessions"),
    "Games_Played_250":     ("250 Games Played", "Participate in 250 game sessions"),
    "Games_Played_500":     ("500 Games Played", "Participate in 500 game sessions"),
    "Major_Victories_5":    ("5 Major Victories", "Complete 5 Major Victories"),
    "Major_Victories_20":   ("20 Major Victories", "Complete 20 Major Victories"),
    "Major_Victories_50":   ("50 Major Victories", "Complete 50 Major Victories"),
    "Top_Player_5":         ("5 Games Top Player", "Finish top player in 5 game rounds"),
    "Top_Player_20":        ("20 Games Top Player", "Finish top player in 20 game rounds")
}
LEADERBOARD_STRINGS = {
    "score":    "Score",
    "mv":       "Major Victories",
    "ttb":      "MVP",
    "pph":      "Points per Hour",
    "time":     "Play Time",
    "kills":     "Kills"
}
CLAN_RANK_STRINGS = (
    "Leader",
    "Co-Leader",
    "Member"
)


def get_iso3166_from_region(region_id: int) -> str:
    if region_id == 1:
        return "us"
    elif region_id == 2048:
        return "cn"
    else:
        return "de"
    
def get_country_flag_url(region_id: int) -> str:
    return COUNTRY_FLAGS_URL.replace("<code>", get_iso3166_from_region(region_id))

def get_clan_region_flag_url(clan_region: int) -> str:
    _region_id = 1 # Default: America
    if clan_region == 2: # Europe
        _region_id = 65536
    elif clan_region == 3: # Asia
        _region_id = 2048
    return get_country_flag_url(_region_id)
