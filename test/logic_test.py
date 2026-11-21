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
  isLoanFixed: isLoanFixed, loanBills: loanBills, livingBills: livingBills,
  loanBillTotal: loanBillTotal, livingBillTotal: livingBillTotal, loanBalanceTotal: loanBalanceTotal,
  openBill: openBill, saveBill: saveBill, syncBillBalField: syncBillBalField,
  planBillRowHTML: planBillRowHTML,
  cardBillTotal: cardBillTotal, stats: stats, payBill: payBill, isPaid: isPaid,
  curYM: curYM, dday: dday, dayDiff: dayDiff, billDateStr: billDateStr,
  actualBillDate: actualBillDate, baseBillDate: baseBillDate, isFixedHoliday: isFixedHoliday,
  isBizDay: isBizDay, billMoved: billMoved, billDayLabel: billDayLabel, dayHintText: dayHintText,
  billRowHTML: billRowHTML, cardRowHTML: cardRowHTML, dsOfDate: dsOfDate,
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
    html_loans = ev("(function(){__T.renderPlan(); return document.getElementById('loanList').innerHTML;})()")
    html_living = ev("(function(){__T.renderPlan(); return document.getElementById('livingList').innerHTML;})()")
    html_bills = html_loans + html_living
    html_cards = ev("(function(){__T.renderPlan(); return document.getElementById('cardList').innerHTML;})()")
    check('대출 목록에 대출 있음', '주택담보대출' in html_loans, html_loans[:200])
    check('보험·생활 목록에 대출 없음', '주택담보대출' not in html_living, html_living[:200])
    check('고정비 목록에 신한카드 없음', '신한카드' not in html_bills, html_bills[:120])
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

print('\n[12] 기준 결제일 → 실제 출금일 (주말·공휴일 평일 이연)')
def ds(ym, day):
    return ev("__T.dsOfDate(__T.actualBillDate('%s', %d))" % (ym, day))

check('2026-12-05(토) → 2026-12-07(월)', ds('2026-12', 5) == '2026-12-07', ds('2026-12', 5))
check('2026-12-20(일) → 2026-12-21(월)', ds('2026-12', 20) == '2026-12-21', ds('2026-12', 20))
check('2026-11-28(토) → 2026-11-30(월)', ds('2026-11', 28) == '2026-11-30', ds('2026-11', 28))
check('2026-12-25(성탄절 금) → 2026-12-28(월)', ds('2026-12', 25) == '2026-12-28', ds('2026-12', 25))
check('2026-11-21(토) → 2026-11-23(월)', ds('2026-11', 21) == '2026-11-23', ds('2026-11', 21))
check('2026-12-01(화, 평일·공휴일 아님) 그대로', ds('2026-12', 1) == '2026-12-01', ds('2026-12', 1))
check('2026-12-04(금) 그대로', ds('2026-12', 4) == '2026-12-04', ds('2026-12', 4))
check('2026-05-05(어린이날 화) → 2026-05-06(수)', ds('2026-05', 5) == '2026-05-06', ds('2026-05', 5))
check('2026-10-03(개천절 토) → 2026-10-05(월)', ds('2026-10', 3) == '2026-10-05', ds('2026-10', 3))
check('2026-08-15(광복절 토) → 2026-08-17(월)', ds('2026-08', 15) == '2026-08-17', ds('2026-08', 15))
check('2026-01-01(신정 목) → 2026-01-02(금)', ds('2026-01', 1) == '2026-01-02', ds('2026-01', 1))
check('2026-06-06(현충일 토) → 2026-06-08(월)', ds('2026-06', 6) == '2026-06-08', ds('2026-06', 6))
check('2026-02-31 → 말일(28일 토) → 2026-03-02(월)', ds('2026-02', 31) == '2026-03-02', ds('2026-02', 31))
check('2026-02-17(화, 말일 아님) 그대로', ds('2026-02', 17) == '2026-02-17', ds('2026-02', 17))
check('2026-04-31 → 30일(목) 그대로', ds('2026-04', 31) == '2026-04-30', ds('2026-04', 31))
check('2026-11-31 → 30일(월) 그대로', ds('2026-11', 31) == '2026-11-30', ds('2026-11', 31))
check('2027-01-01(신정 금) → 2027-01-04(월)', ds('2027-01', 1) == '2027-01-04', ds('2027-01', 1))
check('해 넘김: 2026-12-31(목) 그대로', ds('2026-12', 31) == '2026-12-31', ds('2026-12', 31))
check('연속 공휴일 아님 확인: 2026-05-06(수) 그대로', ds('2026-05', 6) == '2026-05-06', ds('2026-05', 6))

