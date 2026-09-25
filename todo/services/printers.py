"""Windows print spooler integration for an explicitly configured ESC/POS drawer."""
import os
from database import connect,get_setting
from services.security import audit

def installed_printers():
    if os.name!='nt':return []
    import win32print
    return sorted({row[2] for row in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL|win32print.PRINTER_ENUM_CONNECTIONS)})

def open_drawer():
    if get_setting('drawer_enabled','0')!='1':
        raise ValueError('Activez le tiroir compatible ESC/POS dans Paramètres > Impression.')
    printer=get_setting('printer_name','').strip()
    if not printer:raise ValueError('Sélectionnez une imprimante de ticket dans les paramètres.')
    pin=get_setting('drawer_pin','0')
    if pin not in ('0','1'):raise ValueError('Connecteur tiroir invalide.')
    if os.name!='nt':raise OSError('Le tiroir est disponible sous Windows.')
    import win32print
    handle=win32print.OpenPrinter(printer)
    try:
        job=win32print.StartDocPrinter(handle,1,('ToDo - Tiroir',None,'RAW'))
        try:
            win32print.StartPagePrinter(handle)
            try:
                payload=bytes((27,112,int(pin),50,250))
                if win32print.WritePrinter(handle,payload)!=len(payload):
                    raise OSError('Commande tiroir incomplète.')
            finally:win32print.EndPagePrinter(handle)
            win32print.EndDocPrinter(handle)
        except Exception:
            win32print.AbortPrinter(handle)
            raise
    finally:win32print.ClosePrinter(handle)
    with connect() as conn:audit(conn,'DRAWER_OPEN',job,printer)
    return job


def test_printer(printer=None, raw=None):
    """Send a small real test job using the configured printer mode."""
    printer=(printer if printer is not None else get_setting('printer_name','')).strip()
    if not printer:
        raise ValueError('Sélectionnez une imprimante dans les paramètres.')
    if os.name!='nt':
        raise OSError('Le test imprimante est disponible sous Windows.')
    if raw is None:
        raw=get_setting('thermal_raw','0')=='1'
    if raw:
        import win32print
        payload=b'\x1b@\x1ba\x01ToDo POS\nTEST IMPRIMANTE\nOK\n\n\x1dV\x00'
        handle=win32print.OpenPrinter(printer)
        try:
            job=win32print.StartDocPrinter(handle,1,('ToDo - Test imprimante',None,'RAW'))
            try:
                win32print.StartPagePrinter(handle)
                try:
                    if win32print.WritePrinter(handle,payload)!=len(payload):
                        raise OSError('Impression test incomplète.')
                finally:
                    win32print.EndPagePrinter(handle)
                win32print.EndDocPrinter(handle)
            except Exception:
                win32print.AbortPrinter(handle)
                raise
        finally:
            win32print.ClosePrinter(handle)
    else:
        import tempfile
        from pathlib import Path
        from subprocess import list2cmdline
        path=Path(tempfile.gettempdir())/'todo_printer_test.txt'
        path.write_text('ToDo POS\nTEST IMPRIMANTE\nOK\n',encoding='utf-8')
        os.startfile(str(path),'printto',list2cmdline([printer]))
        job=str(path)
    with connect() as conn:audit(conn,'PRINTER_TEST',None,printer)
    return job
