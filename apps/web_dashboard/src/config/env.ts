/**
 * Environment-based configuration. Values come from Vite `VITE_*` variables
 * (see .env.example). Only non-secret values may live here: everything is shipped to the browser.
 */

export interface AppConfig {
  apiBaseUrl: string
}

export class ConfigError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'ConfigError'
  }
}

const DEFAULT_API_BASE_URL = 'http://localhost:8000'

export function parseConfig(env: Partial<ImportMetaEnv>): AppConfig {
  const raw = (env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL).trim()
  let url: URL
  try {
    url = new URL(raw)
  } catch {
    throw new ConfigError(
      `VITE_API_BASE_URL must be an absolute URL such as http://localhost:8000 (got "${raw}")`,
    )
  }
  if (url.protocol !== 'http:' && url.protocol !== 'https:') {
    throw new ConfigError(`VITE_API_BASE_URL must use http or https (got "${url.protocol}")`)
  }
  return { apiBaseUrl: raw.replace(/\/+$/, '') }
}

export const config: AppConfig = parseConfig(import.meta.env)