print('\n[13] 목록 표기 (기준일 + 실제 출금일)')
check('안 밀리면 매월 그대로 (2026-12-01)',
      ev("__T.billDayLabel({day:1}, '2026-12')") == '매월 1일', ev("__T.billDayLabel({day:1}, '2026-12')"))
check('밀리면 둘 다 (2026-11-28 → 30일(월))',
      ev("__T.billDayLabel({day:28}, '2026-11')") == '매월 28일 → 30일(월)',
      ev("__T.billDayLabel({day:28}, '2026-11')"))
check('달을 넘기면 달도 표기 (2026-02-31 → 3월 2일(월))',
      ev("__T.billDayLabel({day:31}, '2026-02')") == '매월 31일 → 3월 2일(월)',
      ev("__T.billDayLabel({day:31}, '2026-02')"))
check('공휴일도 표기 (2026-12-25 → 12-28(월))',
      ev("__T.billDayLabel({day:25}, '2026-12')") == '매월 25일 → 28일(월)',
      ev("__T.billDayLabel({day:25}, '2026-12')"))
check('billDateStr 가 실제 출금일 (2026-12-05 → 2026-12-07)',
      ev("__T.billDateStr({day:5}, '2026-12')") == '2026-12-07')
check('billMoved: 밀린 날 true', ev("__T.billMoved({day:5}, '2026-12')") == True)
check('billMoved: 안 밀린 날 false', ev("__T.billMoved({day:1}, '2026-12')") == False)
check('isFixedHoliday("12-25")', ev("__T.isFixedHoliday(new Date(2026,11,25))") == True)
check('isBizDay(2026-12-04 금)', ev("__T.isBizDay(new Date(2026,11,4))") == True)

print('\n[14] D-day 이 실제 출금일 기준')
ev(r'''
(function(){
  var st = __T.blankState();
  st.bills = [
    {id:'sat', name:'토요일 결제', cat:'통신', amount:55000, day:5, owner:'공동', active:true},
    {id:'hol', name:'성탄절 결제', cat:'보험', amount:92000, day:25, owner:'공동', active:true},
    {id:'plain', name:'평일 결제', cat:'대출', amount:1000000, day:4, owner:'공동', active:true}
  ];
  __T.state = __T.normalize(st);
})();
''')
check('12월 5일 결제 → 실제 12/7 의 D-day 로 계산',
      ev("__T.dsOfDate(__T.actualBillDate('2026-12', __T.state.bills.filter(function(b){return b.id==='sat';})[0].day))") == '2026-12-07')

