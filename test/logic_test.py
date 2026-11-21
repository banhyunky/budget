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
  renderHome: renderHome, renderPlan: renderPlan,
  shortWon: shortWon, shortNum: shortNum, prevYMs: prevYMs, dowOf: dowOf,
  coachPace: coachPace, coachPaceHTML: coachPaceHTML, loanRank: loanRank, loanQuickWin: loanQuickWin,
  ruleHeadline: ruleHeadline, coachSig: coachSig, coachCacheRead: coachCacheRead,
  coachCacheWrite: coachCacheWrite, coachCacheFresh: coachCacheFresh, coachSummary: coachSummary,
  coachPrompt: coachPrompt, parseCoachJSON: parseCoachJSON, coachCleanText: coachCleanText,
  runCoachAI: runCoachAI, renderCoachBar: renderCoachBar, renderCoach: renderCoach, openCoach: openCoach,
  coachLoanHTML: coachLoanHTML, coachAIHTML: coachAIHTML,
  chart6Months: chart6Months, monthShare: monthShare, monthSpendSplit: monthSpendSplit,
  barsSVG: barsSVG, shareSVG: shareSVG,
  loanRankCardHTML: loanRankCardHTML, renderCharts: renderCharts, COACH_KEY: 'money-coach-v1'
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

print('\n[21] AI 코치 · 대출 상환 우선순위 (금리 / 현금흐름)')
import json as _json
ev(r'''
(function(){
  var st = __T.blankState();
  st.incomes = [{id:'i1', name:'월급', amount:5300000, day:25, owner:'공동', active:true}];
  st.bills = [
    {id:'L1', name:'주택담보대출', cat:'대출', amount:1120000, day:25, owner:'공동', active:true, balance:268000000, rate:3.8},
    {id:'L2', name:'부산은행 신용대출', cat:'대출', amount:846000, day:12, owner:'공동', active:true, balance:50297289, rate:7.68},
    {id:'L3', name:'햇살론', cat:'대출', amount:148000, day:20, owner:'현기', active:true, balance:1250024, rate:8.83},
    {id:'L4', name:'자동차 할부', cat:'대출', amount:420000, day:28, owner:'현기', active:true, balance:8400000, rate:0},
    {id:'C1', name:'신한카드', cat:'카드', amount:0, day:14, owner:'공동', active:true, byMonth:{'2026-11':1340000}}
  ];
  __T.state = __T.normalize(st);
})();
''')
rate_order = [x[0] for x in _json.loads(ev("JSON.stringify(__T.loanRank('rate').map(function(l){return [l.name,l.rate];}))"))]
check('금리 순: 8.83 → 7.68 → 3.8 → 0',
      rate_order == ['햇살론', '부산은행 신용대출', '주택담보대출', '자동차 할부'], str(rate_order))
check('대출 4건만 (카드 제외)', ev("__T.loanRank('rate').length") == 4)
cash_order = [x[0] for x in _json.loads(ev("JSON.stringify(__T.loanRank('cash').map(function(l){return [l.name,l.per10m];}))"))]
check('현금흐름 순: 1,000만원당 월 상환액 큰 순',
      cash_order == ['햇살론', '자동차 할부', '부산은행 신용대출', '주택담보대출'], str(cash_order))
check('잔액 1,000만원당 월 상환액 계산 (햇살론)',
      ev("__T.loanRank('cash')[0].per10m") == round(148000 / 1250024 * 10000000),
      str(ev("__T.loanRank('cash')[0].per10m")))
check('완납 시 월 절감액 = 월 상환액',
      ev("__T.loanRank('rate')[0].monthly") == 148000)
check('금리 8% 이상 소액 대출이 빠른 승리로 잡힘',
      ev("__T.loanQuickWin().name") == '햇살론', str(ev("__T.loanQuickWin().name")))
check('금리 8% 이상이 없으면 빠른 승리 없음',
      ev("(function(){var st=__T.blankState(); st.bills=[{id:'x',name:'저금리',cat:'대출',amount:100000,day:5,owner:'공동',active:true,balance:1000000,rate:3.5}]; __T.state=__T.normalize(st); return __T.loanQuickWin() === null;})()") == True)
check('짧은 금액 표기 (311,195,858 → 3.1억)', ev("__T.shortWon(311195858)") == '3.1억', ev("__T.shortWon(311195858)"))
check('짧은 금액 표기 (148,000 → 14.8만)', ev("__T.shortWon(148000)") == '14.8만')
check('짧은 금액 표기 (8,500 → 8,500)', ev("__T.shortWon(8500)") == '8,500')

