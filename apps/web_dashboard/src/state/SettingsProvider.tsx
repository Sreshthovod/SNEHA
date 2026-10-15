import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { translate } from '../i18n/strings'
import {
  loadSettings,
  saveSettings,
  SettingsContext,
  type Settings,
  type SettingsContextValue,
} from './settings'

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<Settings>(loadSettings)

  useEffect(() => {
    const root = document.documentElement
    root.lang = settings.language
    root.dataset.textSize = settings.textSize
    root.dataset.contrast = settings.highContrast ? 'high' : 'normal'
    root.dataset.motion = settings.reducedMotion ? 'reduced' : 'normal'
  }, [settings])

  const update = useCallback((patch: Partial<Settings>) => {
    setSettings((current) => {
      const next = { ...current, ...patch }
      saveSettings(next)
      return next
    })
  }, [])

  const value = useMemo<SettingsContextValue>(
    () => ({ settings, update, t: (key) => translate(settings.language, key) }),
    [settings, update],
  )
  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>
}

