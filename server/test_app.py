"""Tests use only an in-memory SQLite database and throwaway photo directories."""
import hashlib,hmac,json,sqlite3,sys,tempfile,time,unittest,urllib.parse
from contextlib import contextmanager
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import app

class BackendTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.c=sqlite3.connect(':memory:');self.c.row_factory=sqlite3.Row
        self.original=(app.connect,app.DATA,app.OWNER)
        @contextmanager
        def memory():
            with self.c:yield self.c
        app.connect=memory;app.DATA=Path(self.temp.name);app.OWNER='100';app.initialize()
    def tearDown(self):
        app.connect,app.DATA,app.OWNER=self.original;self.c.close();self.temp.cleanup()
    def signed(self,when=1000,user=100):
        values={'auth_date':str(when),'user':json.dumps({'id':user}),'query_id':'test'}
        key=hmac.new(b'WebAppData',b'test-token',hashlib.sha256).digest()
        values['hash']=hmac.new(key,'\n'.join(f'{k}={v}' for k,v in sorted(values.items())).encode(),hashlib.sha256).hexdigest()
        return urllib.parse.urlencode(values)
    def test_auth(self):
        self.assertEqual(app.verify_init(self.signed(),token='test-token',now=1010),'100')
        for value,now in [(self.signed()+'x',1010),(self.signed(),100000),(self.signed(2000),1000),(self.signed()+'&user=bad',1010)]:
            with self.assertRaises(app.Error):app.verify_init(value,token='test-token',now=now)
    def dish(self):
        return {'id':'a','name':'Паста','symbol':'🍝','category':'Ужин','notes':'','cookingTime':20,'servings':2,'favorite':False,'ingredientsAtHome':False,'light':False,'noCooking':False,'difficulty':'Просто','createdAt':'2026-09-22T00:00:00Z','ingredients':[],'variations':[],'cookedDates':[]}
    def test_owner_bootstrap(self):
        with app.connect() as c:
            c.execute('DELETE FROM members');c.execute("INSERT INTO metadata VALUES('bootstrap_hash',?)",(app.digest('private-code'),));c.execute("INSERT INTO metadata VALUES('bootstrap_expires',?)",(str(int(time.time())+100),))
        with self.assertRaises(app.Error):
            with app.connect() as c:app.claim_owner(c,'999','wrong-code')
        with app.connect() as c:app.claim_owner(c,'100','private-code')
        with self.assertRaises(app.Error):
            with app.connect() as c:app.claim_owner(c,'999','private-code')
        with app.connect() as c:self.assertEqual(app.owner_id(c),'100')
    def test_conflicts_and_state(self):
        with app.connect() as c:app.save(c,'dish',self.dish())
        with self.assertRaises(app.Error):
            with app.connect() as c:app.save(c,'dish',self.dish())
        with app.connect() as c:
            updated={**self.dish(),'version':1,'name':'Другая паста'};app.save(c,'dish',updated)
        with self.assertRaises(app.Error):
            with app.connect() as c:app.save(c,'dish',updated)
        with app.connect() as c:self.assertEqual(app.state(c,'100')['dishes'][0]['name'],'Другая паста')
    def test_invite_is_single_use_and_capacity_two(self):
        with app.connect() as c:c.execute('INSERT INTO invites VALUES(?,?)',(app.digest('invite'),time.time()+100))
        with app.connect() as c:app.join(c,'200','invite')
        with self.assertRaises(app.Error):
            with app.connect() as c:app.join(c,'300','invite')
        self.assertEqual(self.c.execute('SELECT count(*) FROM members').fetchone()[0],2)
        self.assertEqual(self.c.execute('SELECT count(*) FROM invites').fetchone()[0],0)
    def test_transaction_rollback_and_photo_restrictions(self):
        with self.assertRaises(app.Error):
            with app.connect() as c:
                c.execute('BEGIN IMMEDIATE');app.save(c,'dish',self.dish());app.save(c,'dish',self.dish())
        self.assertEqual(self.c.execute("SELECT count(*) FROM records WHERE kind='dish'").fetchone()[0],0)
        with self.assertRaises(app.Error):app.validate('dish',{**self.dish(),'photo':'https://evil.test/image'})
        with self.assertRaises(app.Error):
            with app.connect() as c:app.save(c,'plan',{'id':'2026-09-22-Ужин','date':'2026-09-22','meal':'Ужин','dishId':'missing'})

if __name__=='__main__':unittest.main()
