"""Financial chart regressions using real sale/return services."""
import sys,tempfile,unittest,datetime
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'todo'))
import database
from services.bootstrap import ensure_defaults
from services.security import current_user
from services.cash import open_session
from services.sales import complete_sale,create_return
from services.reports import today_summary,period_summary,sales_evolution,top_products,top_cashiers,category_breakdown

class StatisticsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.old=database.DB_PATH
        database.DB_PATH=Path(self.tmp.name)/'stats.db';database.init_db();ensure_defaults()
        with database.connect() as c:
            self.uid=c.execute('SELECT id FROM users').fetchone()[0]
            self.cat=c.execute("INSERT INTO categories(name) VALUES('Test family')").lastrowid
            self.pid=c.execute("INSERT INTO products(name,category_id,sale_price_cents,purchase_price_cents) VALUES('Test rice',?,1500,800)",(self.cat,)).lastrowid
        self.token=current_user.set(self.uid);self.session=open_session(self.uid,0)
    def tearDown(self):
        current_user.reset(self.token);database.DB_PATH=self.old;self.tmp.cleanup()
    def sell(self):
        sale=complete_sale(self.session,self.uid,[dict(product_id=self.pid,qty=2,unit_price_cents=1500)],'CASH',2500,discount_cents=500)
        with database.connect() as c:self.item=c.execute('SELECT id FROM sale_items WHERE sale_id=?',(sale['id'],)).fetchone()[0]
        return sale
    def assert_revenue(self,amount,period='month'):
        self.assertEqual(period_summary(period)['net_sales'],amount)
        self.assertEqual(sum(sales_evolution(period)[1]),amount)
        self.assertEqual(top_products(period=period)[0]['revenue'],amount)
        self.assertEqual(top_cashiers(period)[0]['revenue'],amount)
        self.assertEqual(category_breakdown(period)[0]['revenue'],amount)
    def test_empty_windows_month_and_all_periods(self):
        for period in ['week','month','year']:
            labels,values=sales_evolution(period)
            self.assertEqual(len(labels),len(values));self.assertEqual(sum(values),0)
            self.assertEqual(period_summary(period)['tickets'],0)
        self.assertEqual(len(sales_evolution('month')[0]),datetime.date.today().day)
    def test_discount_and_partial_return_consistent_everywhere(self):
        sale=self.sell();self.assert_revenue(2500)
        self.assertEqual(period_summary()['gross_margin'],900)
        create_return(sale['id'],self.session,self.uid,[(self.item,1)])
        for period in ['week','month','year']:self.assert_revenue(1250,period)
        self.assertEqual(period_summary()['gross_margin'],450)
        self.assertEqual(today_summary()['net_sales'],1250)
    def test_return_recognized_today_for_old_sale(self):
        sale=self.sell()
        with database.connect() as c:c.execute("UPDATE sales SET created_at='2000-01-01 12:00:00' WHERE id=?",(sale['id'],))
        create_return(sale['id'],self.session,self.uid,[(self.item,1)])
        self.assert_revenue(-1250)
        self.assertEqual(period_summary()['tickets'],0)
        self.assertEqual(period_summary()['gross_margin'],-450)
    def test_multiple_families_do_not_duplicate_revenue(self):
        from services.catalog import set_product_categories
        with database.connect() as c:
            other=c.execute("INSERT INTO categories(name) VALUES('Second family')").lastrowid
            set_product_categories(c,self.pid,[self.cat,other])
        self.sell()
        self.assertEqual(sum(r['revenue'] for r in category_breakdown()),2500)
