"""Run index.html's script in QuickJS with a tiny DOM stub and exercise the main flows."""
import re, json, sys
import quickjs

html = open('index.html', encoding='utf-8').read()
js = re.search(r'<script>([\s\S]*)</script>', html).group(1)

STUB = r"""
var __els = {}, __docHandlers = {};
function El(id){
  this.id = id || '';
  this.textContent = ''; this.innerHTML = ''; this.value = ''; this.hidden = false;
  this.style = {}; this.className = ''; this.children = []; this.attrs = {}; this.files = null;
  this._h = {};
  var s = new Set();
  this.classList = {
    add: function(c){ s.add(c); }, remove: function(c){ s.delete(c); },
    toggle: function(c, f){ if (f === undefined){ s.has(c) ? s.delete(c) : s.add(c); }
      else if (f) { s.add(c); } else { s.delete(c); } },
    contains: function(c){ return s.has(c); }
  };
}
El.prototype.addEventListener = function(t, fn){ (this._h[t] = this._h[t] || []).push(fn); };
El.prototype.setAttribute = function(k, v){ this.attrs[k] = String(v); };
El.prototype.getAttribute = function(k){ return this.attrs[k] === undefined ? null : this.attrs[k]; };
El.prototype.querySelector = function(){ return null; };
El.prototype.querySelectorAll = function(){ return []; };
El.prototype.focus = function(){};
El.prototype.blur = function(){};
El.prototype.click = function(){};
El.prototype.remove = function(){};
El.prototype.appendChild = function(){};

var document = {
  readyState: 'complete',
  body: new El('body'),
  head: new El('head'),
  getElementById: function(id){ return __els[id] || (__els[id] = new El(id)); },
  querySelector: function(){ return null; },
  querySelectorAll: function(){ return []; },
  createElement: function(t){ return new El(t); },
  addEventListener: function(t, fn){ (__docHandlers[t] = __docHandlers[t] || []).push(fn); }
};
var window = this;
window.scrollTo = function(){};
window.addEventListener = function(){};
var navigator = {};
var localStorage = {
  _m: {},
  getItem: function(k){ return this._m[k] === undefined ? null : this._m[k]; },
  setItem: function(k, v){ this._m[k] = String(v); },
  removeItem: function(k){ delete this._m[k]; }
};
var setTimeout = function(){ return 0; };
var clearTimeout = function(){};
var URL = { createObjectURL: function(){ return 'blob:x'; }, revokeObjectURL: function(){} };
var FileReader = function(){ this.readAsText = function(){}; };
var Blob = function(){};
"""

