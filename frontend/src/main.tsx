import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './index.css'
import './i18n'
import App from './App.tsx'

const CLIENT_STATE_VERSION_KEY = 'proteinAiClientStateVersion'
const CLIENT_STATE_VERSION = '20260718-user-scope-v3'

try {
  if (localStorage.getItem(CLIENT_STATE_VERSION_KEY) !== CLIENT_STATE_VERSION) {
    localStorage.removeItem('currentConversationId')
    localStorage.setItem(CLIENT_STATE_VERSION_KEY, CLIENT_STATE_VERSION)
  }
} catch {
  // Ignore storage access errors; auth/session recovery will still use the API.
}

void (async () => {
  if (!('serviceWorker' in navigator)) {
    return
  }

  try {
    const registrations = await navigator.serviceWorker.getRegistrations()
    await Promise.all(registrations.map((registration) => registration.unregister()))
  } catch (error) {
    console.warn('Failed to unregister stale service workers', error)
  }

  try {
    if ('caches' in window) {
      const cacheKeys = await caches.keys()
      await Promise.all(cacheKeys.map((key) => caches.delete(key)))
    }
  } catch (error) {
    console.warn('Failed to clear stale service worker caches', error)
  }
})()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
)
