# 가계부 카드 청구액 분리 로직 테스트 (QuickJS)
# index.html 의 스크립트를 꺼내 DOM/Firebase 를 흉내 내는 스텁 위에서 핵심 계산만 검사한다.
import re, sys, os
import quickjs

HERE = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(HERE, '..', 'index.html')
src = open(HTML, encoding='utf-8').read()
js = re.search(r'<script>(.*?)</script>', src, re.S).group(1)

# 시작부(즉시 실행 init) 를 떼고, 내부 함수를 테스트용으로 노출한다
tail = "if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);\nelse init();"
assert tail in js, 'script tail not found'
js = js.replace(tail, '')

export_stmt = r'''
globalThis.__T = {
  get state(){ return state; }, set state(v){ state = v; },
  render: render, normalize: normalize, sampleState: sampleState, blankState: blankState,
  isCardBill: isCardBill, billAmountFor: billAmountFor, setCardMonth: setCardMonth,
  fixedBills: fixedBills, cardBills: cardBills, fixedBillTotal: fixedBillTotal,
  cardBillTotal: cardBillTotal, stats: stats, payBill: payBill, isPaid: isPaid,
  curYM: curYM, dday: dday, dayDiff: dayDiff, billDateStr: billDateStr,
  normalizeCards: normalizeCards, normalizeBills: normalizeBills, parseOcrJSON: parseOcrJSON, markCardDups: markCardDups, markBillDups: markBillDups, addShotBills: addShotBills, loadShotDemo: loadShotDemo,
  addShotCards: addShotCards, saveCardBill: saveCardBill, openCardBill: openCardBill,
  shot: shot, setShot: function(v){ shot = v; }, save: save,
  renderHome: renderHome, renderPlan: renderPlan
};
'''
idx = js.rstrip().rfind('})();')
assert idx > 0
js = js[:idx] + export_stmt + '\n})();\n'

stub = r'''
var __store = {};
var __log = [];
function stubEl(tag){
  var o = {
    tagName: tag || 'div', style:{}, dataset:{}, children:[], childNodes:[], files:[],
    innerHTML:'', textContent:'', value:'', className:'', id:'', hidden:false, checked:false,
    src:'', className:'', href:'',
    classList:{ add:function(){}, remove:function(){}, toggle:function(){}, contains:function(){ return false; } },
    setAttribute:function(){}, getAttribute:function(){ return null; }, removeAttribute:function(){},
    appendChild:function(c){ return c; }, removeChild:function(c){ return c; }, insertBefore:function(c){ return c; },
    focus:function(){}, blur:function(){}, click:function(){}, select:function(){},
    querySelector:function(){ return stubEl(); }, querySelectorAll:function(){ return []; },
    closest:function(){ return null; }, addEventListener:function(){}, removeEventListener:function(){},
    contains:function(){ return false; }, cloneNode:function(){ return stubEl(tag); }
  };
  return new Proxy(o, {
    get:function(t,k){ if (k in t) return t[k]; return function(){}; },
    set:function(t,k,v){ t[k]=v; return true; }
  });
}
var __els = {};
var document = {
  readyState:'complete', body:stubEl('body'), documentElement:stubEl('html'),
  getElementById:function(id){ if (!__els[id]) __els[id] = stubEl(); __els[id].id = id; return __els[id]; },
  querySelector:function(){ return stubEl(); }, querySelectorAll:function(){ return []; },
  createElement:function(t){ return stubEl(t); }, addEventListener:function(){},
  execCommand:function(){ return true; }
};
var window = { addEventListener:function(){}, scrollTo:function(){}, document: document, location:{ origin:'https://x' } };
var navigator = { clipboard: null, serviceWorker: null };
var localStorage = {
  getItem:function(k){ return __store[k] === undefined ? null : __store[k]; },
  setItem:function(k,v){ __store[k] = String(v); }, removeItem:function(k){ delete __store[k]; }
};
var setTimeout = function(fn){ return 0; };
var clearTimeout = function(){};
var fetch = function(){ return Promise.reject(new Error('no net')); };
var firebase = undefined;
var Notification = function(){};
function alert(){} function confirm(){ return true; }
'''

ctx = quickjs.Context()
ctx.eval(stub)
ctx.eval(js)

