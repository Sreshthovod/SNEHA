import { describe, expect, it } from 'vitest'
import { ConfigError, parseConfig } from './env'

describe('parseConfig', () => {
  it('defaults to the local development API', () => {
    expect(parseConfig({}).apiBaseUrl).toBe('http://localhost:8000')
  })

  it('strips trailing slashes', () => {
    expect(parseConfig({ VITE_API_BASE_URL: 'https://api.example.test/' }).apiBaseUrl).toBe(
      'https://api.example.test',
    )
  })

  it('rejects relative or malformed URLs with a helpful message', () => {
    expect(() => parseConfig({ VITE_API_BASE_URL: 'localhost:8000/api' })).toThrow(ConfigError)
    expect(() => parseConfig({ VITE_API_BASE_URL: 'not a url' })).toThrow(/absolute URL/)
  })

  it('rejects non-http protocols', () => {
    expect(() => parseConfig({ VITE_API_BASE_URL: 'ftp://example.test' })).toThrow(/http or https/)
  })
})
