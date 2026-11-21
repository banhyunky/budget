# 머니로그 웹훅(Code.gs) 로직 테스트 — QuickJS 위에서 GAS 기본 객체를 흉내 낸다.
# · 문자/알림 해석(parseMessage)
# · 문자+알림 중복 제거, 부부 이체 짝 맞추기
# · Firestore REST 로 보내는 PATCH 본문 모양(기존 기록 원본 보존 포함)
#
# 실행: python3 test/webhook_test.py
import json, os, sys, datetime
import quickjs

HERE = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.join(HERE, '..', 'Code.gs')
src = open(CODE, encoding='utf-8').read()

STUB = r'''
var __store = { doc: null, patches: [], gets: 0, fail409: 0, logs: [] };
var Logger = { log: function(m){ __store.logs.push(String(m)); } };
var ContentService = {
  MimeType: { JSON: 'application/json' },
  createTextOutput: function(s){
    var o = { _s: String(s) };
    o.setMimeType = function(){ return o; };
    o.getContent = function(){ return o._s; };
    return o;
  }
};
var LockService = {
  getScriptLock: function(){ return { tryLock: function(){ return true; }, releaseLock: function(){} }; }
};
function __resp(code, body){
  return { getResponseCode: function(){ return code; }, getContentText: function(){ return body; } };
}
var UrlFetchApp = {
  fetch: function(url, params){
    params = params || {};
    var method = String(params.method || 'get').toLowerCase();
    if (method === 'get'){ __store.gets++; return __resp(200, JSON.stringify(__store.doc)); }
    if (__store.fail409 > 0){ __store.fail409--; return __resp(409, '{"error":{"status":"FAILED_PRECONDITION"}}'); }
    var body = JSON.parse(params.payload);
    __store.patches.push({ url: url, body: body });
    __store.doc.fields.data = body.fields.data;
    __store.doc.fields.updatedAt = body.fields.updatedAt;
    __store.doc.updateTime = '2026-11-21T03:00:00.000001Z';
    return __resp(200, JSON.stringify(__store.doc));
  }
};
'''

ctx = quickjs.Context()
ctx.eval(STUB)
ctx.eval(src)
ctx.eval("CFG.SECRET = 'test-secret';")

fails = []
def check(name, cond, detail=''):
    if cond:
        print('  OK   ' + name)
    else:
        print('  FAIL ' + name + ('  ' + detail if detail else ''))
        fails.append(name)

def jstr(s):
    return json.dumps(s, ensure_ascii=False)

def patch_count():
    return ctx.eval('__store.patches.length')

def post(payload, urlencoded=False):
    if urlencoded:
        body = '&'.join('%s=%s' % (k, str(v)) for k, v in payload.items())
    else:
        body = json.dumps(payload, ensure_ascii=False)
    expr = 'doPost({postData:{contents:%s}}).getContent()' % jstr(body)
    return json.loads(ctx.eval(expr))

def reset(txns=None, fail409=0):
    doc = {
        'name': 'projects/banhyunky-budget/databases/(default)/documents/households/hy-vtrxxa8dq6',
        'fields': {
            'pin': {'stringValue': '6591'},
            'updatedAt': {'integerValue': '1795229502305'},
            'data': {'mapValue': {'fields': {
                'v': {'integerValue': '1'},
                'viewMonth': {'stringValue': '2026-11'},
                'txns': {'arrayValue': {'values': txns or []}},
                'settings': {'mapValue': {'fields': {
                    'currentUser': {'stringValue': '현기'},
                    'houseId': {'stringValue': 'hy-vtrxxa8dq6'},
                    'autoConnect': {'booleanValue': True},
                }}},
                'bills': {'arrayValue': {'values': [{'mapValue': {'fields': {
                    'id': {'stringValue': 'b1'}, 'name': {'stringValue': '실손보험'},
                    'cat': {'stringValue': '보험'}, 'amount': {'integerValue': '92000'},
                }}}]}},
                'incomes': {'arrayValue': {'values': []}},
                'paid': {'mapValue': {'fields': {}}},
                'accounts': {'arrayValue': {'values': []}},
                'plan': {'mapValue': {'fields': {
                    'assets': {'integerValue': '0'}, 'loan': {'integerValue': '311195858'},
                    'saveGoal': {'integerValue': '0'},
                }}},
            }}},
        },
        'updateTime': '2026-11-21T02:30:00.000000Z',
    }
    ctx.eval('__store.doc = JSON.parse(%s); __store.patches = []; __store.fail409 = %d;'
             % (jstr(json.dumps(doc, ensure_ascii=False)), fail409))

