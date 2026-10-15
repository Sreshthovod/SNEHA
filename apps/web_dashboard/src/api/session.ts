/**
 * Holds the sign-in token. Kept in sessionStorage (cleared when the tab closes),
 * never localStorage, so a token does not outlive the browser session.
 */
const KEY = 'sneha.session.token'
type Listener = (token: string | null) => void
const listeners = new Set<Listener>()
let memoryToken: string | null = null

export function getToken(): string | null {
  try {
    return sessionStorage.getItem(KEY) ?? memoryToken
  } catch {
    return memoryToken
  }
}

export function setToken(token: string | null): void {
  memoryToken = token
  try {
    if (token) sessionStorage.setItem(KEY, token)
    else sessionStorage.removeItem(KEY)
  } catch {
    // Storage blocked (private mode): the in-memory token still works for this page.
  }
  listeners.forEach((listener) => listener(token))
}

export function onTokenChange(listener: Listener): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}