ev(r'''
(function(){
  var st = __T.blankState();
  st.incomes = [{id:'i1', name:'월급', amount:5300000, day:25, owner:'공동', active:true}];
  st.bills = [
    {id:'L1', name:'주택담보대출', cat:'대출', amount:1120000, day:25, owner:'공동', active:true, balance:268000000, rate:3.8},
    {id:'L2', name:'부산은행 신용대출', cat:'대출', amount:846000, day:12, owner:'공동', active:true, balance:50297289, rate:7.68},
    {id:'L3', name:'햇살론', cat:'대출', amount:148000, day:20, owner:'현기', active:true, balance:1250024, rate:8.83},
    {id:'L4', name:'자동차 할부', cat:'대출', amount:420000, day:28, owner:'현기', active:true, balance:8400000, rate:0},
    {id:'C1', name:'신한카드', cat:'카드', amount:0, day:14, owner:'공동', active:true, byMonth:{'2026-11':1340000}}
  ];
  __T.state = __T.normalize(st);
})();
''')
head = ev("__T.ruleHeadline('2026-11')")
check('홈 한 줄: 고금리 소액 대출 빠른 승리',
      '8.83%' in head and '햇살론' in head and '14.8만' in head, str(head))

print('\n[22] 이번 달 지출 페이스')
pace = _json.loads(ev("JSON.stringify((function(){var p=__T.coachPace('2026-11');return {left:p.left,leftDays:p.leftDays,perDay:p.perDay,dailyNow:p.dailyNow,diff:p.diff,dayOf:p.dayOf,dim:p.daysIn};})())"))
check('남은 날 = 오늘 포함 말일까지', pace['leftDays'] == pace['dim'] - pace['dayOf'] + 1, str(pace))
check('남은 여유 = 수입 − 미납 고정비·카드', pace['left'] == 5300000 - 3874000, str(pace))
check('하루 쓸 수 있는 돈 = 남은 여유 ÷ 남은 날',
      pace['perDay'] == int(pace['left'] / pace['leftDays']), str(pace))
check('지금 하루 평균 지출은 쓴 돈 기준', ev("__T.coachPace('2026-11').dailyNow") == 0, str(pace))
html_pace = ev("__T.coachPaceHTML('2026-11')")
check('페이스 카드에 남은 날·하루 금액', '하루' in html_pace and '남은' in html_pace, html_pace[:200])
check('페이스 카드에 사용률·곧 나갈 돈', '이번 달 사용' in html_pace and '고정비' in html_pace, html_pace[:400])

print('\n[23] 6개월 지출 흐름 데이터')
d6 = _json.loads(ev("JSON.stringify(__T.chart6Months('2026-11'))"))
check('6개월치', len(d6) == 6, str(len(d6)))
check('오래된 달부터 6월→11월', [x['ym'] for x in d6] ==
      ['2026-06', '2026-07', '2026-08', '2026-09', '2026-10', '2026-11'], str([x['ym'] for x in d6]))
check('라벨은 월만', d6[-1]['label'] == '11월', str(d6[-1]['label']))
check('고정비는 매달 같은 값 (대출+보험생활)', [x['fixed'] for x in d6] == [2534000] * 6, str([x['fixed'] for x in d6]))
check('변동·카드: 11월 1,340,000 / 10월 0',
      d6[5]['flexible'] == 1340000 and d6[4]['flexible'] == 0, str([x['flexible'] for x in d6]))
check('합계 = 고정비 + 변동·카드', d6[5]['total'] == 2534000 + 1340000, str(d6[5]))
d_over = _json.loads(ev("JSON.stringify(__T.chart6Months('2026-02'))"))
check('해를 넘어가도 6개월 (2025-09 → 2026-02)',
      [x['ym'] for x in d_over] == ['2025-09', '2025-10', '2025-11', '2025-12', '2026-01', '2026-02'],
      str([x['ym'] for x in d_over]))
svg6 = ev("__T.barsSVG(__T.chart6Months('2026-11'), '2026-11')")
check('막대 그래프 SVG 로 그려짐', svg6.startswith('<svg') and '</svg>' in svg6 and svg6.count('<rect') >= 6)
check('그래프에 6개월 라벨', all((m + '월') in svg6 for m in ['6', '7', '8', '9', '10', '11']))
check('강조한 달(11월) 금액 표시', '387만' in svg6, svg6[-400:])