print('\n[15] 줄 렌더에 기준일·실제일 함께 표시')
html_row = ev("__T.billRowHTML(__T.state.bills.filter(function(b){return b.id==='sat';})[0], '2026-12')") if False else None
import datetime
try:
    # 이번 달(2026-11) 기준: 5일은 목요일이라 밀리지 않고, 28일은 토요일이라 밀린다
    r_plain = ev("__T.billRowHTML(__T.state.bills.filter(function(b){return b.id==='plain';})[0], '2026-11')")
    r_move = ev("__T.billRowHTML(__T.state.bills.filter(function(b){return b.id==='sat';})[0], '2026-12')")
    check('평일 기준일은 매월 N일만 (2026-11-04 수)', '매월 4일' in r_plain and '→' not in r_plain, r_plain[:200])
    check('밀린 기준일은 화살표로 같이 표시', '매월 5일 → 7일(월)' in r_move, r_move[:220])
    c_move = ev("__T.cardRowHTML({id:'c', name:'신한카드', cat:'카드', amount:0, day:25, owner:'공동', active:true, byMonth:{}}, '2026-12')")
    check('카드 줄에도 표시', '매월 25일 → 28일(월)' in c_move, c_move[:220])
    # 홈 '곧 빠져나갈 돈' 목록도 실제 출금일 기준 (이번 달 28일은 토요일 → 30일(월))
    ev(r'''
(function(){
  var st = __T.blankState();
  st.bills = [{id:'h28', name:'실손보험', cat:'보험', amount:92000, day:28, owner:'공동', active:true},
              {id:'h15', name:'통신비', cat:'통신', amount:55000, day:15, owner:'공동', active:true}];
  __T.state = __T.normalize(st);
})();
''')
    home = ev("(function(){__T.renderHome(); return document.getElementById('upcoming').innerHTML;})()")
    check('홈 목록에 이연 표기', '매월 28일 → 30일(월)' in home, home[:300])
    want_dd = ev("(function(){var b=__T.state.bills.filter(function(x){return x.id==='h28';})[0]; return __T.dday(__T.billDateStr(b,'2026-11')).t;})()")
    check('홈 D-day 가 11/30 기준 (' + str(want_dd) + ')', want_dd in home, home[:300])
    order = ev("(function(){__T.renderHome(); var h=document.getElementById('upcoming').innerHTML; return h.indexOf('통신비') < h.indexOf('실손보험');})()")
    check('정렬도 실제 출금일 순 (15일 통신비가 30일 실손보험보다 앞)', order == True)
except Exception as e:
    check('줄 렌더', False, str(e))

print('\n[16] 입력칸 안내문')
check('빈 값 안내', ev("__T.dayHintText('')") == '주말·공휴일이면 자동으로 다음 평일로 계산돼요', ev("__T.dayHintText('')"))
check('31 초과 안내', ev("__T.dayHintText('32')") == '주말·공휴일이면 자동으로 다음 평일로 계산돼요')
check('밀리지 않는 날은 "이번 달 출금일은" 으로 안내',
      ev('''(function(){
        var ym = __T.curYM();
        for (var d = 1; d <= 31; d++){
          if (__T.billMoved({day:d}, ym)) continue;
          var t = __T.dayHintText(String(d));
          return t === '이번 달 출금일은 ' + __T.actualBillDate(ym, d).getDate() + '일(' +
            '일월화수목금토'.charAt(__T.actualBillDate(ym, d).getDay()) + ')';
        }
        return false;
      })()''') == True)
check('밀리는 날은 "주말·공휴일이라 이번 달은" 으로 안내',
      ev('''(function(){
        var ym = __T.curYM();
        for (var d = 1; d <= 31; d++){
          if (!__T.billMoved({day:d}, ym)) continue;
          var t = __T.dayHintText(String(d));
          return t.indexOf('주말·공휴일이라 이번 달은 ') === 0;
        }
        return false;
      })()''') == True)

