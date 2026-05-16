# Build screen recording
# Records: opening build screen, selecting building, constructing
Output docs/gifs/build.gif

Set Shell "powershell"
Set Width 100
Set Height 30
Set FontSize 14
Set Theme "Builtin Dark"
Set Padding 10

# Assumes game is in PLAYING phase on colony screen
# Press 'b' to open build screen
Type "b"
Sleep 1s

# Navigate building list
Down
Sleep 500ms
Down
Sleep 500ms
Up
Sleep 500ms

# Select and build
Enter
Sleep 2s

# Go back
Escape
Sleep 1s
