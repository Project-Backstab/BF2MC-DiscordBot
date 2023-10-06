"""CommonStrings.py

Collection of commonly used public static final strings and related functions.
Date: 10/05/2023
Authors: David Wolfe (Red-Thirten)
Licensed under GNU GPLv3 - See LICENSE for more details.
"""

COUNTRY_FLAGS_URL = "https://flagcdn.com/w40/<code>.png"
LANG_FLAGS_URL = "https://www.unknown.nu/flags/images/<code>-100"
GM_THUMBNAILS_URL = "https://raw.githubusercontent.com/lilkingjr1/backstab-discord-bot/main/assets/gamemode_thumbnails/<gamemode>.png"
MAP_IMAGES_URL = "https://raw.githubusercontent.com/lilkingjr1/backstab-discord-bot/main/assets/map_images/<map_name>.png"
STATUS_STRINGS = {
    "online":   "SERVERS: ONLINE 🟢",
    "offline":  "SERVERS: OFFLINE 🔴",
    "unknown":  "SERVERS: UNKNOWN"
}
GM_STRINGS = {
    "conquest":         "Conquest",
    "capturetheflag":   "Capture the Flag"
}
TEAM_STRINGS = {
    "US": ":flag_us:  United States:",
    "CH": ":flag_cn:  China:",
    "AC": ":flag_ir:  Middle Eastern Coalition:",
    "EU": ":flag_eu:  European Union:"
}
MAP_DATA = {
    "backstab":         ("Backstab", 0),
    "bridgetoofar":     ("Bridge Too Far", 1),
    "coldfront":        ("Cold Front", 2),
    "dammage":          ("Dammage", 3),
    "deadlypass":       ("Deadly Pass", 4),
    "harboredge":       ("Harbor Edge", 5),
    "honor":            ("Honor", 6),
    "littlebigeye":     ("Little Big Eye", 7),
    "missilecrisis":    ("Missile Crisis", 8),
    "russianborder":    ("Russian Border", 9),
    "specialop":        ("Special Op", 10),
    "theblackgold":     ("The Black Gold", 11),
    "thenest":          ("The Nest", 12)
}
# Rank Data = (Min Score, Min PPH): (Rank Name, Rank Img)
RANK_DATA = {
    (float('-inf'), float('-inf')): ("Private", "https://raw.githubusercontent.com/Project-Backstab/BF2MC-DiscordBot/main/assets/rank_images/rank01.png"),
    (25, 10):       ("Private 1st Class", "https://raw.githubusercontent.com/Project-Backstab/BF2MC-DiscordBot/main/assets/rank_images/rank02.png"),
    (50, 12):       ("Corporal", "https://raw.githubusercontent.com/Project-Backstab/BF2MC-DiscordBot/main/assets/rank_images/rank03.png"),
    (100, 15):      ("Sergeant", "https://raw.githubusercontent.com/Project-Backstab/BF2MC-DiscordBot/main/assets/rank_images/rank04.png"),
    (150, 18):      ("Sergeant 1st Class", "https://raw.githubusercontent.com/Project-Backstab/BF2MC-DiscordBot/main/assets/rank_images/rank05.png"),
    (225, 25):      ("Master Sergeant", "https://raw.githubusercontent.com/Project-Backstab/BF2MC-DiscordBot/main/assets/rank_images/rank06.png"),
    (360, 28):      ("Sgt. Major", "https://raw.githubusercontent.com/Project-Backstab/BF2MC-DiscordBot/main/assets/rank_images/rank07.png"),
    (550, 30):      ("Command Sgt. Major", "https://raw.githubusercontent.com/Project-Backstab/BF2MC-DiscordBot/main/assets/rank_images/rank08.png"),
    (750, 32):      ("Warrant Officer", "https://raw.githubusercontent.com/Project-Backstab/BF2MC-DiscordBot/main/assets/rank_images/rank09.png"),
    (1050, 35):     ("Chief Warrant Officer", "https://raw.githubusercontent.com/Project-Backstab/BF2MC-DiscordBot/main/assets/rank_images/rank10.png"),
    (1500, 40):     ("2nd Lieutenant", "https://raw.githubusercontent.com/Project-Backstab/BF2MC-DiscordBot/main/assets/rank_images/rank11.png"),
    (2000, 42):     ("1st Lieutenant", "https://raw.githubusercontent.com/Project-Backstab/BF2MC-DiscordBot/main/assets/rank_images/rank12.png"),
    (2800, 50):     ("Captain", "https://raw.githubusercontent.com/Project-Backstab/BF2MC-DiscordBot/main/assets/rank_images/rank13.png"),
    (4000, 55):     ("Major", "https://raw.githubusercontent.com/Project-Backstab/BF2MC-DiscordBot/main/assets/rank_images/rank14.png"),
    (5800, 60):     ("Lieutenant Colonel", "https://raw.githubusercontent.com/Project-Backstab/BF2MC-DiscordBot/main/assets/rank_images/rank15.png"),
    (8000, 65):     ("Colonel", "https://raw.githubusercontent.com/Project-Backstab/BF2MC-DiscordBot/main/assets/rank_images/rank16.png"),
    (12000, 70):    ("Brigadier General", "https://raw.githubusercontent.com/Project-Backstab/BF2MC-DiscordBot/main/assets/rank_images/rank17.png"),
    (16000, 80):    ("Major General", "https://raw.githubusercontent.com/Project-Backstab/BF2MC-DiscordBot/main/assets/rank_images/rank18.png"),
    (22000, 90):    ("Lieutenant General", "https://raw.githubusercontent.com/Project-Backstab/BF2MC-DiscordBot/main/assets/rank_images/rank19.png"),
    (32000, 100):   ("5 Star General", "https://raw.githubusercontent.com/Project-Backstab/BF2MC-DiscordBot/main/assets/rank_images/rank20.png"),
}
MEDAL_BITMASKS = {
    "Service_Cross":                1 << 0,
    "The_Bronze_Star":              1 << 1,
    "Air_Force_Cross":              1 << 2,
    "Silver_Star":                  1 << 3,
    "Service_Cross_First_Class":    1 << 4,
    "Bronze_Star_First_Class":      1 << 5,
    "Air_Force_Cross_First_Class":  1 << 6,
    "Expert_Killing":               1 << 7,
    "Expert_Shooting":              1 << 8,
    "Expert_Demolition":            1 << 9,
    "Expert_Repair":                1 << 10,
    "Expert_Healer":                1 << 11,
    "Navy_Cross":                   1 << 12,
    "Legion_of_Merit":              1 << 13,
    "Legion_of_Merit_First_Class":  1 << 14
}
LEADERBOARD_STRINGS = {
    "score":        "Score",
    "wins":         "Wins",
    "top_player":   "MVP",
    "pph":          "Points per Hour",
    "playtime":     "Play Time"
}


def get_iso3166_from_region(region_id: int) -> str:
    if region_id == 1:
        return "us"
    elif region_id == 2048:
        return "cn"
    else:
        return "de"
    
def get_country_flag_url(region_id: int) -> str:
    return COUNTRY_FLAGS_URL.replace("<code>", get_iso3166_from_region(region_id))

def get_rank_data(score: int, pph: int) -> tuple:
    """Returns rank name and image as a tuple given a score and PPH"""
    for (min_score, min_pph), rank_data in reversed(RANK_DATA.items()):
        if score >= min_score and pph >= min_pph:
            return rank_data