def run():
    ctx = quickjs.Context()
    ctx.eval(STUB)
    ctx.eval(js)

    def val(expr):
        return ctx.eval(expr)

    out = {}
    # --- home ---
    out['homeFree'] = val("document.getElementById('homeFreeNum').textContent")
    out['homeIncome'] = val("document.getElementById('homeIncome').textContent")
    out['homeSpent'] = val("document.getElementById('homeSpent').textContent")
    out['homeFixed'] = val("document.getElementById('homeFixed').textContent")
    out['homeUsed'] = val("document.getElementById('homeUsed').textContent")
    out['homeBar'] = val("document.getElementById('homeBar').style.width")
    out['upTotal'] = val("document.getElementById('upTotal').textContent")
    up_html = val("document.getElementById('upcoming').innerHTML")
    out['upcomingRows'] = up_html.count('class=\"bill')
    out['upcomingHasMortgage'] = '주택담보대출' in up_html
    out['ownerSplitRows'] = val("document.getElementById('ownerSplit').innerHTML").count('orow')

    # --- list ---
    out['monthLabel'] = val("document.getElementById('monthLabel').textContent")
    out['lstIncome'] = val("document.getElementById('lstIncome').textContent")
    out['lstExpense'] = val("document.getElementById('lstExpense').textContent")
    out['lstLeft'] = val("document.getElementById('lstLeft').textContent")
    out['txnRows'] = val("document.getElementById('txnList').innerHTML").count('class=\"txn\"')
    out['listEmpty'] = val("document.getElementById('listEmpty').hidden")

    # --- plan ---
    out['plIncome'] = val("document.getElementById('plIncome').textContent")
    out['plFixed'] = val("document.getElementById('plFixed').textContent")
    out['plSave'] = val("document.getElementById('plSave').textContent")
    out['plSavePct'] = val("document.getElementById('plSavePct').textContent")
    out['plNet'] = val("document.getElementById('plNet').textContent")
    out['lgFixed'] = val("document.getElementById('lgFixed').textContent")
    out['billRows'] = val("document.getElementById('billList').innerHTML").count('class=\"bill')

    # --- click: pay a bill ---
    ctx.eval("""
    function clickAct(act, extra){
      var attrs = {'data-act': act};
      if (extra) for (var k in extra) attrs[k] = extra[k];
      var target = { closest: function(sel){
        if (sel === '[data-act]') return { getAttribute: function(k){ return attrs[k] === undefined ? null : attrs[k]; } };
        return null; } };
      __docHandlers['click'].forEach(function(fn){ fn({ target: target }); });
    }
    """)
    before = val("document.getElementById('homeFixed').textContent")
    ctx.eval("clickAct('pay', {'data-id':'b1'})")
    out['afterPay_fixed'] = val("document.getElementById('homeFixed').textContent")
    out['afterPay_free'] = val("document.getElementById('homeFreeNum').textContent")
    out['afterPay_txns'] = val("document.getElementById('txnList').innerHTML").count('class=\"txn\"')
    out['payChangedTotal'] = before != out['afterPay_fixed']
    # undo
    ctx.eval("clickAct('pay', {'data-id':'b1'})")
    out['undoPay_fixed'] = val("document.getElementById('homeFixed').textContent")
    out['undoRestored'] = out['undoPay_fixed'] == before

    # --- tab switch ---
    ctx.eval("clickAct('tab', {'data-view':'plan'})")
    out['planViewOn'] = val("document.getElementById('view-plan').classList.contains('on')")
    out['homeViewOff'] = not val("document.getElementById('view-home').classList.contains('on')")

    # --- quick entry: open, fill, save ---
    ctx.eval("clickAct('quick')")
    out['quickOpen'] = val("document.getElementById('shQuick').classList.contains('open')")
    out['quickCats'] = val("document.getElementById('qCats').innerHTML").count('chip soft')
    ctx.eval("document.getElementById('qAmount').value = '12,500'")
    ctx.eval("document.getElementById('qMemo').value = '테스트 김밥'")
    ctx.eval("document.getElementById('qDate').value = document.getElementById('qDate').value || '2026-11-21'")
    txn_before = val("document.getElementById('txnList').innerHTML").count('class=\"txn\"')
    ctx.eval("__els['qSave']._h['click'].forEach(function(fn){ fn({}); })")
    out['quickClosed'] = not val("document.getElementById('shQuick').classList.contains('open')")
    out['afterSave_hasMemo'] = '테스트 김밥' in val("document.getElementById('txnList').innerHTML")
    out['afterSave_rows'] = val("document.getElementById('txnList').innerHTML").count('class=\"txn\"')
    out['savedIntoStorage'] = '테스트 김밥' in val("localStorage.getItem('couple-budget-v1')")

    # --- settings sheet ---
    ctx.eval("clickAct('settings')")
    out['settingsOpen'] = val("document.getElementById('shSet').classList.contains('open')")
    out['statusText'] = val("document.getElementById('sStatus').textContent")

    # --- month nav ---
    ctx.eval("clickAct('month', {'data-dir':'-1'})")
    out['prevMonth'] = val("document.getElementById('monthLabel').textContent")
    ctx.eval("clickAct('month', {'data-dir':'1'})")
    out['backMonth'] = val("document.getElementById('monthLabel').textContent")

    # --- owner filter ---
    ctx.eval("clickAct('owner', {'data-owner':'현기'})")
    hy = val("document.getElementById('txnList').innerHTML")
    out['filterHyeongiRows'] = hy.count('class=\"txn\"')
    out['filterOnlyHyeongi'] = ('장미' not in hy)
    ctx.eval("clickAct('owner', {'data-owner':'전체'})")
    out['allRows'] = val("document.getElementById('txnList').innerHTML").count('class=\"txn\"')

    return out

if __name__ == '__main__':
    try:
        res = run()
        for k, v in res.items():
            print(f"{k:26} {v}")
    except Exception as e:
        print("RUNTIME ERROR:", type(e).__name__, str(e)[:1500])
        sys.exit(1)
