del .\GalaxyTimer.exe
pyinstaller -w --hidden-import=pyttsx3 ./pyscript/galaxytimer.py -i Resources/icon/icon.ico
pause