def txns():
    """Firestore 문서에 실제로 들어간 txns 를 JS 객체로 되돌려 읽는다."""
    raw = json.loads(ctx.eval('JSON.stringify(__store.doc)'))
    return [dec(v) for v in raw['fields']['data']['mapValue']['fields']['txns']['arrayValue']['values']]

def dec(v):
    if 'stringValue' in v: return v['stringValue']
    if 'integerValue' in v: return int(v['integerValue'])
    if 'doubleValue' in v: return v['doubleValue']
    if 'booleanValue' in v: return v['booleanValue']
    if 'nullValue' in v: return None
    if 'timestampValue' in v: return {'__ts': v['timestampValue']}
    if 'arrayValue' in v: return [dec(x) for x in v['arrayValue'].get('values', [])]
    if 'mapValue' in v: return {k: dec(x) for k, x in v['mapValue'].get('fields', {}).items()}
    return v

TODAY = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y-%m-%d')
def at(hhmm, ss='00'):
    return '%s %s:%s' % (TODAY, hhmm, ss)

def payload(text, owner='현기', source='sms', title='', app='국민은행', atv=None):
    return {'secret': 'test-secret', 'owner': owner, 'source': source, 'app': app,
            'title': title, 'text': text, 'at': atv or at('12:00')}

# ---------------------------------------------------------------- 1. 해석
print('\n[1] 문자·알림 해석')
CASES = [
    ('[신한카드] 승인 14,800원 스타벅스 11/21 12:34', '현기', 'expense', 14800, '식비'),
    ('[KB국민카드] 11/21 12:34 승인 15,000원 이마트 1234', '현기', 'expense', 15000, '식비'),
    ('토스 1,000원을 보냈어요', '현기', 'expense', 1000, None),
    ('장미님에게 1,000원을 보냈어요', '현기', 'transfer', 1000, '이체'),
    ('반현기님이 1,000원을 보냈어요', '장미', 'transfer', 1000, '이체'),
    ('신한은행 11/21 12:34 1,000원 출금 장미 잔액 1,234,567원', '현기', 'transfer', 1000, '이체'),
    ('NH농협 1,000원 입금 반현기 잔액 123,456원', '장미', 'transfer', 1000, '이체'),
    ('삼성페이 5,000원 결제 스타벅스', '현기', 'expense', 5000, '식비'),
    ('자동이체 92,000원 출금 실손보험', '현기', 'expense', 92000, '보험'),
    ('카카오뱅크 1,000원 이체 장미 잔액 500,000원', '현기', 'transfer', 1000, '이체'),
    ('1,000원 출금 잔액 1,234,567원', '현기', 'expense', 1000, None),
    ('우리은행 11/21 1,000원 출금 잔액 10,000원', '현기', 'expense', 1000, None),
    ('월급 2,200,000원 입금', '현기', 'income', 2200000, '급여'),
    ('이자 1,234원 입금', '장미', 'income', 1234, '이자'),
]
for text, owner, kind, amount, cat in CASES:
    r = json.loads(ctx.eval('JSON.stringify(parseMessage(%s, %s))' % (jstr(text), jstr(owner))))
    ok = (not r.get('skip')) and r.get('kind') == kind and r.get('amount') == amount
    if cat: ok = ok and r.get('cat') == cat
    check('%s → %s %s' % (text[:34], kind, amount), ok, json.dumps(r, ensure_ascii=False))

for text, reason in [
    ('[현대카드] 승인취소 5,000원 스타벅스', 'cancel'),
    ('인증번호 [123456] 을 입력해 주세요', 'otp'),
    ('이번 달 혜택 5,000원 쿠폰이 도착했어요', 'ad'),
    ('오늘도 좋은 하루 되세요', 'no_amount'),
]:
    r = json.loads(ctx.eval('JSON.stringify(parseMessage(%s, %s))' % (jstr(text), jstr('현기'))))
    check('버림: %s → %s' % (text[:26], reason), r.get('skip') is True and r.get('reason') == reason,
          json.dumps(r, ensure_ascii=False))

