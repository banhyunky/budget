/**
 * 머니로그 문자·알림 수집 웹훅 (Google Apps Script)
 * ------------------------------------------------------------------
 * 폰(MacroDroid) → 이 웹앱(doPost) → Firestore(households/hy-vtrxxa8dq6)
 *
 * · 문자(SMS)와 앱 알림을 받아 금액·종류·가맹점을 읽고 가계부에 한 건 추가한다.
 * · 같은 결제의 문자+알림이 3분 안에 둘 다 오면 한 건만 남긴다.
 * · 부부(현기↔장미)끼리 오간 이체는 kind:'transfer' 로 기록해 수입·지출 집계에서 뺀다.
 * · 두 폰이 같은 이체를 각각 보내도(둘 다 이미 '이체'로 읽혀도) 10분 안이면 한 줄만 남긴다.
 *
 * 설정 방법은 같은 폴더의 SETUP.md 참고.
 * 수정 후에는 [배포] → [배포 관리] → 연필 → 버전 '새 버전' → 배포 를 다시 해야 반영된다.
 */

/* ======================= 설정 (여기만 고치면 됩니다) ======================= */
var CFG = {
  /* 1) 비밀값: 반드시 본인만 아는 값으로 바꾸세요(20자 이상 권장).
        MacroDroid 의 HTTP 요청 본문에도 같은 값을 넣습니다. */
  SECRET: 'CHANGE_ME_moneylog_2026',

  /* 2) 머니로그가 쓰는 Firebase 프로젝트와 가계부 ID (앱 설정의 '가계부 ID'와 같습니다) */
  PROJECT_ID: 'banhyunky-budget',
  HOUSE_ID: 'hy-vtrxxa8dq6',

  /* 3) 판정 범위: 같은 결제의 문자+알림 중복(3분), 부부 이체 짝(10분) */
  DUP_WINDOW_MS: 3 * 60 * 1000,
  PAIR_WINDOW_MS: 10 * 60 * 1000,

  VERSION: '1.1.0'
};

/* ============================== 상수 ============================== */
var SPOUSE = { '현기': '장미', '장미': '현기' };   /* 내 이름 → 배우자 이름 */
var OWNERS = ['현기', '장미', '공동'];
var TRANSFER_CAT = '이체';

var RE_OTP = /(인증\s*번호|인증번호|OTP|비밀\s*번호|보안\s*코드|승인\s*번호)/;
var RE_CANCEL = /(승인\s*취소|결제\s*취소|매입\s*취소|취소|거절|실패)/;
var RE_INCOME = /(입금|받았|받으셨|받음|받기\s*완료|충전|환불|이자|급여|월급|상여)/;
var RE_EXPENSE = /(출금|결제|승인|사용|자동\s*이체|이체|송금|보냈|보냄|납부|인출|할부)/;
/* 돈이 '움직였다'는 표시 — 부부 이체 짝을 맞출 때 쓴다(카드 승인에는 없음) */
var RE_MOVED = /(이체|송금|보냈|보냄|보내|받았|받음|받기|출금|입금|인출)/;
var RE_CARD_OK = /(승인|일시불|할부|결제)/;
var RE_AD = /(광고|이벤트|혜택|쿠폰|추천|당첨|무료|리워드|포인트\s*적립)/;

/* ============================== 웹훅 입구 ============================== */
function doPost(e) {
  try {
    if (String(CFG.SECRET).indexOf('CHANGE_ME') === 0) {
      return out({ ok: false, error: 'secret_not_set' });
    }
    var p = readPayload(e);
    if (!p) return out({ ok: false, error: 'empty_body' });
    if (String(p.secret || '') !== String(CFG.SECRET)) {
      return out({ ok: false, error: 'bad_secret' });
    }
    return out(ingest(p));
  } catch (err) {
    return out({ ok: false, error: String((err && err.message) || err) });
  }
}

