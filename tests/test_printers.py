import sys,unittest,tempfile
from pathlib import Path
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'todo'))
import database
from services import printers
from services.bootstrap import ensure_defaults
from services.security import current_user

class PrinterTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.old=database.DB_PATH
        database.DB_PATH=Path(self.temp.name)/'test.db';database.init_db();ensure_defaults()
        with database.connect() as c:uid=c.execute('SELECT id FROM users').fetchone()[0]
        self.token=current_user.set(uid)
    def tearDown(self):
        database.DB_PATH=self.old;current_user.reset(self.token);self.temp.cleanup()
    def test_disabled_drawer_sends_nothing(self):
        api=Mock()
        with patch.dict(sys.modules,win32print=api):
            with self.assertRaises(ValueError):printers.open_drawer()
            api.OpenPrinter.assert_not_called()
    def test_drawer_payload_cleanup_and_audit(self):
        database.set_setting('drawer_enabled','1');database.set_setting('printer_name','Receipt Test')
        api=Mock();api.OpenPrinter.return_value=99;api.StartDocPrinter.return_value=7;api.WritePrinter.return_value=5
        with patch.dict(sys.modules,win32print=api),patch.object(printers.os,'name','nt'):
            self.assertEqual(printers.open_drawer(),7)
        api.WritePrinter.assert_called_once_with(99,bytes([27,112,0,50,250]))
        api.EndDocPrinter.assert_called_once_with(99);api.ClosePrinter.assert_called_once_with(99)
        with database.connect() as c:self.assertEqual(c.execute("SELECT COUNT(*) FROM audit_log WHERE action='DRAWER_OPEN'").fetchone()[0],1)
    def test_failed_write_aborts_and_closes(self):
        database.set_setting('drawer_enabled','1');database.set_setting('printer_name','Receipt Test')
        api=Mock();api.OpenPrinter.return_value=99;api.WritePrinter.return_value=2
        with patch.dict(sys.modules,win32print=api),patch.object(printers.os,'name','nt'):
            with self.assertRaises(OSError):printers.open_drawer()
        api.AbortPrinter.assert_called_once_with(99);api.ClosePrinter.assert_called_once_with(99)