# ---------------------------------------------------------------- 2. 인증
print('\n[2] 비밀값·요청 형식')
reset()
ctx.eval("__keep = CFG.SECRET; CFG.SECRET = 'CHANGE_ME_moneylog_2026';")
r0 = post({'secret': 'CHANGE_ME_moneylog_2026', 'owner': '현기', 'text': '승인 1,000원 스타벅스'})
check('기본 비밀값이면 아예 거부', r0.get('error') == 'secret_not_set', str(r0))
ctx.eval('CFG.SECRET = __keep;')
reset()
bad = post({'secret': 'wrong', 'owner': '현기', 'text': '승인 1,000원 스타벅스'})
check('비밀값이 다르면 거부', bad.get('ok') is False and bad.get('error') == 'bad_secret', str(bad))
check('거부 시 문서를 쓰지 않음', patch_count() == 0)
reset()
r = post({'secret': 'test-secret', 'owner': '현기', 'source': 'sms',
          'text': '승인 7,000원 스타벅스', 'at': at('12:01')}, urlencoded=True)
check('form-urlencoded 로 와도 처리', r.get('status') == 'added' and r.get('amount') == 7000, str(r))
reset()
raw = json.loads(ctx.eval('doGet({}).getContent()'))
check('doGet 은 살아있음만 알려줌(비밀값 없음)', raw.get('ok') is True and 'secret' not in json.dumps(raw))

# ---------------------------------------------------------------- 3. 추가·중복
print('\n[3] 기록 추가와 문자+알림 중복')
reset()
r1 = post(payload('[신한카드] 승인 14,800원 스타벅스', atv=at('12:00')))
r2 = post(payload('신한카드 승인 14,800원 스타벅스', source='push', app='신한카드', atv=at('12:01')))
check('첫 문자는 added', r1.get('status') == 'added', str(r1))
check('1분 뒤 같은 결제 알림은 duplicate', r2.get('status') == 'duplicate', str(r2))
check('실제로 한 건만 저장', len(txns()) == 1, str(len(txns())))
t = txns()[0]
check('저장된 날짜는 한국 날짜', t['date'] == TODAY, t.get('date'))
check('가맹점·분류 저장', t['memo'] == '스타벅스' and t['cat'] == '식비' and t['amount'] == 14800,
      json.dumps(t, ensure_ascii=False))
check('PATCH 는 data·updatedAt 만 갱신',
      'updateMask.fieldPaths=data&updateMask.fieldPaths=updatedAt' in
      json.loads(ctx.eval('JSON.stringify(__store.patches[0].url)')))
check('기존 고정비·설정은 그대로',
      txns() and json.loads(ctx.eval('JSON.stringify(__store.doc)'))['fields']['data']['mapValue']['fields']['bills']['arrayValue']['values'][0]['mapValue']['fields']['name']['stringValue'] == '실손보험')
check('updatedAt 은 숫자(ms)로 갱신',
      json.loads(ctx.eval('JSON.stringify(__store.doc)'))['fields']['updatedAt'].get('integerValue') is not None)

reset()
post(payload('승인 14,800원 스타벅스', atv=at('12:00')))
r = post(payload('승인 14,800원 스타벅스', atv=at('12:10')))
check('10분 뒤 같은 금액 카드 결제는 따로 기록', r.get('status') == 'added' and len(txns()) == 2,
      str(r))

# ---------------------------------------------------------------- 4. 부부 이체
print('\n[4] 부부 이체(장미↔현기)')
reset()
r1 = post(payload('토스 1,000원을 보냈어요', source='push', app='토스', atv=at('09:00')))
check('이름 없는 토스 알림은 우선 지출로', r1.get('kind') == 'expense', str(r1))
r2 = post(payload('장미님에게 1,000원을 보냈어요', source='push', app='토스', atv=at('09:01')))
check('1분 뒤 이름 있는 알림이 오면 이체로 정리', r2.get('status') == 'upgraded' and r2.get('kind') == 'transfer', str(r2))
check('행이 늘지 않음', len(txns()) == 1, str(len(txns())))
check('메모가 부부 이체로', txns()[0]['kind'] == 'transfer' and txns()[0]['memo'] == '현기 ↔ 장미',
      json.dumps(txns()[0], ensure_ascii=False))
