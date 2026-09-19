Option Explicit
Dim shell, fso, folder, cmd
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
folder = fso.GetParentFolderName(WScript.ScriptFullName)

' First try the normal Python Windows launcher.
cmd = "pyw -3 """ & folder & "\ToDo.pyw"""
On Error Resume Next
shell.Run cmd, 0, False
If Err.Number = 0 Then
    WScript.Quit
End If
Err.Clear

' Fallback to pythonw.
cmd = "pythonw """ & folder & "\ToDo.pyw"""
shell.Run cmd, 0, False
If Err.Number = 0 Then
    WScript.Quit
End If

MsgBox "Python n'a pas été trouvé. Lancez DEBUG_TODO.bat pour voir le détail.", 16, "ToDo"
