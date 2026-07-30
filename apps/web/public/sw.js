self.addEventListener('push', (event) => {
  const payload = event.data ? event.data.json() : {}
  event.waitUntil(
    self.registration.showNotification(payload.title || 'TechGrowth', {
      body: payload.body || '你有一条新的成长进展。',
      data: { url: payload.url || '/' },
      tag: 'techgrowth-update',
    }),
  )
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  event.waitUntil(clients.openWindow(event.notification.data.url || '/'))
})