T = ctx.get('__T')
fails = []
def check(name, cond, detail=''):
    if cond:
        print('  OK   ' + name)
    else:
        print('  FAIL ' + name + ('  ' + detail if detail else ''))
        fails.append(name)

def ev(expr):
    return ctx.eval(expr)

# ---------- 테스트용 가계부 ----------
setup = r'''
(function(){
  var st = { v:1, viewMonth:'2026-11',
    plan:{ saveGoal:0, loan:0, assets:0 },
    incomes:[{id:'i1', name:'현기 월급', amount:3200000, day:25, owner:'현기', active:true}],
    accounts:[],
    bills:[
      {id:'loan1', name:'주택담보대출', cat:'대출', amount:1120000, day:25, owner:'공동', active:true},
      {id:'ins1', name:'실손보험', cat:'보험', amount:92000, day:20, owner:'공동', active:true},
      {id:'card1', name:'신한카드', cat:'카드', amount:0, day:28, owner:'공동', active:true,
        byMonth:{ '2026-11': 1340000 }}
    ],
    txns:[], paid:{},
    settings:{ currentUser:'현기', lastOwner:'현기', geminiKey:'' } };
  __T.state = __T.normalize(st);
})();
'''
ev(setup)

print('\n[1] 달별 금액 분리')
check('11월 카드 청구액 = 1,340,000',
      ev("__T.billAmountFor(__T.state.bills.filter(function(b){return b.id==='card1';})[0], '2026-11')") == 1340000)
check('12월 카드 청구액 = 0 (이월 없음)',
      ev("__T.billAmountFor(__T.state.bills.filter(function(b){return b.id==='card1';})[0], '2026-12')") == 0)
check('12월 고정비(대출)는 그대로 1,120,000 반복',
      ev("__T.billAmountFor(__T.state.bills.filter(function(b){return b.id==='loan1';})[0], '2026-12')") == 1120000)
check('11월 고정비 합계 = 1,212,000 (카드 제외)',
      ev("__T.fixedBillTotal()") == 1212000)
check('11월 카드 합계 = 1,340,000',
      ev("__T.cardBillTotal('2026-11')") == 1340000)
check('12월 카드 합계 = 0',
      ev("__T.cardBillTotal('2026-12')") == 0)
check('카드 청구액은 fixedBills 에 없음',
      ev("__T.fixedBills().filter(function(b){return b.cat==='카드';}).length") == 0)
check('cardBills 에 1건',
      ev("__T.cardBills().length") == 1)

print('\n[2] stats 합계 분리')
s11 = json.loads(ev("JSON.stringify((function(){var s=__T.stats('2026-11');return {fixed:s.fixed, card:s.card, unpaidFixed:s.unpaidFixed, unpaidCard:s.unpaidCard, unpaid:s.unpaid};})())")) if False else None
import json
res = ev("JSON.stringify((function(){var s=__T.stats('2026-11');return {fixed:s.fixed, card:s.card, unpaidFixed:s.unpaidFixed, unpaidCard:s.unpaidCard, unpaid:s.unpaid};})())")
d = json.loads(res)
check('stats.fixed = 1,212,000 (카드 미포함)', d['fixed'] == 1212000, str(d))
check('stats.card = 1,340,000', d['card'] == 1340000, str(d))
check('unpaidFixed = 1,212,000', d['unpaidFixed'] == 1212000, str(d))
check('unpaidCard = 1,340,000', d['unpaidCard'] == 1340000, str(d))
check('unpaid 합계 = 2,552,000', d['unpaid'] == 2552000, str(d))

print('\n[3] D-day 알림')
check("D-7 (2026-11-28)", ev("__T.dday('2026-11-28').t") == 'D-7', ev("__T.dday('2026-11-28').t"))
check("D-1 (2026-11-22)", ev("__T.dday('2026-11-22').t") == 'D-1')
check("D-day (2026-11-21)", ev("__T.dday('2026-11-21').t") == '오늘')
check("지난 날 (2026-11-14)", ev("__T.dday('2026-11-14').t") == '7일 지남')
check("D-7 hot 아님", ev("__T.dday('2026-11-28').hot") == False)
check("D-1 hot", ev("__T.dday('2026-11-22').hot") == True)