r3 = post(payload('1,000원을 받았어요', owner='장미', source='push', app='토스', atv=at('09:02')))
check('장미 폰의 받은 알림은 새 줄을 만들지 않음', r3.get('status') == 'duplicate' and len(txns()) == 1, str(r3))

reset()
r1 = post(payload('신한은행 1,000원 출금 잔액 500,000원', atv=at('10:00')))
check('이름 없는 은행 출금은 지출', r1.get('kind') == 'expense', str(r1))
r2 = post(payload('신한은행 1,000원 입금 반현기 잔액 300,000원', owner='장미', atv=at('10:02')))
check('장미 폰 입금과 짝지어 한 줄로 정리', r2.get('status') == 'paired' and len(txns()) == 1, str(r2))
check('짝지은 기록은 transfer', txns()[0]['kind'] == 'transfer' and txns()[0]['amount'] == 1000,
      json.dumps(txns()[0], ensure_ascii=False))

reset()
post(payload('승인 30,000원 장미꽃집', atv=at('11:00')))
check('가맹점 이름에 장미가 있어도 이체 아님', txns()[0]['kind'] == 'expense', json.dumps(txns()[0], ensure_ascii=False))
post(payload('30,000원 입금', owner='장미', atv=at('11:05')))
check('카드 승인과 입금은 짝짓지 않음', len(txns()) == 2 and txns()[0]['kind'] == 'expense',
      json.dumps(txns(), ensure_ascii=False))

reset()
r = post(payload('입금 1,000원 반현기', owner='공동', atv=at('13:00')))
check("owner 가 '공동'이면 문구의 이름으로 판단", r.get('kind') == 'transfer' and r.get('owner') == '공동', str(r))

# ---------------------------------------------------------------- 5. 동시 저장
print('\n[5] 그 사이 폰이 먼저 저장한 경우(재시도)')
reset(fail409=1)
gets0 = ctx.eval('__store.gets')
r = post(payload('승인 3,000원 편의점', atv=at('14:00')))
check('409 뒤 다시 읽고 저장', r.get('status') == 'added' and len(txns()) == 1, str(r))
check('읽기를 두 번 함', ctx.eval('__store.gets') - gets0 == 2, str(ctx.eval('__store.gets') - gets0))

# ---------------------------------------------------------------- 6. 원본 보존
print('\n[6] 기존 기록의 원본 타입 보존')
old = {'mapValue': {'fields': {
    'id': {'stringValue': 'kept1'}, 'date': {'stringValue': TODAY},
    'amount': {'integerValue': '500'}, 'kind': {'stringValue': 'expense'},
    'owner': {'stringValue': '현기'}, 'cat': {'stringValue': '기타'},
    'memo': {'stringValue': '옛 기록'}, 'private': {'booleanValue': False},
    'syncedAt': {'timestampValue': '2026-11-01T00:00:00Z'},
}}}
reset(txns=[old])
post(payload('승인 2,000원 편의점', atv=at('15:00')))
rawvals = json.loads(ctx.eval('JSON.stringify(__store.doc)'))['fields']['data']['mapValue']['fields']['txns']['arrayValue']['values']
check('건드리지 않은 기록은 timestampValue 그대로', rawvals[0]['mapValue']['fields']['syncedAt'] == {'timestampValue': '2026-11-01T00:00:00Z'},
      json.dumps(rawvals[0], ensure_ascii=False))
check('새 기록은 정수로 저장', rawvals[1]['mapValue']['fields']['amount'] == {'integerValue': '2000'})

# ---------------------------------------------------------------- 7. 잘못된 본문
print('\n[7] 이상한 요청')
reset()
r = json.loads(ctx.eval('doPost({}).getContent()'))
check('본문이 없으면 empty_body', r.get('error') == 'empty_body', str(r))
r = json.loads(ctx.eval("doPost({postData:{contents:'not-json'}}).getContent()"))
check('JSON 이 아니면 조용히 실패', r.get('ok') is False, str(r))

print('\n==== %s ====' % ('ALL PASS' if not fails else ('FAILED: ' + ', '.join(fails))))
sys.exit(1 if fails else 0)
