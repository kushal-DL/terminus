# Colony screen recording
# Records: colony with resources ticking, buildings panel
Output docs/gifs/colony.gif

Set Shell "powershell"
Set Width 100
Set Height 30
Set FontSize 14
Set Theme "Builtin Dark"
Set Padding 10

# Assumes game is already running and in PLAYING phase
# Start the game and wait for colony screen
Type "python -m terminus"
Enter
Sleep 2s

# Quick create + start (single player demo)
Type "c"
Sleep 500ms
Type "Demo"
Enter
Sleep 1s

# The colony screen shows resources ticking
Sleep 8s
