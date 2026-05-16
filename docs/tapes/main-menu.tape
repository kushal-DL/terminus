# Main Menu recording
# Records: title screen → create game flow
Output docs/gifs/main-menu.gif

Set Shell "powershell"
Set Width 100
Set Height 30
Set FontSize 14
Set Theme "Builtin Dark"
Set Padding 10

Type "python -m terminus"
Enter
Sleep 2s

# Navigate main menu
Type "c"
Sleep 1s

# Enter name
Type "DemoPlayer"
Sleep 500ms
Enter
Sleep 2s

# Show lobby briefly
Sleep 3s
