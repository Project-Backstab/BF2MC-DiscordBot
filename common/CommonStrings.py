"""CommonStrings.py

Collection of commonly used public static final strings and related functions.
Date: 08/02/2023
Authors: David Wolfe (Red-Thirten)
Licensed under GNU GPLv3 - See LICENSE for more details.
"""

COUNTRY_FLAGS_URL = "https://stats.bf2mc.net/static/img/flags/<code>.png"
GM_THUMBNAILS_URL = "https://raw.githubusercontent.com/lilkingjr1/backstab-discord-bot/main/assets/gamemode_thumbnails/<gamemode>.png"
MAP_IMAGES_URL = "https://raw.githubusercontent.com/lilkingjr1/backstab-discord-bot/main/assets/map_images/<map_name>.png"
STATUS_STRINGS = {
    "online": "SERVERS: ONLINE 🟢",
    "offline": "SERVERS: OFFLINE 🔴",
    "unknown": "SERVERS: UNKNOWN"
}
GM_STRINGS = {
    "conquest": "Conquest",
    "capturetheflag": "Capture the Flag"
}
TEAM_STRINGS = {
    "US": ":flag_us:  United States:",
    "CH": ":flag_cn:  China:",
    "AC": ":flag_ir:  Middle Eastern Coalition:",
    "EU": ":flag_eu:  European Union:"
}
MAP_DATA = {
    "backstab": ("Backstab", 0),
    "bridgetoofar": ("Bridge Too Far", 1),
    "coldfront": ("Cold Front", 2),
    "dammage": ("Dammage", 3),
    "deadlypass": ("Deadly Pass", 4),
    "harboredge": ("Harbor Edge", 5),
    "honor": ("Honor", 6),
    "littlebigeye": ("Little Big Eye", 7),
    "missilecrisis": ("Missile Crisis", 8),
    "russianborder": ("Russian Border", 9),
    "specialop": ("Special Op", 10),
    "theblackgold": ("The Black Gold", 11),
    "thenest": ("The Nest", 12)
}
RANK_DATA = {
    (0, 25): ("Private", "https://raw.githubusercontent.com/lilkingjr1/persman/master/public/ranks/large/pv2.png"),
    (25, 50): ("Private 1st Class", "https://raw.githubusercontent.com/lilkingjr1/persman/master/public/ranks/large/pfc.png"),
    (50, 100): ("Corporal", "https://raw.githubusercontent.com/lilkingjr1/persman/master/public/ranks/large/cpl.png"),
    (100, 150): ("Sergeant", "https://raw.githubusercontent.com/lilkingjr1/persman/master/public/ranks/large/sgt.png"),
    (150, 225): ("Sergeant 1st Class", "https://raw.githubusercontent.com/lilkingjr1/persman/master/public/ranks/large/sfc.png"),
    (225, 360): ("Master Sergeant", "https://raw.githubusercontent.com/lilkingjr1/persman/master/public/ranks/large/msg.png"),
    (360, 550): ("Sgt. Major", "https://raw.githubusercontent.com/lilkingjr1/persman/master/public/ranks/large/sgm.png"),
    (550, 750): ("Command Sgt. Major", "https://raw.githubusercontent.com/lilkingjr1/persman/master/public/ranks/large/csm.png"),
    (750, 1050): ("Warrant Officer", "https://raw.githubusercontent.com/lilkingjr1/persman/master/public/ranks/large/wo1.png"),
    (1050, 1500): ("Chief Warrant Officer", "https://raw.githubusercontent.com/lilkingjr1/persman/master/public/ranks/large/cw4.png"),
    (1500, 2000): ("2nd Lieutenant", "https://raw.githubusercontent.com/lilkingjr1/persman/master/public/ranks/large/2lt.png"),
    (2000, 2800): ("1st Lieutenant", "https://raw.githubusercontent.com/lilkingjr1/persman/master/public/ranks/large/1lt.png"),
    (2800, 4000): ("Captain", "https://raw.githubusercontent.com/lilkingjr1/persman/master/public/ranks/large/cpt.png"),
    (4000, 5800): ("Major", "https://raw.githubusercontent.com/lilkingjr1/persman/master/public/ranks/large/maj.png"),
    (5800, 8000): ("Lieutenant Colonel", "https://raw.githubusercontent.com/lilkingjr1/persman/master/public/ranks/large/ltc.png"),
    (8000, 12000): ("Colonel", "https://raw.githubusercontent.com/lilkingjr1/persman/master/public/ranks/large/col.png"),
    (12000, 16000): ("Brigadier General", "https://www.military-ranks.org/images/ranks/army/large/brigadier-general.png"),
    (16000, 22000): ("Major General", "https://www.military-ranks.org/images/ranks/army/large/major-general.png"),
    (22000, 32000): ("Lieutenant General", "https://www.military-ranks.org/images/ranks/army/large/lieutenant-general.png"),
    (32000, float('inf')): ("5 Star General", "https://www.military-ranks.org/images/ranks/army/large/general-of-the-army.png")
}
LEADERBOARD_STRINGS = {
    "score": "Score",
    "wins": "Wins",
    "top_player": "MVP"
}


def get_rank_data(score: int) -> tuple:
    """Returns rank name and image as a tuple given a score"""
    for score_range, rank_data in RANK_DATA.items():
        if score_range[0] <= score < score_range[1]:
            return rank_data
