import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'
import { setToken } from '../api/session'
import { reportReachable } from '../api/network'

afterEach(() => {
  if (typeof document === 'undefined') return // node-environment tests
  cleanup()
  setToken(null)
  reportReachable(true)
  try {
    localStorage.clear()
    sessionStorage.clear()
  } catch {
    // ignore
  }
  document.documentElement.removeAttribute('data-text-size')
})