print('\n[4] 납부 처리')
ev("__T.payBill('card1')")
check('카드 납부분류는 지난달 금액으로 기록됨 (1,340,000)',
      ev("(function(){var t=__T.state.txns.filter(function(x){return x.billId==='card1';}); return t.length===1 && t[0].amount===1340000;})()"))
check('카드 납부 후 11월 unpaidCard = 0',
      ev("__T.stats('2026-11').unpaidCard") == 0)
check('고정비 납부분류는 그대로',
      ev("__T.stats('2026-11').unpaidFixed") == 1212000)

print('\n[5] 예전 카드 항목 이전(migration)')
ev(r'''
(function(){
  var st = __T.blankState();
  st.bills = [{id:'old1', name:'우리카드', cat:'카드', amount:870000, day:12, owner:'공동', active:true}];
  __T.state = __T.normalize(st);
})();
''')
check('예전 금액이 이번 달(2026-11)에만 잡힘',
      ev("__T.billAmountFor(__T.state.bills[0], '2026-11')") == 870000)
check('다음 달(2026-12)은 0',
      ev("__T.billAmountFor(__T.state.bills[0], '2026-12')") == 0)
check('byMonth 기록이 생김',
      ev("JSON.stringify(__T.state.bills[0].byMonth)") == '{"2026-11":870000}')

print('\n[6] 카드 청구액 캡처 파싱/담기')
ev(r'''
(function(){
  var st = __T.blankState();
  st.bills = [
    {id:'c1', name:'신한카드', cat:'카드', amount:0, day:14, owner:'공동', active:true, byMonth:{'2026-10':900000}},
    {id:'l1', name:'주택담보대출', cat:'대출', amount:1000000, day:25, owner:'공동', active:true}
  ];
  __T.state = __T.normalize(st);
})();
''')
check('parseOcrJSON(card) 카드 2건',
      ev("__T.parseOcrJSON('{\"cards\":[{\"name\":\"신한카드\",\"amount\":1340000,\"billingDay\":14},{\"name\":\"삼성카드\",\"amount\":486000,\"billingDay\":25}]}', 'card').length") == 2)
ev("__T.shot.cards = __T.markCardDups(__T.parseOcrJSON('{\"cards\":[{\"name\":\"신한카드\",\"amount\":1340000,\"billingDay\":14},{\"name\":\"삼성카드\",\"amount\":486000,\"billingDay\":25}]}', 'card'))")
check('기존 카드와 이름이 같으면 update 로 붙음',
      ev("__T.shot.cards[0].act") == 'update' and ev("__T.shot.cards[0].matchId") == 'c1')
check('새 카드는 add', ev("__T.shot.cards[1].act") == 'add')
ev("__T.addShotCards()")
check('신한카드 11월 금액 갱신',
      ev("__T.billAmountFor(__T.state.bills.filter(function(b){return b.name==='신한카드';})[0], '2026-11')") == 1340000)
check('신한카드 지난달(10월) 기록은 그대로',
      ev("__T.billAmountFor(__T.state.bills.filter(function(b){return b.name==='신한카드';})[0], '2026-10')") == 900000)
check('삼성카드가 새 카드로 담김',
      ev("__T.state.bills.filter(function(b){return b.name==='삼성카드';}).length") == 1)
check('삼성카드 11월 486,000',
      ev("__T.cardBillTotal('2026-11')") == 1340000 + 486000)
check('대출은 그대로 1건',
      ev("__T.state.bills.filter(function(b){return b.cat==='대출';}).length") == 1)
check('카드 담기 후 12월 카드 합계 0',
      ev("__T.cardBillTotal('2026-12')") == 0)

print('\n[7] 화면 렌더 (스텁 DOM 에서 오류 없이)')
try:
    ev("__T.render()")
    check('render() 예외 없음', True)
except Exception as e:
    check('render() 예외 없음', False, str(e))

