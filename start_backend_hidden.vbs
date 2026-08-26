Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\Users\user\Desktop\Kassa\backend"
WshShell.Run """C:\Users\user\AppData\Local\Programs\Python\Python311\python.exe"" main.py", 0, False
