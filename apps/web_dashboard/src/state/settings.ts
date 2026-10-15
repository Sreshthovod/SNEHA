import { createContext, useContext } from 'react'
import { LANGUAGES, type StringKey, type UiLanguage } from '../i18n/strings'

export type TextSize = 'normal' | 'large' | 'larger'

export interface Settings {
  language: UiLanguage
  textSize: TextSize
  highContrast: boolean
  reducedMotion: boolean
}

export const DEFAULT_SETTINGS: Settings = {
  language: 'en',
  textSize: 'normal',
  highContrast: false,
  reducedMotion: false,
}

export const SETTINGS_KEY = 'sneha.dashboard.settings'

/** Per-viewer convenience preferences; storage may be unavailable, so never rely on it. */
export function loadSettings(): Settings {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY)
    if (!raw) return DEFAULT_SETTINGS
    const parsed = JSON.parse(raw) as Partial<Settings>
    return {
      language: parsed.language && parsed.language in LANGUAGES ? parsed.language : 'en',
      textSize: ['normal', 'large', 'larger'].includes(parsed.textSize as string)
        ? (parsed.textSize as TextSize)
        : 'normal',
      highContrast: parsed.highContrast === true,
      reducedMotion: parsed.reducedMotion === true,
    }
  } catch {
    return DEFAULT_SETTINGS
  }
}

export function saveSettings(settings: Settings): void {
  try {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings))
  } catch {
    // Not persisted (private window or blocked storage); still applied for this visit.
  }
}

export interface SettingsContextValue {
  settings: Settings
  update: (patch: Partial<Settings>) => void
  t: (key: StringKey) => string
}

export const SettingsContext = createContext<SettingsContextValue | null>(null)

export function useSettings(): SettingsContextValue {
  const ctx = useContext(SettingsContext)
  if (!ctx) throw new Error('useSettings must be used inside SettingsProvider')
  return ctx
}