print('\n[24] 이번 달 지출 비중')
sh = _json.loads(ev("JSON.stringify(__T.monthShare('2026-11'))"))
check('대출 상환 = 고정 대출 합계', sh['loan'] == 2534000, str(sh))
check('보험·생활 = 0', sh['living'] == 0, str(sh))
check('변동·카드 = 카드 + 변동', sh['flex'] == 1340000, str(sh))
check('비중 합이 100%', abs(sh['loanPct'] + sh['livingPct'] + sh['flexPct'] - 100) <= 0.2, str(sh))
check('대출 비중 65.4%', sh['loanPct'] == 65.4, str(sh['loanPct']))
shsvg = ev("__T.shareSVG(__T.monthShare('2026-11'))")
check('가로 누적 바 SVG (2조각)', shsvg.startswith('<svg') and shsvg.count('<rect') == 2, shsvg[:300])
check('기록이 없으면 빈 비중',
ev("(function(){var st=__T.blankState(); __T.state=__T.normalize(st); var s=__T.monthShare('2026-11'); return s.total===0 && s.loanPct===0 && __T.shareSVG(s)==='';})()") == True)

print('\n[24-b] 카드 청구액 납부 기록을 두 번 세지 않음')
ev(r'''
(function(){
  var st = __T.blankState();
  st.incomes = [{id:'i1', name:'월급', amount:5300000, day:25, owner:'공동', active:true}];
  st.bills = [
    {id:'L1', name:'주택담보대출', cat:'대출', amount:1000000, day:25, owner:'공동', active:true, balance:100000000, rate:4},
    {id:'C1', name:'신한카드', cat:'카드', amount:0, day:14, owner:'공동', active:true, byMonth:{'2026-11':1340000}}
  ];
  st.txns = [{id:'p1', date:'2026-11-16', amount:1340000, kind:'expense', cat:'카드', owner:'공동', memo:'신한카드', billId:'C1'}];
  __T.state = __T.normalize(st);
})();
''')
sp = _json.loads(ev("JSON.stringify(__T.monthSpendSplit('2026-11'))"))
check('카드 납부액은 변동에서 빠짐', sp['variable'] == 0 and sp['paidCard'] == 1340000, str(sp))
check('카드 몫은 한 번만', sp['flexible'] == 1340000 and sp['total'] == 2340000, str(sp))
sh_paid = _json.loads(ev("JSON.stringify(__T.monthShare('2026-11'))"))
check('비중도 두 번 안 셈', sh_paid['flex'] == 1340000 and sh_paid['total'] == 2340000, str(sh_paid))
check('납부한 카드도 비중에는 남음', abs(sh_paid['flexPct'] - 57.3) <= 0.2, str(sh_paid['flexPct']))
sp_sum = _json.loads(ev("JSON.stringify(__T.coachSummary('2026-11'))"))
check('AI 요약도 납부한 카드값을 따로', sp_sum['variableSpend'] == 0 and sp_sum['cardBillThisMonth'] == 1340000, str(sp_sum))

print('\n[25] 제미나이 진단 JSON 파서')
def coach_parse(text):
    return _json.loads(ev("JSON.stringify(__T.parseCoachJSON(%s))" % _json.dumps(text)))

sample = ('설명입니다.\n```json\n{"headline":"카드값 134만원, 25일 전에 100만원으로",'
          '"patterns":["고정비 비중 73%","카드값이 변동의 100%"],'
          '"loanAdvice":"8.83% 햇살론부터",'
          '"actions":["카드값 100만원으로 줄이기","햇살론 20만원 추가 상환","통신비 5만원 줄이기","네번째"]}\n```')
co = coach_parse(sample)
check('코드블록·여분 문장을 받아 줌', co is not None, str(co))
if co:
    check('headline 추출', co['headline'] == '카드값 134만원, 25일 전에 100만원으로', str(co))
    check('패턴 2개', len(co['patterns']) == 2, str(co['patterns']))
    check('대출 조언 추출', co['loanAdvice'] == '8.83% 햇살론부터')
    check('행동은 3개까지만', len(co['actions']) == 3, str(co['actions']))
co2 = coach_parse('{"coach":{"headline":"한 줄","patterns":["p1"],"loanAdvice":"l","actions":["a"]}}')
check('coach 로 한 겹 싸여도 읽음', bool(co2) and co2['headline'] == '한 줄' and co2['actions'] == ['a'], str(co2))
co3 = coach_parse('{"patterns":"· 이자 8.83% 먼저\n· 카드값 줄이기"}')
check('패턴이 문자열 한 덩어리여도 나눔', bool(co3) and len(co3['patterns']) == 2, str(co3))
check('headline 이 없으면 패턴 첫 줄로', bool(co3) and co3['headline'] == co3['patterns'][0], str(co3))
check('JSON 이 아니면 null', coach_parse('그냥 문장') is None)
check('빈 응답이면 null', coach_parse('') is None)