print('\n[17] 고정비 3단 분리 (대출 / 보험·생활 / 카드)')
ev(r'''
(function(){
  var st = __T.blankState();
  st.bills = [
    {id:'L1', name:'주택담보대출', cat:'대출', amount:1120000, day:25, owner:'공동', active:true, balance:268000000},
    {id:'L2', name:'자동차 할부', cat:'대출', amount:420000, day:28, owner:'현기', active:true, balance:8400000},
    {id:'L3', name:'전세자금대출', cat:'대출', amount:300000, day:10, owner:'공동', active:true, balance:50000000},
    {id:'I1', name:'실손보험', cat:'보험', amount:92000, day:20, owner:'공동', active:true},
    {id:'I2', name:'자동차보험', cat:'보험', amount:118000, day:5, owner:'장미', active:true},
    {id:'I3', name:'KT 인터넷·TV', cat:'통신', amount:55000, day:27, owner:'공동', active:true},
    {id:'I4', name:'아파트 관리비', cat:'주거', amount:210000, day:27, owner:'공동', active:true},
    {id:'C1', name:'신한카드', cat:'카드', amount:0, day:14, owner:'공동', active:true, byMonth:{'2026-11':1340000}},
    {id:'Z1', name:'정수기 렌탈', cat:'기타', amount:32900, day:20, owner:'공동', active:true, active:true}
  ];
  __T.state = __T.normalize(st);
})();
''')
check('대출 3건만 대출 목록', ev("__T.loanBills().length") == 3,
      str(ev("JSON.stringify(__T.loanBills().map(function(b){return b.id;}))")))
check('보험·생활 5건 (보험2·통신·주거·기타)', ev("__T.livingBills().length") == 5,
      str(ev("JSON.stringify(__T.livingBills().map(function(b){return b.id;}))")))
check('카드는 어느 쪽에도 안 섞임',
      ev("__T.loanBills().concat(__T.livingBills()).filter(function(b){return b.cat==='카드';}).length") == 0)
check('대출 월 상환 합계 = 1,840,000', ev("__T.loanBillTotal()") == 1840000)
check('보험·생활 월 합계 = 507,900', ev("__T.livingBillTotal()") == 507900,
      str(ev("__T.livingBillTotal()")))
check('월 고정비 = 대출 + 보험·생활',
      ev("__T.fixedBillTotal()") == ev("__T.loanBillTotal() + __T.livingBillTotal()"))
check('대출 총 잔액 = 326,400,000', ev("__T.loanBalanceTotal()") == 326400000,
      str(ev("__T.loanBalanceTotal()")))
check('카드 청구액은 고정비 합계에 안 들어감', ev("__T.fixedBillTotal()") == 2347900)
check('stats 에 loan/living/loanBalance 가 따로',
      ev("JSON.stringify((function(){var s=__T.stats('2026-11');return [s.loan,s.living,s.loanBalance,s.fixed,s.card];})())") == '[1840000,507900,326400000,2347900,1340000]',
      str(ev("JSON.stringify((function(){var s=__T.stats('2026-11');return [s.loan,s.living,s.loanBalance,s.fixed,s.card];})())")))

