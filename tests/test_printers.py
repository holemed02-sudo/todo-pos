import sys,unittest,tempfile
from pathlib import Path
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'todo'))
import database
from services import printers,receipts
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
    def test_escpos_receipt_contains_init_cut_and_optional_drawer(self):
        with database.connect() as c:
            c.execute("INSERT INTO cash_sessions(user_id,opening_cash_cents,status) VALUES(?,0,'OPEN')",(current_user.get(),))
            sid=c.execute("SELECT last_insert_rowid()").fetchone()[0]
            c.execute("INSERT INTO sales(sale_no,session_id,cashier_user_id,subtotal_cents,discount_cents,total_cents,payment_method,paid_cents,change_cents) VALUES('T-1',?,?,1000,0,1000,'CASH',1000,0)",(sid,current_user.get()))
            sale_id=c.execute("SELECT last_insert_rowid()").fetchone()[0]
            c.execute("INSERT INTO products(name,sale_price_cents,stock_qty) VALUES('Test',1000,1)")
            product_id=c.execute("SELECT last_insert_rowid()").fetchone()[0]
            c.execute("INSERT INTO sale_items(sale_id,product_id,name_snapshot,qty,unit_price_cents,line_total_cents,net_total_cents,pricing_mode,qty_multiplier) VALUES(?,?,'Test',1,1000,1000,1000,'UNIT',1)",(sale_id,product_id))
        payload=receipts.build_escpos_receipt(sale_id,cut=True,open_drawer=False)
        self.assertTrue(payload.startswith(bytes((27,64))))
        self.assertTrue(payload.endswith(bytes((29,86,0))))
        self.assertNotIn(bytes((27,112,0,50,250)),payload)
        database.set_setting('drawer_pin','1')
        payload=receipts.build_escpos_receipt(sale_id,cut=True,open_drawer=True)
        self.assertIn(bytes((27,112,1,50,250)),payload)

    def test_failed_write_aborts_and_closes(self):
        database.set_setting('drawer_enabled','1');database.set_setting('printer_name','Receipt Test')
        api=Mock();api.OpenPrinter.return_value=99;api.WritePrinter.return_value=2
        with patch.dict(sys.modules,win32print=api),patch.object(printers.os,'name','nt'):
            with self.assertRaises(OSError):printers.open_drawer()
        api.AbortPrinter.assert_called_once_with(99);api.ClosePrinter.assert_called_once_with(99)