/* 브라우저로 열었을 때 살아 있는지 확인하는 용도 (가계부 내용은 내보내지 않음) */
function doGet(e) {
  return out({
    ok: true,
    name: 'moneylog-webhook',
    version: CFG.VERSION,
    house: CFG.HOUSE_ID,
    time: kstString(Date.now())
  });
}

/* MacroDroid 는 application/json 으로 보내지만, 가끔 form-urlencoded 로도 온다.
   문자 본문에 줄바꿈이 들어가면 JSON 이 깨지므로 그 경우까지 받아 준다. */
function readPayload(e) {
  if (!e) return null;
  var body = e.postData && e.postData.contents;
  if (body) {
    var s = String(body);
    try { return JSON.parse(s); } catch (err) {}
    try { return JSON.parse(s.replace(/[\r\n\t]+/g, ' ').replace(/[\u0000-\u001f]/g, ' ')); } catch (err1) {}
    try {
      var loose = looseFields(s);
      if (loose) return loose;
    } catch (err2) {}
    try {
      if (s.indexOf('=') >= 0) {
        var o = {}, parts = s.split('&');
        for (var i = 0; i < parts.length; i++) {
          var kv = parts[i].split('=');
          if (!kv[0]) continue;
          o[decodeURIComponent(kv[0])] = decodeURIComponent(String(kv[1] || '').replace(/\+/g, ' '));
        }
        if (o.secret !== undefined || o.text !== undefined) return o;
      }
    } catch (err3) {}
  }
  if (e.parameter && (e.parameter.secret !== undefined || e.parameter.text !== undefined)) {
    return e.parameter;
  }
  return null;
}

/* 깨진 JSON 에서 키·값만 느슨하게 뽑아낸다 (값 안의 줄바꿈 허용) */
function looseFields(s) {
  var keys = ['secret', 'owner', 'source', 'app', 'title', 'text', 'at'];
  var o = {}, found = 0;
  for (var i = 0; i < keys.length; i++) {
    var k = keys[i];
    var re = new RegExp('"' + k + '"\\s*:\\s*"([\\s\\S]*?)"\\s*[,}]');
    var m = s.match(re);
    if (m) { o[k] = m[1]; found++; }
  }
  return found >= 2 ? o : null;
}

