Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\Users\user\Desktop\Kassa\frontend"
WshShell.Run """C:\Users\user\AppData\Local\Programs\node\node.exe"" ""C:\Users\user\Desktop\Kassa\frontend\node_modules\vite\bin\vite.js""", 0, False
