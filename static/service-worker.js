const CACHE_NAME = 'mits-ims-pwa-v1';
const ASSETS_TO_CACHE = [
  '/',
  '/static/index.html',
  '/static/style.css',
  '/static/app.js',
  '/static/manifest.json',
  '/static/offline.html',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/icons/apple-touch-icon.png',
  'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Outfit:wght@400;600;700;800&display=swap',
  'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css'
];

// Install Event: Cache Core Static Shell
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[Service Worker] Caching App Shell Assets');
      return cache.addAll(ASSETS_TO_CACHE);
    }).then(() => self.skipWaiting())
  );
});

// Activate Event: Cleanup Old Caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keyList) => {
      return Promise.all(
        keyList.map((key) => {
          if (key !== CACHE_NAME) {
            console.log('[Service Worker] Removing old cache:', key);
            return caches.delete(key);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch Event: Network-First with Cache & Offline Fallback Strategy
self.addEventListener('fetch', (event) => {
  // Ignore non-GET requests
  if (event.request.method !== 'GET') return;

  const url = new URL(event.request.url);

  // Ignore non-http/https schemes (e.g. chrome-extension://) and API routes
  if (!url.protocol.startsWith('http') || url.pathname.startsWith('/api/')) {
    return;
  }

  event.respondWith(
    fetch(event.request)
      .then((networkResponse) => {
        // Update cache dynamically for valid static responses
        if (networkResponse && networkResponse.status === 200 && networkResponse.type === 'basic') {
          const responseToCache = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseToCache).catch(() => {});
          });
        }
        return networkResponse;
      })

      .catch(() => {
        // Fallback to cache if network fails
        return caches.match(event.request).then((cachedResponse) => {
          if (cachedResponse) {
            return cachedResponse;
          }
          // If HTML page request, return offline fallback page
          if (event.request.headers.get('accept').includes('text/html')) {
            return caches.match('/static/offline.html');
          }
        });
      })
  );
});