function out(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

/* ============================== 한 건 처리 ============================== */
function ingest(p) {
  var owner = normOwner(p.owner);
  var text = joinText(p);
  var at = parseAt(p.at) || Date.now();
  var src = String(p.source || '');
  var app = String(p.app || '');

  var parsed = parseMessage(text, owner);
  if (parsed.skip) {
    return { ok: true, status: 'ignored', reason: parsed.reason, at: kstString(at) };
  }

  var cand = {
    id: newId(),
    date: kstDate(at),
    amount: parsed.amount,
    kind: parsed.kind,
    cat: parsed.cat,
    owner: parsed.owner,
    memo: parsed.memo,
    private: false,
    at: at,
    mv: !!parsed.moved,
    src: src,
    app: app
  };

  var lock = LockService.getScriptLock();
  if (!lock.tryLock(20000)) return { ok: false, error: 'busy' };
  try {
    var lastErr = '';
    for (var attempt = 0; attempt < 3; attempt++) {
      var doc;
      try { doc = getDoc(); } catch (e1) { lastErr = String(e1.message || e1); break; }
      var fields = doc.fields && doc.fields.data && doc.fields.data.mapValue && doc.fields.data.mapValue.fields;
      if (!fields) return { ok: false, error: 'data_field_missing' };

      var box = decodeTxns(fields);
      var js = box.js;

      /* 1) 같은 폰에서 같은 결제가 문자+알림으로 두 번 온 경우 */
      var si = findSame(js, cand);
      if (si >= 0) {
        var same = js[si];
        if (cand.kind === 'transfer' && same.kind !== 'transfer') {
          same.kind = 'transfer';
          same.cat = TRANSFER_CAT;
          same.memo = cand.memo;
          same.mv = true;
          if (writeTxns(doc, fields, box, si)) {
            return { ok: true, status: 'upgraded', id: same.id, kind: 'transfer', amount: same.amount };
          }
          continue;
        }
        return { ok: true, status: 'duplicate', id: same.id, kind: same.kind, amount: same.amount };
      }

      /* 2) 배우자 폰에서 같은 금액이 잡힌 경우 = 같은 이체 (한 줄만 남긴다) */
      var pi = findPair(js, cand);
      if (pi >= 0) {
        var mate = js[pi];
        if (mate.kind === 'transfer') {
          /* 두 폰 모두 이미 '이체'로 읽힌 같은 부부 이체 — 새 줄을 만들지 않는다 */
          var st = (cand.kind === 'transfer') ? 'merged' : 'duplicate';
          return { ok: true, status: st, id: mate.id, kind: 'transfer', amount: mate.amount };
        }
        mate.kind = 'transfer';
        mate.cat = TRANSFER_CAT;
        mate.memo = mate.owner && SPOUSE[mate.owner] ? (mate.owner + ' ↔ ' + SPOUSE[mate.owner]) : '부부 이체';
        mate.mv = true;
        if (writeTxns(doc, fields, box, pi)) {
          return { ok: true, status: 'paired', id: mate.id, kind: 'transfer', amount: mate.amount };
        }
        continue;
      }

      /* 3) 새 기록 */
      box.rawValues.push(encVal(cand));
      if (writeTxns(doc, fields, box, -1)) {
        return {
          ok: true, status: 'added', id: cand.id, kind: cand.kind, amount: cand.amount,
          cat: cand.cat, memo: cand.memo, owner: cand.owner, date: cand.date
        };
      }
    }
    return { ok: false, error: 'conflict_retry_failed', detail: lastErr };
  } finally {
    lock.releaseLock();
  }
}

function joinText(p) {
  var s = [String(p.title || ''), String(p.text || '')].join(' ').replace(/\s+/g, ' ').trim();
  if (!s) s = String(p.app || '').trim();
  return s;
}

function normOwner(v) {
  var s = String(v || '').trim();
  for (var i = 0; i < OWNERS.length; i++) if (s === OWNERS[i]) return s;
  if (/장미/.test(s)) return '장미';
  if (/현기/.test(s)) return '현기';
  return '공동';
}

function newId() {
  return 'x' + Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
}

/* ============================== 문자·알림 해석 ============================== */
/**
 * 문구 하나를 읽어 { skip, reason } 또는
 * { amount, kind, cat, memo, owner, moved, spouse } 를 돌려준다.
 */
function parseMessage(text, ownerName) {
  var t = cleanText(text);
  var owner = normOwner(ownerName);
  if (!t) return { skip: true, reason: 'empty' };
  if (RE_OTP.test(t)) return { skip: true, reason: 'otp' };
  if (RE_CANCEL.test(t)) return { skip: true, reason: 'cancel' };

  var am = findAmount(t);
  if (!am) return { skip: true, reason: 'no_amount' };

  var spouse = detectSpouse(t, owner);
  var cardish = RE_CARD_OK.test(t) && !/이체|송금/.test(t);
  var moved = RE_MOVED.test(t);
  var transfer = !!spouse && moved && !cardish;

  var kind;
  if (transfer) kind = 'transfer';
  else if (RE_INCOME.test(t)) kind = am.sign < 0 ? 'expense' : 'income';
  else if (RE_EXPENSE.test(t)) kind = 'expense';
  else if (RE_AD.test(t)) return { skip: true, reason: 'ad' };
  else return { skip: true, reason: 'no_kind' };

  var memo;
  if (kind === 'transfer') {
    memo = owner === '공동' ? '부부 이체' : (owner + ' ↔ ' + spouse);
  } else {
    memo = extractMerchant(t) || (kind === 'income' ? '입금' : '결제');
    if (memo.length > 24) memo = memo.slice(0, 24).replace(/\s+$/, '');
  }

  return {
    skip: false,
    amount: am.value,
    kind: kind,
    cat: kind === 'transfer' ? TRANSFER_CAT : guessCat(t, memo, kind),
    memo: memo,
    owner: owner,
    moved: moved,
    spouse: spouse
  };
}

function cleanText(v) {
  return String(v || '')
    .replace(/[\u200b-\u200d\ufeff]/g, '')
    .replace(/\r/g, ' ')
    .replace(/\n/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

/* 금액: '1,000원' '1000원' '-1,000원' — 잔액·누적·한도 숫자는 건너뛴다 */
function findAmount(t) {
  var re = /([-+]?)\s?(\d[\d,]*)\s*원/g, m;
  while ((m = re.exec(t)) !== null) {
    var before = t.slice(Math.max(0, m.index - 8), m.index);
    if (/(잔액|누적|한도|잔여|포인트|한도액)/.test(before)) continue;
    var v = parseInt(String(m[2]).replace(/,/g, ''), 10);
    if (!v || v <= 0 || v > 1000000000) continue;
    return { value: v, sign: m[1] === '-' ? -1 : 1, raw: m[0] };
  }
  return null;
}

/* 내 폰 기준 배우자 이름이 문구에 있는지 */
function detectSpouse(t, owner) {
  var want = SPOUSE[owner];
  if (want) return t.indexOf(want) >= 0 ? want : '';
  if (/장미/.test(t)) return '장미';
  if (/반현기|현기/.test(t)) return '현기';
  return '';
}

/* 가맹점·메모 뽑기: 브랜드·금액·날짜·잔액·동작 동사를 걷어낸 나머지 */
function extractMerchant(t) {
  var s = ' ' + t + ' ';
  s = s.replace(/\[[^\]]*\]/g, ' ');
  s = s.replace(/\([^)]*\)/g, ' ');
  s = s.replace(/(잔액|누적|한도|잔여|포인트)[^0-9]{0,6}[\d,]+\s*(원|점|P)?/g, ' ');
  s = s.replace(/[+\-]?\d[\d,]*\s*원/g, ' ');
  s = s.replace(/\d{4}[.\-\/]\d{1,2}[.\-\/]\d{1,2}/g, ' ');
  s = s.replace(/\d{1,2}\s*[\/.]\s*\d{1,2}(\s+\d{1,2}:\d{2})?/g, ' ');
  s = s.replace(/\d{1,2}:\d{2}(:\d{2})?/g, ' ');
  s = s.replace(/(승인취소|승인|취소|일시불|할부|체크|출금|입금|이체|송금|보냈어요|보냈습니다|보냄|보냈|받았어요|받았습니다|받음|결제|자동이체|완료|안내|Web발신|국제발신)/g, ' ');
  s = s.replace(/(님에게|님께|님한테|에게서|에게|께서|으로부터|로부터)/g, ' ');
  s = s.replace(/\S*(카드|은행|뱅크|페이|증권|캐피탈|저축은행|생명|화재)\S*/g, ' ');
  s = s.replace(/(^|\s)(을|를|이|가|은|는|의|에|도|만|와|과)(\s|$)/g, ' ');
  s = s.replace(/(^|\s)\d{2,}(\s|$)/g, ' ');
  s = s.replace(/[|·:;,\/\-_.~'"“”‘’]/g, ' ');
  s = s.replace(/\s+/g, ' ').trim();
  return s;
}

var CAT_RULES = [
  [/경조사|축의|조의|부조/, '경조사'],
  [/대출|상환|원리금|이자\s*납부/, '대출'],
  [/보험|실손|생명|화재/, '보험'],
  [/통신|SKT|KT|LGU|유플러스|인터넷|휴대폰|알뜰폰|요금/, '통신'],
  [/월세|관리비|전기|가스|수도|공과금|주택/, '주거'],
  [/병원|의원|약국|치과|한의원|의료/, '의료'],
  [/학원|교육|교재|인강|학교/, '교육'],
  [/CGV|메가박스|영화|넷플릭스|유튜브|게임|노래방|여가/, '여가'],
  [/버스|지하철|택시|카카오\s*T|주유|기름|주차|통행료|KTX|SRT|철도|교통/, '교통'],
  [/스타벅스|카페|커피|식당|김밥|치킨|배달|편의점|GS25|CU|이마트|홈플러스|쿠팡|마트|빵|제과|분식|고기|식비/, '식비'],
  [/다이소|올리브영|무신사|생활|렌탈|정수기|세탁/, '생활']
];

function guessCat(text, memo, kind) {
  var s = String(text || '') + ' ' + String(memo || '');
  if (kind === 'income') {
    if (/급여|월급|상여/.test(s)) return '급여';
    if (/이자/.test(s)) return '이자';
    if (/부수입|외주|프리랜서/.test(s)) return '부수입';
    return '기타';
  }
  for (var i = 0; i < CAT_RULES.length; i++) if (CAT_RULES[i][0].test(s)) return CAT_RULES[i][1];
  return '기타';
}

/* ============================== 중복·짝 판정 ============================== */
function kindOf(t) {
  if (!t) return '';
  if (t.kind === 'transfer') return 'transfer';
  if (t.kind === 'income') return 'income';
  return 'expense';
}

/* 같은 폰·같은 결제(문자+알림). 이체가 더 정확하면 그쪽으로 정리한다 */
function findSame(txns, cand) {
  for (var i = txns.length - 1; i >= 0; i--) {
    var t = txns[i];
    if (!t || !t.at) continue;
    if (+t.amount !== +cand.amount) continue;
    if (normOwner(t.owner) !== cand.owner) continue;
    if (Math.abs(+t.at - cand.at) > CFG.DUP_WINDOW_MS) continue;
    var k = kindOf(t);
    if (k === cand.kind) return i;
    if (k === 'transfer' || cand.kind === 'transfer') return i;
  }
  return -1;
}

/* 배우자 폰에서 같은 금액이 잡힌 경우 = 같은 이체 한 건
   · 방향이 반대(입금↔출금)면 짝으로 묶는다.
   · 둘 다 이미 '이체'면(각 폰이 배우자 이름을 다 읽은 경우) 같은 이체로 보고 합친다. */
function findPair(txns, cand) {
  for (var i = txns.length - 1; i >= 0; i--) {
    var t = txns[i];
    if (!t || !t.at) continue;
    if (+t.amount !== +cand.amount) continue;
    if (normOwner(t.owner) === cand.owner) continue;
    if (Math.abs(+t.at - cand.at) > CFG.PAIR_WINDOW_MS) continue;
    if (!cand.mv || !t.mv) continue;              /* 카드 승인처럼 돈이 '이체'로 움직인 문구만 */
    if (kindOf(t) === kindOf(cand)) {
      if (cand.kind === 'transfer' && kindOf(t) === 'transfer') return i;  /* 같은 부부 이체 */
      continue;                                   /* 그 밖에는 방향이 반대여야 함 */
    }
    return i;
  }
  return -1;
}

/* ============================== Firestore ============================== */
function docUrl() {
  return 'https://firestore.googleapis.com/v1/projects/' + CFG.PROJECT_ID +
    '/databases/(default)/documents/households/' + CFG.HOUSE_ID;
}

function getDoc() {
  var res = UrlFetchApp.fetch(docUrl(), { method: 'get', muteHttpExceptions: true });
  var code = res.getResponseCode();
  if (code !== 200) throw new Error('가계부 문서를 읽지 못했어요 (' + code + ') ' + res.getContentText().slice(0, 160));
  return JSON.parse(res.getContentText());
}

/* 필드 두 개(data, updatedAt)만 갱신한다. 앱의 onSnapshot 이 바로 반영한다. */
function writeTxns(doc, fields, box, changedIndex) {
  if (changedIndex >= 0 && changedIndex < box.js.length) {
    box.rawValues[changedIndex] = encVal(box.js[changedIndex]);
  }
  fields.txns = { arrayValue: { values: box.rawValues } };

  var body = {
    fields: {
      data: { mapValue: { fields: fields } },
      updatedAt: { integerValue: String(Date.now()) }
    }
  };
  var url = docUrl() + '?updateMask.fieldPaths=data&updateMask.fieldPaths=updatedAt';
  if (doc.updateTime) url += '&currentDocument.updateTime=' + encodeURIComponent(doc.updateTime);

  var res = UrlFetchApp.fetch(url, {
    method: 'patch',
    contentType: 'application/json',
    payload: JSON.stringify(body),
    muteHttpExceptions: true
  });
  var code = res.getResponseCode();
  if (code === 200) return true;
  var txt = res.getContentText();
  /* 그 사이 폰이 먼저 저장했으면 다시 읽고 재시도 */
  if (code === 409 || code === 400 || /FAILED_PRECONDITION|ABORTED/.test(txt)) return false;
  throw new Error('가계부에 쓰지 못했어요 (' + code + ') ' + txt.slice(0, 160));
}

/* txns 배열을 '원본 Firestore 값'과 'JS 객체' 두 벌로 읽는다.
   건드리지 않은 기록은 원본을 그대로 되돌려 보내 타입이 바뀌지 않게 한다. */
function decodeTxns(fields) {
  var arr = (fields && fields.txns && fields.txns.arrayValue && fields.txns.arrayValue.values) || [];
  var raw = [], js = [];
  for (var i = 0; i < arr.length; i++) {
    raw.push(arr[i]);
    js.push(decVal(arr[i]) || {});
  }
  return { rawValues: raw, js: js };
}

function decVal(v) {
  if (v === null || v === undefined) return null;
  if (v.stringValue !== undefined) return v.stringValue;
  if (v.integerValue !== undefined) return Number(v.integerValue);
  if (v.doubleValue !== undefined) return Number(v.doubleValue);
  if (v.booleanValue !== undefined) return !!v.booleanValue;
  if (v.nullValue !== undefined) return null;
  if (v.timestampValue !== undefined) return v.timestampValue;
  if (v.arrayValue) {
    var a = v.arrayValue.values || [];
    return a.map(decVal);
  }
  if (v.mapValue) return decMap(v.mapValue.fields || {});
  return null;
}
function decMap(fields) {
  var o = {};
  for (var k in fields) { if (fields.hasOwnProperty(k)) o[k] = decVal(fields[k]); }
  return o;
}

function encVal(x) {
  if (x === null || x === undefined) return { nullValue: null };
  if (typeof x === 'string') return { stringValue: x };
  if (typeof x === 'boolean') return { booleanValue: x };
  if (typeof x === 'number') {
    if (!isFinite(x)) return { nullValue: null };
    return (Math.floor(x) === x) ? { integerValue: String(x) } : { doubleValue: x };
  }
  if (Object.prototype.toString.call(x) === '[object Array]') {
    var vals = [];
    for (var i = 0; i < x.length; i++) vals.push(encVal(x[i]));
    return { arrayValue: { values: vals } };
  }
  var f = {};
  for (var k in x) { if (x.hasOwnProperty(k) && x[k] !== undefined) f[k] = encVal(x[k]); }
  return { mapValue: { fields: f } };
}

/* ============================== 시간 ============================== */
/* 서버 시간대와 무관하게 항상 한국 시간으로 계산한다 */
function kstParts(ms) {
  var d = new Date(ms + 9 * 3600 * 1000);
  return {
    y: d.getUTCFullYear(), m: d.getUTCMonth() + 1, d: d.getUTCDate(),
    hh: d.getUTCHours(), mi: d.getUTCMinutes(), ss: d.getUTCSeconds()
  };
}
function p2(n) { return n < 10 ? '0' + n : '' + n; }
function kstDate(ms) { var p = kstParts(ms); return p.y + '-' + p2(p.m) + '-' + p2(p.d); }
function kstString(ms) {
  var p = kstParts(ms);
  return kstDate(ms) + ' ' + p2(p.hh) + ':' + p2(p.mi) + ':' + p2(p.ss);
}

/* at: '2026-11-21 12:34:56' (한국 시간) 또는 밀리초 숫자. 이상하면 지금 시각. */
function parseAt(v) {
  if (v === null || v === undefined || v === '') return 0;
  var now = Date.now();
  var s = String(v).trim();
  if (/^\d{12,}$/.test(s)) {
    var n = Number(s);
    if (n > now - 86400000 && n < now + 86400000) return n;
    return 0;
  }
  var m = s.match(/^(\d{4})[-.\/](\d{1,2})[-.\/](\d{1,2})(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?)?/);
  if (m) {
    var ms = Date.UTC(+m[1], +m[2] - 1, +m[3], +(m[4] || 0), +(m[5] || 0), +(m[6] || 0)) - 9 * 3600 * 1000;
    if (Math.abs(ms - now) < 3 * 86400000) return ms;
  }
  return 0;
}

/* ============================== 편집기에서 확인 ============================== */
function testParse() {
  var cases = [
    { owner: '현기', text: '[신한카드] 승인 14,800원 스타벅스 11/21 12:34', kind: 'expense', amount: 14800 },
    { owner: '현기', text: '[KB국민카드] 11/21 12:34 승인 15,000원 이마트 1234', kind: 'expense', amount: 15000 },
    { owner: '현기', text: '토스 1,000원을 보냈어요', kind: 'expense', amount: 1000 },
    { owner: '현기', text: '장미님에게 1,000원을 보냈어요', kind: 'transfer', amount: 1000 },
    { owner: '장미', text: '반현기님이 1,000원을 보냈어요', kind: 'transfer', amount: 1000 },
    { owner: '현기', text: '신한은행 11/21 12:34 1,000원 출금 장미 잔액 1,234,567원', kind: 'transfer', amount: 1000 },
    { owner: '장미', text: 'NH농협 1,000원 입금 반현기 잔액 123,456원', kind: 'transfer', amount: 1000 },
    { owner: '현기', text: '[현대카드] 승인취소 5,000원 스타벅스', skip: true },
    { owner: '현기', text: '삼성페이 5,000원 결제 스타벅스', kind: 'expense', amount: 5000 },
    { owner: '현기', text: '자동이체 92,000원 출금 실손보험', kind: 'expense', amount: 92000 },
    { owner: '현기', text: '카카오뱅크 1,000원 이체 장미 잔액 500,000원', kind: 'transfer', amount: 1000 },
    { owner: '현기', text: '인증번호 [123456] 을 입력해 주세요', skip: true },
    { owner: '현기', text: '1,000원 출금 잔액 1,234,567원', kind: 'expense', amount: 1000 },
    { owner: '현기', text: '1,000원 입금 반현기', kind: 'transfer', amount: 1000 }
  ];
  var lines = ['=== 머니로그 문자 해석 테스트 ==='], pass = 0, fail = 0;
  for (var i = 0; i < cases.length; i++) {
    var c = cases[i];
    var r = parseMessage(c.text, c.owner);
    var ok;
    if (c.skip) ok = !!r.skip;
    else ok = (!r.skip && r.amount === c.amount && r.kind === c.kind);
    if (ok) pass++; else fail++;
    lines.push((ok ? 'OK   ' : 'FAIL ') + '[' + c.owner + '] ' + c.text +
      '\n      → ' + JSON.stringify(r));
  }
  lines.push('=== 통과 ' + pass + ' / 실패 ' + fail + ' ===');
  Logger.log(lines.join('\n'));
  return { pass: pass, fail: fail };
}

/* Firestore 읽기만 확인한다(가계부는 건드리지 않음) */
function testFirestore() {
  var doc = getDoc();
  var fields = doc.fields && doc.fields.data && doc.fields.data.mapValue && doc.fields.data.mapValue.fields;
  var box = decodeTxns(fields);
  var msg = '가계부 문서 확인: households/' + CFG.HOUSE_ID + ' · 기록 ' + box.js.length + '건 · 수정시각 ' + (doc.updateTime || '');
  Logger.log(msg);
  return msg;
}