print('\n[18] 렌더: 세 구역이 서로 안 섞임')
try:
    loans_html = ev("(function(){__T.renderPlan(); return document.getElementById('loanList').innerHTML;})()")
    living_html = ev("(function(){__T.renderPlan(); return document.getElementById('livingList').innerHTML;})()")
    cards_html = ev("(function(){__T.renderPlan(); return document.getElementById('cardList').innerHTML;})()")
    check('대출 구역: 대출 3건', all(n in loans_html for n in ['주택담보대출', '자동차 할부', '전세자금대출']), loans_html[:300])
    check('대출 구역: 보험·통신 없음', '실손보험' not in loans_html and 'KT 인터넷·TV' not in loans_html)
    check('대출 구역: 월 상환 합계', '월 상환 합계' in loans_html and '1,840,000원' in loans_html, loans_html[-400:])
    check('대출 구역: 대출 총 잔액', '대출 총 잔액' in loans_html and '326,400,000원' in loans_html, loans_html[-400:])
    check('대출 구역: 잔액 한 줄도 표시', '남은 잔액 268,000,000원' in loans_html, loans_html[:400])
    check('대출 구역: + 대출 추가 버튼', '+ 대출 추가' in loans_html)
    check('보험·생활 구역: 5건 모두', all(n in living_html for n in ['실손보험', '자동차보험', 'KT 인터넷·TV', '아파트 관리비', '정수기 렌탈']), living_html[:400])
    check('보험·생활 구역: 대출 없음', '주택담보대출' not in living_html)
    check('보험·생활 구역: 월 합계', '월 합계' in living_html and '507,900원' in living_html, living_html[-400:])
    check('보험·생활 구역: + 보험·고정비 추가 버튼', '+ 보험·고정비 추가' in living_html)
    check('보험·생활 구역: 캡처 버튼', '고정비·대출 캡처로 불러오기' in living_html)
    check('카드 구역: 카드만', '신한카드' in cards_html and '주택담보대출' not in cards_html and '실손보험' not in cards_html)
    check('카드 구역: 대출·보험 추가 버튼 없음', '대출 추가' not in cards_html and '보험·고정비 추가' not in cards_html)
    check('요약: 대출 금액', ev("document.getElementById('sumLoan').textContent") == '1,840,000원', str(ev("document.getElementById('sumLoan').textContent")))
    check('요약: 보험·생활 금액', ev("document.getElementById('sumLiving').textContent") == '507,900원', str(ev("document.getElementById('sumLiving').textContent")))
    check('요약: 월 고정비 = 대출+보험·생활', ev("document.getElementById('sumFixed').textContent") == '2,347,900원', str(ev("document.getElementById('sumFixed').textContent")))
    check('요약: 카드는 따로 표시', ev("document.getElementById('sumCard').textContent") == '1,340,000원', str(ev("document.getElementById('sumCard').textContent")))
    check('재무설계: 고정비 내역 줄', '대출 1,840,000원 + 보험·생활 507,900원' == ev("document.getElementById('plFixedBreak').textContent"), str(ev("document.getElementById('plFixedBreak').textContent")))
    check('재무설계: 월 고정비 합계는 카드 제외', ev("document.getElementById('plFixed').textContent") == '2,347,900원', str(ev("document.getElementById('plFixed').textContent")))
except Exception as e:
    check('3단 렌더 검사', False, str(e))

