"""ASCII art registry for locations, specializations, and buildings."""

# ─── Locations (10-12 lines x 30-35 cols) ────────────────────────────────────

LOCATION_ART: dict[str, str] = {
    "coast": r"""
        ~  ~     .  *  ~  ~
   ~  ~   ~  ~  .    ~  ~  ~
  ~~~~~~~~~~~~~~~~~~~~~~~~~
       |     /|  .
  _____|____/ |_________
 |  *  |  H  |   __|__ |
 | === | === |  |  S  ||
 |_____|_____|  |__|__||
  ~~~ ===  ===  ~~~ ~~~
 ~~~~~~~~~~~~~~~~~~~~~~~~~
  ~  ~  ~  ~  ~  ~  ~  ~
""",

    "mountain": r"""
         /\
        /  \       /\
       / *  \     /  \
      /  /\  \   / *  \
     /  /  \  \_/    \ \
    /  /    \     /\  \ \
   /__/ (==) \___/  \__\ \
   |          ___         |
   |  /\     |   |   /\   |
   |_/  \____|___|__/  \___|
""",

    "plains": r"""
                 o
     \  |  /    /|\
      \ | /    / | \   _____
    ---( )---      |  / ___ \
      / | \  ,--+--, |     |=|
     /  |  \/ ||| \==|     |=|
  ___________||||_____|_____|___
  ~~~ ||| ||| ||| ||| ||| |||
  ~~~ ||| ||| ||| ||| ||| |||
  ________________________________
""",

    "forest": r"""
       /\      /\     /\
      /  \    /  \   /  \
     / /\ \  / /\ \ / /\ \
    / /  \ \/ /  \ / /  \ \
   / /    \  /    / /  /\ \\
  /_/______\/____/_/__/  \_\\
  |  ^  . o  .  ^ ^  .  ^ |
  | /|\ . . /|\. /|\. . /|\|
  |/ | \.  / | \/ | \. / | \|
  |__|__|___|_|__|_|__|__|__|
""",

    "desert": r"""
            \  |  /
             \.!./
          --- ( ) ---
             /'\'\
    ~~^~~        |>  ~~^~~
  ~~    ~~       |>~    ~~
 ~  ~~   ~~  |>  ~~  ~   ~
  ~~~~  [~~]  ~~   ~~~~  ~~
   ~~~~  ~~  ~~~~   ~~  ~~
  ~~  ~~~~  ~~  ~~~~  ~~~~
""",
}


# ─── Specializations (6-8 lines x 20-25 cols) ────────────────────────────────

SPECIALIZATION_ART: dict[str, str] = {
    "military": r"""
      /\  |  /\
     /  \ | /  \
    / /--\|/--\ \
   ( (  [===]  ) )
    \_\  |||  /_/
       \ ||| /
      [=======]
      |  |||  |
""",

    "trade": r"""
        ___
    ===|   |===
   /   |___|   \
  / ($)     ($) \
  \_____| |_____/
        |_|
    ($) ($) ($)
   [$][$][$][$]
""",

    "science": r"""
        /---]
       / ___/
      | |  *  *
      | |  {_}
    --|_|--/  \--
   |  * *  |__|  |
   |  {=}  *  *  |
   |_____________|
""",

    "agriculture": r"""
     \  |  /
      \.!./
    -- ( ) --
      /   \
   ||| ||| |||
   ||| ||| |||
  =============
  |  /_____\  |
  |_|  |||  |_|
""",
}


# ─── Buildings (4-5 lines x 15-20 cols) ──────────────────────────────────────

BUILDING_ART: dict[str, str] = {
    "farm": r"""
    /_____\  |||
   |  |-|  | |||
   |__|_|__| |||
   [===][===]|||
""",

    "mine": r"""
    (=======)
     \  /\  /
      \/ /\ |
     [--o---]===
""",

    "lab": r"""
      {_}  *
     /   \ |
    | === ||=|
    |_____|===
""",

    "market": r"""
    /========\
   /  ($)(#)  \
   |  [==][==] |
   |___________|
""",

    "hospital": r"""
     ___+___
    |  +-+  |
    | +-+-+ |
    |  +-+  |
    |_______|
""",

    "wall": r"""
   [=#=#=#=#=#=]
   |  ||  ||  |
   |  ||  ||  |
   [=#=#=#=#=#=]
""",

    "warehouse": r"""
    ___________
   |  [=][=]  |
   | [=][=][=]|
   |_[=][=][=]|
""",

    "housing": r"""
      /\  /\
     /  \/  \
    |[]    []|
    |  ====  |
    |__|  |__|
""",

    "school": r"""
     ___/\___
    | [====] |
    | |BOOK| |
    |_|____|_|
""",

    "watchtower": r"""
      [*]
      |=|
      |=|
     /| |\
    /_|_|_\
""",
}


def get_location_art(location_id: str) -> str:
    """Return ASCII art for a location, or empty string if not found."""
    return LOCATION_ART.get(location_id, "")


def get_specialization_art(spec_id: str) -> str:
    """Return ASCII art for a specialization, or empty string if not found."""
    return SPECIALIZATION_ART.get(spec_id, "")


def get_building_art(building_id: str) -> str:
    """Return ASCII art for a building, or empty string if not found."""
    return BUILDING_ART.get(building_id, "")


# ─── Catastrophe Art (8-10 lines x 35-40 cols) ───────────────────────────────

CATASTROPHE_ART: dict[str, str] = {
    "plague": r"""
            _____
         .-'     '-.
        /  _     _  \
       |  (o)   (o)  |
       |    __ __     |
        \  '--^--'  /
         '-._____ .-'
     ...:::   ::: :::...
    ..:::: :::  :::  ::::..
   ..::: PLAGUE SPREADS :::..
""",

    "drought": r"""
       \   |   /
        \  |  /
     --- (   ) ---  SCORCHING
        /  |  \
       /   |   \
    ________________________
     \/  \/  \/  \/  \/  \/
    _/\__/\__/\__/\__/\__/\_
    x  x    x  x    x  x
    CROPS WITHER AND DIE...
""",

    "earthquake": r"""
    ____         ____
   |    |       |    |
   |    \       /    |
   | === \\   // === |
   |______\\-//______|
         \\ //
    _____//-\\_____
   /   //     \\   \
  /___//  ___  \\\__\
     THE GROUND SPLITS
""",

    "fire": r"""
         (  (  (
        ) )  ) )  )
       (  ( /^\ (  (
      ) ) (/   \) ) )
     (  ( |  *  | (  (
      ) ) |  |  | ) )
     _____|__|__|_____
    |  #  |XXXXX|  #  |
    |_____|_____|_____|
       INFERNO RAGES!
""",

    "storm": r"""
    ~~~~~~~~~~~~~~~~~~~
      ~~~  ~~~   ~~~
        \/
        /\      |||  |||
       /  \     |||  |||
      /    \    |||  |||
     / BOLT \   |||  |||
    /________\  |||  |||
    ~^~^~^~^~^~^~^~^~^~
      TEMPEST UNLEASHED!
""",

    "raid": r"""
    -->-->    Y  Y    <--<--
    -->-->   /|\/|\   <--<--
             / \/ \
     [X]======[  ]======[X]
     |  |   BROKEN    |  |
     |  |    GATE     |  |
    _|__|______________|__|_
    Y  Y  Y        Y  Y  Y
   /|\/|\/|\      /|\/|\/|\
      INVADERS ATTACK!
""",
}


def get_catastrophe_art(category: str) -> str:
    """Return ASCII art for a catastrophe category, or empty string if not found."""
    return CATASTROPHE_ART.get(category.lower(), "")
