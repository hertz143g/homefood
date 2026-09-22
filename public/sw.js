// Retire the previous service worker; this frontend has no offline storage.
self.addEventListener('install',()=>self.skipWaiting());
self.addEventListener('activate',event=>event.waitUntil(self.registration.unregister()));