print('\n[8] 고정비/카드 분리 렌더 결과')
try:
    html_bills = ev("(function(){__T.renderPlan(); return document.getElementById('billList').innerHTML;})()")
    html_cards = ev("(function(){__T.renderPlan(); return document.getElementById('cardList').innerHTML;})()")
    check('고정비 목록에 신한카드 없음', '신한카드' not in html_bills, html_bills[:120])
    check('고정비 목록에 대출 있음', '주택담보대출' in html_bills)
    check('카드 목록에 신한카드 있음', '신한카드' in html_cards)
    check('카드 목록에 대출 없음', '주택담보대출' not in html_cards)
    check('카드 목록에 금액 표시', '1,340,000' in html_cards, html_cards[:200])
    home_card = ev("(function(){__T.renderHome(); return document.getElementById('homeCardAmt').textContent;})()")
    check('홈 카드 금액 표시', home_card not in ('', '0원'), str(home_card))
except Exception as e:
    check('분리 렌더 검사', False, str(e))

print('\n[9] 직접 입력(카드 청구액 시트)')
ev(r'''
(function(){
  var st = __T.blankState();
  st.bills = [{id:'l1', name:'주택담보대출', cat:'대출', amount:1000000, day:25, owner:'공동', active:true}];
  __T.state = __T.normalize(st);
})();
''')
ev("__T.openCardBill(null)")
ev("document.getElementById('cName').value = '현대카드 M'") 
ev("document.getElementById('cDay').value = '17'")
ev("document.getElementById('cAmount').value = '742,000'")
ev("__T.saveCardBill()")
check('새 카드가 cat 카드로 담김',
      ev("__T.state.bills.filter(function(b){return b.cat==='카드' && b.name==='현대카드 M';}).length") == 1)
check('이번 달 금액 742,000', ev("__T.cardBillTotal('2026-11')") == 742000)
check('다음 달 카드 0', ev("__T.cardBillTotal('2026-12')") == 0)
check('고정비 합계는 그대로', ev("__T.fixedBillTotal()") == 1000000)
ev("__T.openCardBill(__T.state.bills.filter(function(b){return b.name==='현대카드 M';})[0])")
ev("document.getElementById('cAmount').value = '812,500'")
ev("__T.saveCardBill()")
check('같은 카드 다시 입력하면 이번 달 금액만 바뀜', ev("__T.cardBillTotal('2026-11')") == 812500)
check('카드가 중복 생기지 않음',
      ev("__T.state.bills.filter(function(b){return b.name==='현대카드 M';}).length") == 1)

print('\n[10] 캡처 예시/검토 화면 (카드 모드)')
ev(r'''
(function(){
  var st = __T.blankState();
  st.bills = [{id:'c1', name:'신한카드', cat:'카드', amount:0, day:14, owner:'공동', active:true, byMonth:{}}];
  __T.state = __T.normalize(st);
})();
''')
try:
    ev("__T.shot.mode='card'; __T.loadShotDemo('card')")
    check('카드 예시 검토 화면 렌더', ev("__T.shot.cards.length") == 2)
    check('신한카드는 기존 카드로 update', ev("__T.shot.cards[0].act") == 'update')
    html = ev("document.getElementById('shotReview').innerHTML")
    check('검토 화면에 카드 이름', '신한카드' in html)
    check('검토 화면에 이번 달 안내', '에만 쓰여요' in html, html[:200])
except Exception as e:
    check('카드 검토 화면', False, str(e))

print('\n[11] 고정비 캡처에 섞인 카드값은 이번 달로')
ev(r'''
(function(){
  var st = __T.blankState();
  st.bills = [{id:'l1', name:'주택담보대출', cat:'대출', amount:1000000, day:25, owner:'공동', active:true}];
  __T.state = __T.normalize(st);
})();
''')
try:
    ev("__T.shot.bills = __T.markBillDups(__T.normalizeBills([{name:'신한카드 결제', category:'카드', amount:1340000, billingDay:14}]))")
    ev("__T.addShotBills()")
    check('카드가 고정비로 들어가지 않음',
          ev("__T.fixedBills().filter(function(b){return b.cat==='카드';}).length") == 0)
    check('카드 청구액으로 담김 (11월 1,340,000)', ev("__T.cardBillTotal('2026-11')") == 1340000)
    check('고정비 합계에 안 섞임', ev("__T.fixedBillTotal()") == 1000000)
    check('12월에는 0', ev("__T.cardBillTotal('2026-12')") == 0)
except Exception as e:
    check('카드 섞임 처리', False, str(e))

print('\n==== %s ====' % ('ALL PASS' if not fails else ('FAILED: ' + ', '.join(fails))))
sys.exit(1 if fails else 0)
