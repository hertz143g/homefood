"""Homefood VPS backend. No database or secret is created on the frontend host."""
from contextlib import contextmanager
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import ssl
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

TOKEN = os.environ.get('BOT_TOKEN', '')
OWNER = os.environ.get('OWNER_ID', '')
DATA = Path(os.environ.get('DATA_DIR', '/var/lib/homefood'))
APP_URL = os.environ.get('APP_URL', 'https://homefood-ten.vercel.app')
MAX_BODY = 2 * 1024 * 1024

class Error(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status

def verify_init(raw, token=TOKEN, now=None):
    pairs = urllib.parse.parse_qsl(raw, keep_blank_values=True, strict_parsing=True)
    values = dict(pairs)
    if len(values) != len(pairs): raise Error('Некорректный вход', 401)
    supplied = values.pop('hash', '')
    key = hmac.new(b'WebAppData', token.encode(), hashlib.sha256).digest()
    expected = hmac.new(key, '\n'.join(f'{k}={v}' for k, v in sorted(values.items())).encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(supplied, expected): raise Error('Откройте приложение через Telegram.', 401)
    age = (time.time() if now is None else now) - int(values.get('auth_date', 0))
    if not -60 <= age <= 86400: raise Error('Откройте приложение заново через бота.', 401)
    user = json.loads(values.get('user', '{}'))
    if type(user.get('id')) is not int or user['id'] <= 0: raise Error('Не найден аккаунт Telegram', 401)
    return str(user['id'])

def digest(value): return hashlib.sha256(value.encode()).hexdigest()
@contextmanager
def connect():
    c = sqlite3.connect(DATA / 'homefood.sqlite', timeout=15)
    c.row_factory = sqlite3.Row
    try:
        with c:yield c
    finally:c.close()

def initialize():
    DATA.mkdir(mode=0o700, parents=True, exist_ok=True)
    (DATA / 'photos').mkdir(mode=0o700, exist_ok=True)
    with connect() as c:
        c.executescript('''PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS records(kind TEXT NOT NULL,id TEXT NOT NULL,payload TEXT NOT NULL,version INTEGER NOT NULL DEFAULT 1,PRIMARY KEY(kind,id));
        CREATE TABLE IF NOT EXISTS members(user_id TEXT PRIMARY KEY,slot TEXT NOT NULL UNIQUE);
        CREATE TABLE IF NOT EXISTS sessions(hash TEXT PRIMARY KEY,user_id TEXT NOT NULL,expires INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS invites(hash TEXT PRIMARY KEY,expires INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS photos(id TEXT PRIMARY KEY,mime TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);''')
        home={'name':'Наш дом','members':[{'id':'first','name':'Я','notes':''},{'id':'second','name':'Партнёр','notes':''}],'categories':['Завтрак','Обед','Ужин','Перекус','Десерт'],'onboarded':True}
        c.execute('INSERT OR IGNORE INTO records(kind,id,payload) VALUES(?,?,?)', ('home','home',json.dumps(home,ensure_ascii=False)))
        if OWNER: c.execute('INSERT OR IGNORE INTO members VALUES(?,?)',(OWNER,'first'))

def text(value, limit=200, required=False):
    if not isinstance(value,str) or len(value)>limit or (required and not value.strip()): raise Error('Проверьте заполненные поля')
    return value

def validate(kind,v):
    if not isinstance(v,dict): raise Error('Некорректная запись')
    v=dict(v)
    if kind=='home':
        text(v.get('name'),150,True)
        members=v.get('members',[])
        if len(members)!=2 or [m.get('id') for m in members]!=['first','second']: raise Error('Некорректные участники')
        for m in members: text(m.get('name'),80,True);text(m.get('notes'),1000)
        if not isinstance(v.get('categories'),list) or len(v['categories'])>50: raise Error('Слишком много категорий')
        for cat in v['categories']:text(cat,80,True)
    elif kind=='dish':
        text(v.get('id'),100,True);text(v.get('name'),200,True);text(v.get('symbol'),40,True);text(v.get('category'),80,True);text(v.get('notes'),10000)
        for k,maxval in [('cookingTime',360),('servings',24)]:
            if type(v.get(k)) is not int or not 0<=v[k]<=maxval: raise Error('Проверьте время и порции')
        if v['servings']<1:raise Error('Укажите число порций')
        for k in ['favorite','ingredientsAtHome','light','noCooking']:
            if type(v.get(k)) is not bool: raise Error('Некорректная отметка')
        text(v.get('difficulty'),80);text(v.get('createdAt'),40,True)
        if v.get('lastCookedAt'):text(v['lastCookedAt'],40,True)
        for key,maximum in [('ingredients',100),('variations',50),('cookedDates',2000)]:
            if not isinstance(v.get(key),list) or len(v[key])>maximum: raise Error('Слишком много строк')
        for i in v['ingredients']:
            text(i.get('id'),100,True);text(i.get('name'),250,True);text(i.get('amount'),100);text(i.get('unit'),50)
            if type(i.get('available')) is not bool:raise Error('Некорректная отметка ингредиента')
        for x in v['variations']:text(x,500)
        for x in v['cookedDates']:text(x,40,True)
        if v.get('photo'):
            path=urllib.parse.urlsplit(v['photo']).path
            if not re.fullmatch(r'/api/backend/photos/[a-f0-9]{32}',path):raise Error('Сначала загрузите фотографию')
            v['photo']=path
    elif kind=='plan':
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',v.get('date','')) or v.get('meal') not in ['Завтрак','Обед','Ужин']:raise Error('Некорректная дата')
        if v.get('id')!=v['date']+'-'+v['meal']:raise Error('Некорректный план')
        text(v.get('dishId'),100,True)
    elif kind=='preference':
        text(v.get('dishId'),100,True)
        if v.get('userId') not in ['first','second'] or v.get('status') not in ['Люблю','Нейтрально','Не люблю'] or v.get('id')!=v['userId']+'-'+v['dishId']:raise Error('Некорректная отметка')
    else:raise Error('Неизвестный тип записи')
    return v

def sign_photo(path):
    expires=str(int(time.time())+3600)
    signature=hmac.new(TOKEN.encode(),(path+'\n'+expires).encode(),hashlib.sha256).hexdigest()
    return path+'?expires='+expires+'&signature='+signature

def owner_id(c):
    row=c.execute("SELECT user_id FROM members WHERE slot='first'").fetchone()
    return row['user_id'] if row else ''

def claim_owner(c,user,raw):
    c.execute('BEGIN IMMEDIATE')
    row=c.execute("SELECT value FROM metadata WHERE key='bootstrap_hash'").fetchone()
    expiry=c.execute("SELECT value FROM metadata WHERE key='bootstrap_expires'").fetchone()
    if owner_id(c) or not row or not expiry or int(expiry['value'])<time.time() or not hmac.compare_digest(row['value'],digest(raw)):
        raise Error('Ссылка настройки уже использована или недействительна.',403)
    c.execute("INSERT INTO members VALUES(?,'first')",(user,))
    c.execute("DELETE FROM metadata WHERE key IN ('bootstrap_hash','bootstrap_expires')")

def state(c,user):
    result={'dishes':[],'plans':[],'preferences':[]}
    for row in c.execute('SELECT * FROM records'):
        value=json.loads(row['payload']);value['version']=row['version']
        if value.get('photo'):value['photo']=sign_photo(value['photo'])
        if row['kind']=='home':result['home']=value
        else:result[{'dish':'dishes','plan':'plans','preference':'preferences'}[row['kind']]].append(value)
    result['member']=c.execute('SELECT slot FROM members WHERE user_id=?',(user,)).fetchone()['slot']
    result['partnerConnected']=c.execute("SELECT 1 FROM members WHERE slot='second'").fetchone() is not None
    return result

def save(c,kind,v):
    v=validate(kind,v);version=v.pop('version',None);record_id='home' if kind=='home' else v['id']
    if kind in ['plan','preference'] and not c.execute("SELECT 1 FROM records WHERE kind='dish' AND id=?",(v['dishId'],)).fetchone():raise Error('Блюдо уже удалено',409)
    if kind=='dish' and v.get('photo') and not c.execute('SELECT 1 FROM photos WHERE id=?',(v['photo'].rsplit('/',1)[1],)).fetchone():raise Error('Фото не найдено')
    payload=json.dumps(v,ensure_ascii=False)
    if len(payload)>150000:raise Error('Слишком большая запись')
    old=c.execute('SELECT version FROM records WHERE kind=? AND id=?',(kind,record_id)).fetchone()
    if old:
        if version!=old['version']:raise Error('Запись изменена на другом телефоне. Откройте её заново, чтобы увидеть изменения.',409)
        c.execute('UPDATE records SET payload=?,version=version+1 WHERE kind=? AND id=?',(payload,kind,record_id))
    else:
        if version is not None:raise Error('Запись уже удалена. Обновите меню.',409)
        if c.execute('SELECT count(*) FROM records').fetchone()[0]>=5000:raise Error('Достигнут предел записей')
        c.execute('INSERT INTO records(kind,id,payload) VALUES(?,?,?)',(kind,record_id,payload))

def join(c,user,raw):
    c.execute('BEGIN IMMEDIATE')
    if c.execute('SELECT 1 FROM members WHERE user_id=?',(user,)).fetchone():return
    if c.execute("SELECT 1 FROM members WHERE slot='second'").fetchone():raise Error('В доме уже два участника',403)
    item=c.execute('SELECT 1 FROM invites WHERE hash=? AND expires>?',(digest(raw),time.time())).fetchone()
    if not item:raise Error('Приглашение устарело или использовано',403)
    c.execute("INSERT INTO members VALUES(?,'second')",(user,));c.execute('DELETE FROM invites')

class Handler(BaseHTTPRequestHandler):
    server_version='Homefood'
    def log_message(self,*args):pass # Do not log authorization or photo tickets.
    def setup(self):super().setup();self.connection.settimeout(20)
    def respond(self,value,status=200,mime='application/json'):
        body=value if isinstance(value,bytes) else json.dumps(value,ensure_ascii=False).encode()
        self.send_response(status);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(body)
    def user(self,c):
        header=self.headers.get('Authorization','')
        if not header.startswith('Bearer '):raise Error('Откройте приложение через Telegram.',401)
        row=c.execute('SELECT s.user_id FROM sessions s JOIN members m ON m.user_id=s.user_id WHERE s.hash=? AND s.expires>?',(digest(header[7:]),time.time())).fetchone()
        if not row:raise Error('Вход устарел. Откройте приложение заново.',401)
        return row['user_id']
    def body(self):
        size=int(self.headers.get('Content-Length','0'))
        if not 0<size<=MAX_BODY:raise Error('Слишком большой запрос',413)
        return json.loads(self.rfile.read(size))
    def do_GET(self):self.handle_request('GET')
    def do_POST(self):self.handle_request('POST')
    def handle_request(self,method):
        try:
            url=urllib.parse.urlsplit(self.path);path=url.path
            if method=='GET' and path=='/health':return self.respond({'ok':True})
            if method=='GET' and re.fullmatch(r'/photos/[a-f0-9]{32}',path):
                params=urllib.parse.parse_qs(url.query);expires=params.get('expires',[''])[0];signature=params.get('signature',[''])[0]
                wanted=hmac.new(TOKEN.encode(),('/api/backend'+path+'\n'+expires).encode(),hashlib.sha256).hexdigest()
                if not hmac.compare_digest(signature,wanted) or not expires.isdigit() or int(expires)<time.time():raise Error('Фото недоступно',403)
                file=DATA/'photos'/path.rsplit('/',1)[1]
                if not file.is_file():raise Error('Фото не найдено',404)
                return self.respond(file.read_bytes(),mime='image/jpeg')
            with connect() as c:
                if method=='POST' and path=='/session':
                    if not owner_id(c):raise Error('Владелец дома ещё не подключён.',503)
                    body=self.body();user=verify_init(text(body.get('initData'),20000,True))
                    if not c.execute('SELECT 1 FROM members WHERE user_id=?',(user,)).fetchone():raise Error('Попросите владельца прислать приглашение в дом.',403)
                    raw=secrets.token_urlsafe(32)
                    c.execute('DELETE FROM sessions WHERE user_id=? AND hash NOT IN (SELECT hash FROM sessions WHERE user_id=? ORDER BY expires DESC LIMIT 20)',(user,user))
                    c.execute('DELETE FROM sessions WHERE expires<?',(time.time(),));c.execute('INSERT INTO sessions VALUES(?,?,?)',(digest(raw),user,int(time.time())+30*86400))
                    return self.respond({'token':raw,**state(c,user)})
                user=self.user(c)
                if method=='GET' and path=='/state':return self.respond(state(c,user))
                if method!='POST':raise Error('Не найдено',404)
                body=self.body()
                if path=='/invite':
                    if user!=owner_id(c):raise Error('Приглашение создаёт владелец дома',403)
                    if c.execute("SELECT 1 FROM members WHERE slot='second'").fetchone():raise Error('Партнёр уже подключён')
                    raw=secrets.token_urlsafe(24);c.execute('DELETE FROM invites');c.execute('INSERT INTO invites VALUES(?,?)',(digest(raw),int(time.time())+7*86400))
                    return self.respond({'url':'https://t.me/homefoodzavbot?start=join_'+raw})
                if path=='/photos':
                    encoded=text(body.get('data'),1900000,True)
                    if not encoded.startswith('data:image/jpeg;base64,'):raise Error('Требуется JPEG')
                    raw=base64.b64decode(encoded.split(',',1)[1],validate=True)
                    if not raw.startswith(b'\xff\xd8\xff') or len(raw)>1400000:raise Error('Фото слишком большое или повреждено')
                    if c.execute('SELECT count(*) FROM photos').fetchone()[0]>=2000:raise Error('Достигнут предел фотографий')
                    record_id=secrets.token_hex(16);file=DATA/'photos'/record_id
                    file.write_bytes(raw);c.execute('INSERT INTO photos VALUES(?,?)',(record_id,'image/jpeg'))
                    return self.respond({'photo':'/api/backend/photos/'+record_id})
                if path!='/mutate':raise Error('Не найдено',404)
                c.execute('BEGIN IMMEDIATE')
                action=body.get('action');kind=body.get('kind')
                if action=='save':save(c,kind,body.get('value'))
                elif action=='delete':
                    if kind not in ['dish','plan']:raise Error('Некорректное действие')
                    record_id=text(body.get('id'),100,True)
                    c.execute('DELETE FROM records WHERE kind=? AND id=?',(kind,record_id))
                    if kind=='dish':c.execute("DELETE FROM records WHERE kind IN ('plan','preference') AND json_extract(payload,'$.dishId')=?",(record_id,))
                elif action=='movePlan':
                    source=body['source'];target=body['target']
                    if source['id']!=target['id']:
                        old=c.execute("SELECT * FROM records WHERE kind='plan' AND id=?",(source['id'],)).fetchone()
                        if not old or old['version']!=source.get('version') or json.loads(old['payload'])['dishId']!=target['dishId']:raise Error('План изменился. Повторите перенос.',409)
                        save(c,'plan',target);c.execute("DELETE FROM records WHERE kind='plan' AND id=?",(source['id'],))
                else:raise Error('Неизвестное действие')
                response=state(c,user)
            return self.respond(response)
        except Error as e:self.respond({'error':str(e)},e.status)
        except (ValueError,KeyError,TypeError,AttributeError):self.respond({'error':'Проверьте данные запроса'},400)
        except (BrokenPipeError,ConnectionResetError,TimeoutError):pass
        except Exception as e:
            print('Request failed:',type(e).__name__,flush=True)
            self.respond({'error':'Не удалось сохранить. Попробуйте ещё раз.'},500)

def bot_call(method,payload):
    req=urllib.request.Request('https://api.telegram.org/bot'+TOKEN+'/'+method,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    result=json.load(urllib.request.urlopen(req,timeout=40))
    if not result.get('ok'):raise RuntimeError('Telegram API error')
    return result['result']

def poll_bot():
    while True:
        try:
            with connect() as c:
                row=c.execute("SELECT value FROM metadata WHERE key='offset'").fetchone();offset=int(row['value']) if row else 0
            updates=bot_call('getUpdates',{'offset':offset,'timeout':25,'allowed_updates':['message']})
            for update in updates:
                msg=update.get('message',{});user=str(msg.get('from',{}).get('id',''));content=msg.get('text','')
                if msg.get('chat',{}).get('type')=='private' and content.startswith('/start'):
                    try:
                        with connect() as c:
                            if content.startswith('/start owner_'):claim_owner(c,user,content.split('owner_',1)[1])
                            elif content.startswith('/start join_'):join(c,user,content.split('join_',1)[1])
                        with connect() as c:allowed=c.execute('SELECT 1 FROM members WHERE user_id=?',(user,)).fetchone()
                        text_reply='Ваше домашнее меню — по кнопке ниже.' if allowed else 'Это личное меню. Попросите владельца прислать приглашение.'
                        payload={'chat_id':msg['chat']['id'],'text':text_reply}
                        if allowed:payload['reply_markup']={'inline_keyboard':[[{'text':'Открыть меню','web_app':{'url':APP_URL}}]]}
                        bot_call('sendMessage',payload)
                    except Error as e:bot_call('sendMessage',{'chat_id':msg['chat']['id'],'text':str(e)})
                with connect() as c:c.execute("INSERT OR REPLACE INTO metadata VALUES('offset',?)",(str(update['update_id']+1),))
        except Exception as e:
            print('Bot retry:',type(e).__name__,flush=True);time.sleep(5)

if __name__=='__main__':
    if not TOKEN:raise SystemExit('BOT_TOKEN is required')
    initialize()
    server=ThreadingHTTPServer(('0.0.0.0',8443),Handler)
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.minimum_version=ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(os.environ['TLS_CERT'],os.environ['TLS_KEY']);server.socket=context.wrap_socket(server.socket,server_side=True)
    threading.Thread(target=poll_bot,daemon=True).start()
    print('Homefood listening on 8443',flush=True);server.serve_forever()