print('\n[26] 홈 한 줄 배너 (규칙 → AI 캐시)')
ev(r'''
(function(){
  var st = __T.blankState();
  st.incomes = [{id:'i1', name:'월급', amount:5300000, day:25, owner:'공동', active:true}];
  st.bills = [
    {id:'L3', name:'햇살론', cat:'대출', amount:148000, day:20, owner:'현기', active:true, balance:1250024, rate:8.83},
    {id:'C1', name:'신한카드', cat:'카드', amount:0, day:14, owner:'공동', active:true, byMonth:{'2026-11':1340000}}
  ];
  __T.state = __T.normalize(st);
})();
''')
ev("localStorage.removeItem(__T.COACH_KEY)")
ev("__T.renderHome()")
bar = ev("document.getElementById('coachBarTxt').textContent")
check('캐시 없으면 규칙 한 줄', bar == ev("__T.ruleHeadline('2026-11')"), str(bar))
check('배너에 금액·행동이 들어감', '갚으면' in bar and '원' in bar, str(bar))
check('AI 배지는 숨김', ev("document.getElementById('coachBarAI').hidden") == True)
ev("__T.coachCacheWrite('2026-11', __T.coachSig('2026-11'), {headline:'카드값 134만원, 25일 전에 100만원으로', patterns:['p'], loanAdvice:'l', actions:['a']}, 500)")
ev("__T.renderHome()")
check('저장된 AI 진단이 있으면 그 문장',
ev("document.getElementById('coachBarTxt').textContent") == '카드값 134만원, 25일 전에 100만원으로',
      str(ev("document.getElementById('coachBarTxt').textContent")))
check('AI 배지 표시', ev("document.getElementById('coachBarAI').hidden") == False)
check('캐시 신선도 판정', ev("__T.coachCacheFresh(__T.coachCacheRead())") == True)
ev("__T.coachCacheWrite('2026-11', 'old-signature', {headline:'옛 진단', patterns:[], loanAdvice:'', actions:[]}, 100)")
ev("__T.renderHome()")
check('기록이 바뀌면 배너는 다시 규칙 문장',
ev("document.getElementById('coachBarTxt').textContent") == ev("__T.ruleHeadline('2026-11')"))
check('옛 캐시는 신선하지 않음', ev("__T.coachCacheFresh(__T.coachCacheRead())") == False)
ev("localStorage.removeItem(__T.COACH_KEY)")

print('\n[27] AI 코치 시트 렌더')
ev(r'''
(function(){
  var st = __T.blankState();
  st.incomes = [{id:'i1', name:'월급', amount:5300000, day:25, owner:'공동', active:true}];
  st.bills = [
    {id:'L1', name:'주택담보대출', cat:'대출', amount:1120000, day:25, owner:'공동', active:true, balance:268000000, rate:3.8},
    {id:'L2', name:'부산은행 신용대출', cat:'대출', amount:846000, day:12, owner:'공동', active:true, balance:50297289, rate:7.68},
    {id:'L3', name:'햇살론', cat:'대출', amount:148000, day:20, owner:'현기', active:true, balance:1250024, rate:8.83},
    {id:'C1', name:'신한카드', cat:'카드', amount:0, day:14, owner:'공동', active:true, byMonth:{'2026-11':1340000}}
  ];
  st.settings.geminiKey = '';
  __T.state = __T.normalize(st);
})();
''')
try:
    ev("__T.openCoach()")
    body = ev("document.getElementById('coachBody').innerHTML")
    check('시트: 지출 페이스', '이번 달 지출 페이스' in body)
    check('시트: 대출 우선순위', '대출 상환 우선순위' in body and '햇살론' in body and '8.83%' in body, body[:400])
    check('시트: 금리 순 · 현금흐름 순 두 목록', '금리 높은 순' in body and '현금이 가장 트이는 순' in body)
    check('시트: 대출 합계 줄', '대출 3건' in body and '매달' in body, body[-600:])
    check('시트: AI 정밀 진단', 'AI 정밀 진단' in body)
    check('키 없으면 설정 안내', '제미나이 키가 아직 없어요' in body and 'shotkey' in body)
    check('키 없을 때는 진단 버튼 없음', 'coachai' not in body)

    ev("__T.state.settings.geminiKey = 'AIzaTESTKEY1234567890'")
    ev("__T.renderCoach()")
    body2 = ev("document.getElementById('coachBody').innerHTML")
    check('키가 있으면 진단 버튼', 'AI 정밀 진단 받기' in body2 and 'coachai' in body2)
    check('키가 있으면 개인정보 안내', '나만 보기' in body2)

    ev("__T.coachCacheWrite('2026-11', __T.coachSig('2026-11'), {headline:'카드값 134만원부터', patterns:['고정비 73%'], loanAdvice:'햇살론부터', actions:['카드값 줄이기']}, 480)")
    ev("__T.renderCoach()")
    body3 = ev("document.getElementById('coachBody').innerHTML")
    check('저장된 진단 표시', '카드값 134만원부터' in body3 and '읽은 패턴' in body3 and '이번 주 할 일' in body3, body3[-500:])
    check('다시 분석 버튼', '다시 분석' in body3)
    check('분석 시각·속도 표기', '분 전 분석' in body3 or '방금 분석' in body3, body3[-500:])
    check('최신 표시', '최신' in body3)
    ev("localStorage.removeItem(__T.COACH_KEY)")
