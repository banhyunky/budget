// 화면 파일을 폰에 저장해 두고 인터넷이 없어도 열리게 하는 서비스워커 (가계 데이터는 건드리지 않음)
// 전략: 항상 최신 파일을 먼저 받아오고(네트워크 우선), 인터넷이 안 될 때만 저장된 파일을 보여줌
// 화면을 고쳐 올린 뒤에는 아래 V 숫자를 올리면 예전 캐시가 정리됩니다.
const V = 'budget-v12';
const FILES = ['./', 'index.html', 'manifest.json', 'icon-192.png', 'icon-512.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(V).then(c => c.addAll(FILES)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(ks => Promise.all(ks.filter(k => k !== V).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const r = e.request;
  if (r.method !== 'GET') return;
  if (new URL(r.url).origin !== location.origin) return;   // Firebase·구글 서버 호출은 그대로 통과
  e.respondWith(
    fetch(r, { cache: 'no-store' })
      .then(res => {
        if (res.ok) caches.open(V).then(c => c.put(r, res.clone()));
        return res;
      })
      .catch(() => caches.open(V).then(c => c.match(r, { ignoreSearch: true })))
  );
});

self.addEventListener('push', e => {
  let data = {};
  try { data = e.data ? e.data.json() : {}; } catch (err) {}
  const title = data.title || '우리집 가계부';
  const body = data.body || '';
  e.waitUntil(self.registration.showNotification(title, {
    body,
    icon: 'icon-192.png',
    badge: 'icon-192.png',
    tag: data.tag || 'budget',
    renotify: true,
    data: { url: (data.url || './') }
  }));
});

self.addEventListener('notificationclick', e => {
  e.notification.close();
  const url = (e.notification.data && e.notification.data.url) || './';
  e.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(cs => {
      for (const c of cs) { if ('focus' in c) return c.focus(); }
      if (clients.openWindow) return clients.openWindow(url);
    })
  );
});
