!macro customInit
  IfFileExists "$INSTDIR\Uninstall SmartKassa.exe" 0 smartkassa_not_installed
    MessageBox MB_YESNO|MB_ICONQUESTION "SmartKassa allaqachon o'rnatilgan.$\r$\nEski versiyani o'chirishni xohlaysizmi?" IDYES smartkassa_do_uninstall IDNO smartkassa_not_installed
    smartkassa_do_uninstall:
      ExecWait '"$INSTDIR\Uninstall SmartKassa.exe" /S'
      MessageBox MB_OK|MB_ICONINFORMATION "Eski versiya o'chirildi.$\r$\nYangisini o'rnatish uchun ushbu faylni qayta ishga tushiring."
      Quit
  smartkassa_not_installed:
!macroend