except Exception as e:
    check('코치 시트 렌더', False, str(e))

print('\n[28] 설계 탭 그래프 렌더')
ev(r'''
(function(){
  var st = __T.blankState();
  st.viewMonth = '2026-11';
  st.incomes = [{id:'i1', name:'월급', amount:5300000, day:25, owner:'공동', active:true}];
  st.bills = [
    {id:'L3', name:'햇살론', cat:'대출', amount:148000, day:20, owner:'현기', active:true, balance:1250024, rate:8.83},
    {id:'L4', name:'자동차 할부', cat:'대출', amount:420000, day:28, owner:'현기', active:true, balance:8400000, rate:0},
    {id:'I1', name:'실손보험', cat:'보험', amount:92000, day:22, owner:'공동', active:true},
    {id:'C1', name:'신한카드', cat:'카드', amount:0, day:14, owner:'공동', active:true, byMonth:{'2026-11':1340000}}
  ];
  __T.state = __T.normalize(st);
})();
''')
try:
    ev("__T.renderPlan()")
    c6 = ev("document.getElementById('chart6').innerHTML")
    check('6개월 그래프가 설계 탭에 들어감', '<svg' in c6 and '11월' in c6)
    check('그래프에 고정비 색', '#3182F6' in c6 and '#FF8A3D' in c6)
    cs = ev("document.getElementById('chartShare').innerHTML")
    check('비중 바 렌더', '<svg' in cs and '<rect' in cs)
    lg = ev("document.getElementById('shareLegend').innerHTML")
    check('범례: 대출/보험·생활/변동·카드', '대출 상환' in lg and '보험·생활' in lg and '변동·카드' in lg, lg[:300])
    check('범례에 금액과 %', '568,000원' in lg and '1,340,000원' in lg and '%' in lg, lg[:400])
    card = ev("document.getElementById('loanRankCard').innerHTML")
    check('대출 우선순위 카드', '대출 정리 우선순위' in card and '햇살론' in card, card[:400])
    check('카드에 Top 2~3 만', card.count('rkrow') == 2, str(card.count('rkrow')))
    check('카드에 현금흐름 한 줄', '현금이 가장 트이는 건' in card, card[-300:])
    check('지출 흐름 헤더(이번 달)', ev("document.getElementById('chartHead').textContent") == '이번 달')
    check('비중 제목(이번 달)', ev("document.getElementById('shareTitle').textContent") == '이번 달 지출 비중')
    ev("__T.state.viewMonth = '2026-09'; __T.renderPlan()")
    check('지난 달을 보고 있으면 그 달을 강조', ev("document.getElementById('chartHead').textContent") == '2026년 9월')
    check('지난 달 비중 제목', ev("document.getElementById('shareTitle').textContent") == '9월 지출 비중')
    ev("__T.state.viewMonth = '2026-11'")
except Exception as e:
    check('설계 탭 그래프 렌더', False, str(e))