print('\n[19] 추가 시트 기본 분류 · 대출 잔액 입력')
ev(r'''
(function(){
  var st = __T.blankState();
  st.bills = [
    {id:'L1', name:'주택담보대출', cat:'대출', amount:1120000, day:25, owner:'공동', active:true, balance:268000000},
    {id:'I1', name:'실손보험', cat:'보험', amount:92000, day:20, owner:'공동', active:true}
  ];
  __T.state = __T.normalize(st);
})();
''')
try:
    ev("__T.openBill(null, '대출')")
    check('대출 추가: 제목', ev("document.getElementById('bTitle').textContent") == '대출 추가', str(ev("document.getElementById('bTitle').textContent")))
    check('대출 추가: 분류 기본 대출', ev("document.getElementById('bCat').value") == '대출')
    check('대출 추가: 잔액 칸 보임', ev("document.getElementById('bBalField').hidden") == False)
    ev("document.getElementById('bName').value = '신용대출'")
    ev("document.getElementById('bAmount').value = '350,000'")
    ev("document.getElementById('bDay').value = '17'")
    ev("document.getElementById('bBal').value = '12,000,000'")
    ev("__T.saveBill()")
    check('대출 저장: 새 대출이 대출 목록으로',
          ev("__T.loanBills().filter(function(b){return b.name==='신용대출';}).length") == 1)
    check('대출 저장: 잔액도 함께 저장', ev("__T.loanBalanceTotal()") == 268000000 + 12000000, str(ev("__T.loanBalanceTotal()")))
    check('대출 저장: 월 상환 합계 1,470,000', ev("__T.loanBillTotal()") == 1470000)
    check('대출 저장: 재무설계 대출 잔액에도 반영', ev("__T.state.plan.loan") == 12000000, str(ev("__T.state.plan.loan")))

    ev("__T.openBill(null, '보험')")
    check('보험 추가: 제목', ev("document.getElementById('bTitle').textContent") == '보험·고정비 추가', str(ev("document.getElementById('bTitle').textContent")))
    check('보험 추가: 분류 기본 보험', ev("document.getElementById('bCat').value") == '보험')
    check('보험 추가: 잔액 칸 숨김', ev("document.getElementById('bBalField').hidden") == True)
    ev("document.getElementById('bName').value = '암보험'")
    ev("document.getElementById('bAmount').value = '63,000'")
    ev("document.getElementById('bDay').value = '12'")
    ev("__T.saveBill()")
    check('보험 저장: 보험·생활로 들어감',
          ev("__T.livingBills().filter(function(b){return b.name==='암보험';}).length") == 1)
    check('보험 저장: 대출 총 잔액은 그대로', ev("__T.loanBalanceTotal()") == 280000000)
    check('보험 저장: 보험·생활 합계 155,000', ev("__T.livingBillTotal()") == 155000)

    # 분류를 대출 → 보험으로 바꾸면 잔액은 지운다
    ev("__T.openBill(__T.state.bills.filter(function(b){return b.name==='신용대출';})[0])")
    ev("document.getElementById('bCat').value = '보험'; __T.syncBillBalField()")
    ev("__T.saveBill()")
    check('대출→보험으로 바꾸면 잔액 0',
          ev("Math.round(+__T.state.bills.filter(function(b){return b.name==='신용대출';})[0].balance || 0)") == 0)
    check('바뀐 항목은 보험·생활로 이동',
          ev("__T.livingBills().filter(function(b){return b.name==='신용대출';}).length") == 1)
    check('대출 잔액에서도 빠짐', ev("__T.loanBalanceTotal()") == 268000000, str(ev("__T.loanBalanceTotal()")))
    check('재무설계 대출 잔액도 되돌아감', ev("__T.state.plan.loan") == 0, str(ev("__T.state.plan.loan")))
except Exception as e:
    check('시트 기본값/잔액', False, str(e))

print('\n[20] 기존 데이터 호환 (bills 스키마 그대로)')
ev(r'''
(function(){
  var st = __T.blankState();
  __T.state = __T.normalize(st);
})();
''')
check('정규화가 고정비에 새 키를 만들지 않음',
      ev("JSON.stringify((function(){var st=__T.blankState(); st.bills=[{id:'x',name:'주담대',cat:'대출',amount:1000000,day:25,owner:'공동',active:true,balance:100000000}]; __T.state=__T.normalize(st); return Object.keys(__T.state.bills[0]).sort();})())") == '["active","amount","balance","cat","day","id","name","owner"]',
      str(ev("JSON.stringify(Object.keys(__T.state.bills[0]))")))
check('잔액 없는 예전 대출도 대출로 분류 (cat 기준)',
      ev("__T.isLoanFixed({id:'y',name:'신용대출',cat:'대출',amount:300000,day:10,owner:'공동',active:true})") == True)
check('카드 항목은 대출로 분류 안 됨',
      ev("__T.isLoanFixed({id:'z',name:'카드',cat:'카드',amount:0,day:14,owner:'공동',active:true,balance:5})") == False)
check('잔액만 있고 분류가 기타인 예전 캡처도 대출로',
      ev("__T.isLoanFixed({id:'w',name:'은행대출',cat:'기타',amount:100,day:1,owner:'공동',active:true,balance:1000})") == True)
check('잔액 0 인 보험은 대출이 아니라 보험·생활',
      ev("__T.isLoanFixed({id:'v',name:'암보험',cat:'보험',amount:63000,day:12,owner:'공동',active:true,balance:0})") == False)

print('\n==== %s ====' % ('ALL PASS' if not fails else ('FAILED: ' + ', '.join(fails))))
sys.exit(1 if fails else 0)
