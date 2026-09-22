"""Tests use only an in-memory SQLite database and throwaway photo directories."""
import hashlib,hmac,json,sqlite3,sys,tempfile,time,unittest,urllib.parse,urllib.request,urllib.error,threading
from contextlib import contextmanager
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import app

class BackendTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.c=sqlite3.connect(':memory:',check_same_thread=False);self.c.row_factory=sqlite3.Row
        self.original=(app.connect,app.DATA,app.OWNER,app.TOKEN);self.lock=threading.RLock();app.TOKEN='test-token'
        @contextmanager
        def memory():
            with self.lock,self.c:yield self.c
        app.connect=memory;app.DATA=Path(self.temp.name);app.OWNER='100';app.initialize()
    def tearDown(self):
        app.connect,app.DATA,app.OWNER,app.TOKEN=self.original;self.c.close();self.temp.cleanup()
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
    def test_http_auth_and_persistence(self):
        from http.server import ThreadingHTTPServer
        server=ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base=f'http://127.0.0.1:{server.server_port}';token=''
        def request(path,body=None):
            headers={'Content-Type':'application/json'}
            if token:headers['Authorization']='Bearer '+token
            req=urllib.request.Request(base+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
            try:
                with urllib.request.urlopen(req) as r:return r.status,json.load(r)
            except urllib.error.HTTPError as e:
                with e:return e.code,json.load(e)
        try:
            self.assertEqual(request('/state')[0],401)
            self.assertEqual(request('/session',{'initData':self.signed(int(time.time()),999)})[1]['needsHome'],True)
            code,session=request('/session',{'initData':self.signed(int(time.time()))});self.assertEqual(code,200);token=session['token']
            self.assertEqual(request('/mutate',{'action':'save','kind':'dish','value':self.dish()})[0],200)
            self.assertEqual(request('/state')[1]['dishes'][0]['name'],'Паста')
            self.assertEqual(request('/mutate',{'action':'save','kind':'dish','value':self.dish()})[0],409)
            self.assertEqual(request('/invite',{})[0],200)
            plan={'id':'2026-09-22-Ужин','date':'2026-09-22','meal':'Ужин','dishId':'a'}
            self.assertEqual(request('/mutate',{'action':'save','kind':'plan','value':plan})[0],200)
            source=request('/state')[1]['plans'][0];target={**plan,'id':'2026-09-23-Обед','date':'2026-09-23','meal':'Обед'}
            self.assertEqual(request('/mutate',{'action':'movePlan','source':source,'target':target})[0],200)
            self.assertEqual(request('/state')[1]['plans'][0]['id'],target['id'])
            self.assertEqual(request('/mutate',{'action':'movePlan','source':source,'target':target})[0],409)
            owner_token=token
            code,new=request('/session',{'initData':self.signed(int(time.time()),999)})
            self.assertEqual(code,200);self.assertTrue(new['needsHome']);token=new['token']
            self.assertEqual(request('/mutate',{'action':'delete','kind':'dish','id':'a'})[0],403)
            self.assertEqual(request('/homes',{})[0],200)
            self.assertEqual(request('/state')[1]['dishes'],[])
            self.assertEqual(request('/mutate',{'action':'save','kind':'dish','value':{**self.dish(),'name':'Суп'}})[0],200)
            self.assertEqual(request('/mutate',{'action':'delete','kind':'dish','id':'a'})[0],200)
            token=owner_token
            self.assertEqual(request('/state')[1]['dishes'][0]['name'],'Паста')
            self.assertEqual(len(request('/state')[1]['plans']),1)

        finally:server.shutdown();server.server_close();thread.join()
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
        with app.connect() as c:c.execute("INSERT INTO invites VALUES(?,'legacy',?)",(app.digest('invite'),time.time()+100))
        with app.connect() as c:app.join(c,'200','invite')
        with self.assertRaises(app.Error):
            with app.connect() as c:app.join(c,'300','invite')
        self.assertEqual(self.c.execute('SELECT count(*) FROM members').fetchone()[0],2)
        self.assertEqual(self.c.execute('SELECT count(*) FROM invites').fetchone()[0],0)
    def test_household_isolation(self):
        with app.connect() as c:
            app.create_home(c,'300','other')
            app.save(c,'dish',self.dish())
            app.save(c,'dish',{**self.dish(),'name':'Суп'},'other')
            c.execute("INSERT INTO photos VALUES(?,'legacy','image/jpeg')",('a'*32,))
            c.execute("INSERT INTO invites VALUES(?,'other',?)",(app.digest('other-invite'),time.time()+100))
            c.execute("INSERT INTO invites VALUES(?,'legacy',?)",(app.digest('ours'),time.time()+100))
        with self.assertRaises(app.Error):
            with app.connect() as c:app.save(c,'dish',{**self.dish(),'version':1,'photo':'/api/backend/photos/'+'a'*32},'other')
        with self.assertRaises(app.Error):
            with app.connect() as c:app.join(c,'100','other-invite')
        with app.connect() as c:app.join(c,'400','other-invite')
        with app.connect() as c:
            self.assertEqual(app.state(c,'100')['dishes'][0]['name'],'Паста')
            self.assertEqual(app.state(c,'400')['dishes'][0]['name'],'Суп')
            self.assertFalse(app.state(c,'100')['partnerConnected'])
            self.assertTrue(app.state(c,'300')['partnerConnected'])
            self.assertEqual(c.execute('SELECT count(*) FROM invites').fetchone()[0],1)
            app.create_home(c,'100')
            self.assertEqual(c.execute('SELECT count(*) FROM homes').fetchone()[0],2)
        app.initialize()
        with app.connect() as c:self.assertEqual(app.state(c,'100')['dishes'][0]['name'],'Паста')

    def test_legacy_migration(self):
        with app.connect() as c:
            for table in ['records','members','invites','photos','homes']:c.execute('DROP TABLE '+table)
            c.execute('CREATE TABLE records(kind TEXT,id TEXT,payload TEXT,version INTEGER,PRIMARY KEY(kind,id))')
            c.execute('CREATE TABLE members(user_id TEXT PRIMARY KEY,slot TEXT UNIQUE)')
            c.execute('CREATE TABLE invites(hash TEXT PRIMARY KEY,expires INTEGER)')
            c.execute('CREATE TABLE photos(id TEXT PRIMARY KEY,mime TEXT)')
            c.execute("INSERT INTO records VALUES('home','home',?,7)",(json.dumps(app.default_home()),))
            c.execute("INSERT INTO records VALUES('dish','a',?,3)",(json.dumps(self.dish()),))
            c.execute("INSERT INTO members VALUES('100','first')")
            c.execute("INSERT INTO members VALUES('200','second')")
            c.execute("INSERT INTO sessions VALUES('session','100',9999999999)")
            c.execute("INSERT INTO photos VALUES('photo','image/jpeg')")
            c.execute("INSERT INTO invites VALUES('invite',9999999999)")
        app.initialize();app.initialize()
        with app.connect() as c:
            result=app.state(c,'100')
            self.assertEqual(result['home']['version'],7)
            self.assertEqual(result['dishes'][0]['version'],3)
            self.assertTrue(result['partnerConnected'])
            self.assertEqual(c.execute('SELECT home_id FROM photos').fetchone()[0],'legacy')
            self.assertEqual(c.execute('SELECT home_id FROM invites').fetchone()[0],'legacy')
            self.assertEqual(c.execute('SELECT user_id FROM sessions').fetchone()[0],'100')

    def test_transaction_rollback_and_photo_restrictions(self):
        with self.assertRaises(app.Error):
            with app.connect() as c:
                c.execute('BEGIN IMMEDIATE');app.save(c,'dish',self.dish());app.save(c,'dish',self.dish())
        self.assertEqual(self.c.execute("SELECT count(*) FROM records WHERE kind='dish'").fetchone()[0],0)
        with self.assertRaises(app.Error):app.validate('dish',{**self.dish(),'photo':'https://evil.test/image'})
        with self.assertRaises(app.Error):
            with app.connect() as c:app.save(c,'plan',{'id':'2026-09-22-Ужин','date':'2026-09-22','meal':'Ужин','dishId':'missing'})

if __name__=='__main__':unittest.main()