print('\n[29] 대출 금리 입력 (시트)')
ev(r'''
(function(){
  var st = __T.blankState();
  st.bills = [];
  __T.state = __T.normalize(st);
})();
''')
try:
    ev("__T.openBill(null, '대출')")
    check('대출: 금리 칸 보임', ev("document.getElementById('bRateField').hidden") == False)
    ev("document.getElementById('bName').value = '햇살론'")
    ev("document.getElementById('bAmount').value = '148,000'")
    ev("document.getElementById('bDay').value = '20'")
    ev("document.getElementById('bBal').value = '1,250,024'")
    ev("document.getElementById('bRate').value = '8.83'")
    ev("__T.saveBill()")
    check('금리 저장', abs(ev("__T.state.bills[0].rate") - 8.83) < 0.001, str(ev("__T.state.bills[0].rate")))
    check('금리 저장 후 순위 계산에 반영', ev("__T.loanRank('rate')[0].rate") == 8.83)
    ev("__T.openBill(null, '보험')")
    check('보험: 금리 칸 숨김', ev("document.getElementById('bRateField').hidden") == True)
    html_loan = ev("__T.planBillRowHTML(__T.state.bills[0], '2026-11')")
    check('대출 줄에 잔액·금리 표시', '남은 잔액 1,250,024원' in html_loan and '금리 8.83%' in html_loan, html_loan[:300])
except Exception as e:
    check('대출 금리 입력', False, str(e))

print('\n[30] 코치 요약(제미나이로 보낼 내용) · 나만 보기 가리기')
ev(r'''
(function(){
  var st = __T.blankState();
  st.incomes = [{id:'i1', name:'월급', amount:5300000, day:25, owner:'공동', active:true}];
  st.bills = [{id:'L3', name:'햇살론', cat:'대출', amount:148000, day:20, owner:'현기', active:true, balance:1250024, rate:8.83}];
  st.txns = [
    {id:'t1', date:'2026-11-18', amount:120000, kind:'expense', cat:'식비', owner:'공동', memo:'이마트 장보기'},
    {id:'t2', date:'2026-11-19', amount:32000, kind:'expense', cat:'식비', owner:'공동', memo:'배달 음식'},
    {id:'t3', date:'2026-11-20', amount:45000, kind:'expense', cat:'여가', owner:'공동', memo:'영화 관람'},
    {id:'t4', date:'2026-11-20', amount:12000, kind:'expense', cat:'기타', owner:'현기', memo:'개인 커피', private:true},
    {id:'t5', date:'2026-11-21', amount:300000, kind:'income', cat:'부수입', owner:'현기', memo:'지인 소개'}
  ];
  __T.state = __T.normalize(st);
})();
''')
try:
    sumj = _json.loads(ev("JSON.stringify(__T.coachSummary('2026-11'))"))
    check('요약: 이번 달 이름', sumj['month'] == '2026년 11월', str(sumj.get('month')))
    check('요약: 수입(고정 수입 + 기타 수입)', sumj['income'] == 5600000, str(sumj['income']))
    check('요약: 고정비/카드/변동', sumj['fixed']['total'] == 148000 and sumj['cardBillThisMonth'] == 0 and sumj['variableSpend'] == 209000, str(sumj))
    check('요약: 대출 금리·잔액 포함', sumj['loans'][0]['rate'] == 8.83 and sumj['loans'][0]['balance'] == 1250024)
    cats = {c['cat']: c['amount'] for c in sumj['categories']}
    check('요약: 카테고리 합계', cats.get('식비') == 152000 and cats.get('여가') == 45000, str(cats))
    check('요약: 카테고리 합계 = 변동 지출', sum(c['amount'] for c in sumj['categories']) == sumj['variableSpend'], str(sumj['categories']))
    mercs = [m['name'] for m in sumj['merchants']]
    check('요약: 자주 쓴 곳', '이마트 장보기' in mercs, str(mercs))
    check('나만 보기 내용은 보내지 않음', '개인 커피' not in mercs, str(mercs))
    check('주중/주말 합계', sumj['weekdaySpend'] + sumj['weekendSpend'] == 120000 + 32000 + 45000 + 12000, str(sumj))
    check('전달 달 비교', sumj['prevMonth']['month'] == '2026년 10월')
    pr = ev("__T.coachPrompt(__T.coachSummary('2026-11'))")
    check('프롬프트에 JSON 요청 형식', 'headline' in pr and 'loanAdvice' in pr and 'actions' in pr)
    check('프롬프트에 요약 JSON 이 붙음', '"month":"2026년 11월"' in pr)
except Exception as e:
    check('코치 요약', False, str(e))

print('\n==== %s ====' % ('ALL PASS' if not fails else ('FAILED: ' + ', '.join(fails))))
sys.exit(1 if fails else 0)
