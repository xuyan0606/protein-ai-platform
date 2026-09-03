/* Minimal no-op service worker to prevent SPA fallback HTML from being
   interpreted as JavaScript when the browser probes /sw.js. */
self.addEventListener('install', () => {
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim())
})

self.addEventListener('fetch', () => {
  // Intentionally empty.
})
