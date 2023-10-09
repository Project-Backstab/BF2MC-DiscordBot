"""CommonStrings.py

Collection of commonly used public static final strings and related functions.
Date: 10/08/2023
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
    "conquest":         ("Conquest", 1),
    "capturetheflag":   ("Capture the Flag", 2)
}
TEAM_STRINGS = {
    "US": (":flag_us:  United States:", 1),
    "CH": (":flag_cn:  China:", 2),
    "AC": (":flag_ir:  Middle Eastern Coalition:", 3),
    "EU": (":flag_eu:  European Union:", 4)
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
# Rank Data = (Rank Name, Rank Img)
# TODO: Change 'v4.0.0-bfmc-spy' back to 'main'
RANK_DATA = (
    ("Private", "https://raw.githubusercontent.com/Project-Backstab/BF2MC-DiscordBot/v4.0.0-bfmc-spy/assets/rank_images/rank01.png"),
    ("Private 1st Class", "https://raw.githubusercontent.com/Project-Backstab/BF2MC-DiscordBot/v4.0.0-bfmc-spy/assets/rank_images/rank02.png"),
    ("Corporal", "https://raw.githubusercontent.com/Project-Backstab/BF2MC-DiscordBot/v4.0.0-bfmc-spy/assets/rank_images/rank03.png"),
    ("Sergeant", "https://raw.githubusercontent.com/Project-Backstab/BF2MC-DiscordBot/v4.0.0-bfmc-spy/assets/rank_images/rank04.png"),
    ("Sergeant 1st Class", "https://raw.githubusercontent.com/Project-Backstab/BF2MC-DiscordBot/v4.0.0-bfmc-spy/assets/rank_images/rank05.png"),
    ("Master Sergeant", "https://raw.githubusercontent.com/Project-Backstab/BF2MC-DiscordBot/v4.0.0-bfmc-spy/assets/rank_images/rank06.png"),
    ("Sgt. Major", "https://raw.githubusercontent.com/Project-Backstab/BF2MC-DiscordBot/v4.0.0-bfmc-spy/assets/rank_images/rank07.png"),
    ("Command Sgt. Major", "https://raw.githubusercontent.com/Project-Backstab/BF2MC-DiscordBot/v4.0.0-bfmc-spy/assets/rank_images/rank08.png"),
    ("Warrant Officer", "https://raw.githubusercontent.com/Project-Backstab/BF2MC-DiscordBot/v4.0.0-bfmc-spy/assets/rank_images/rank09.png"),
    ("Chief Warrant Officer", "https://raw.githubusercontent.com/Project-Backstab/BF2MC-DiscordBot/v4.0.0-bfmc-spy/assets/rank_images/rank10.png"),
    ("2nd Lieutenant", "https://raw.githubusercontent.com/Project-Backstab/BF2MC-DiscordBot/v4.0.0-bfmc-spy/assets/rank_images/rank11.png"),
    ("1st Lieutenant", "https://raw.githubusercontent.com/Project-Backstab/BF2MC-DiscordBot/v4.0.0-bfmc-spy/assets/rank_images/rank12.png"),
    ("Captain", "https://raw.githubusercontent.com/Project-Backstab/BF2MC-DiscordBot/v4.0.0-bfmc-spy/assets/rank_images/rank13.png"),
    ("Major", "https://raw.githubusercontent.com/Project-Backstab/BF2MC-DiscordBot/v4.0.0-bfmc-spy/assets/rank_images/rank14.png"),
    ("Lieutenant Colonel", "https://raw.githubusercontent.com/Project-Backstab/BF2MC-DiscordBot/v4.0.0-bfmc-spy/assets/rank_images/rank15.png"),
    ("Colonel", "https://raw.githubusercontent.com/Project-Backstab/BF2MC-DiscordBot/v4.0.0-bfmc-spy/assets/rank_images/rank16.png"),
    ("Brigadier General", "https://raw.githubusercontent.com/Project-Backstab/BF2MC-DiscordBot/v4.0.0-bfmc-spy/assets/rank_images/rank17.png"),
    ("Major General", "https://raw.githubusercontent.com/Project-Backstab/BF2MC-DiscordBot/v4.0.0-bfmc-spy/assets/rank_images/rank18.png"),
    ("Lieutenant General", "https://raw.githubusercontent.com/Project-Backstab/BF2MC-DiscordBot/v4.0.0-bfmc-spy/assets/rank_images/rank19.png"),
    ("5 Star General", "https://raw.githubusercontent.com/Project-Backstab/BF2MC-DiscordBot/v4.0.0-bfmc-spy/assets/rank_images/rank20.png")
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
