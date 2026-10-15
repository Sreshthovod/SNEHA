import { BackendStatusCard } from '../components/BackendStatusCard'
import { Card } from '../components/ui/Card'
import { CheckboxField, SelectField } from '../components/ui/Field'
import { PageHeader } from '../components/ui/PageHeader'
import { Notice } from '../components/ui/States'
import { LANGUAGES, type UiLanguage } from '../i18n/strings'
import { useSettings, type TextSize } from '../state/settings'

export function SettingsPage() {
  const { settings, update, t } = useSettings()
  const draft = LANGUAGES[settings.language].draft
  return (
    <>
      <PageHeader title={t('settings.title')} lede="These preferences are saved in this browser only." />
      <Card title="Language and accessibility">
        <SelectField
          label={t('settings.language')}
          value={settings.language}
          onChange={(e) => update({ language: e.target.value as UiLanguage })}
          options={(Object.keys(LANGUAGES) as UiLanguage[]).map((code) => ({
            value: code,
            label: LANGUAGES[code].draft ? `${LANGUAGES[code].label} — draft` : LANGUAGES[code].label,
          }))}
        />
        {draft && (
          <Notice tone="info">
            This translation is a draft that has not yet been checked by a native speaker. Parts
            of the dashboard are still shown in English.
          </Notice>
        )}
        <SelectField
          label={t('settings.textSize')}
          value={settings.textSize}
          onChange={(e) => update({ textSize: e.target.value as TextSize })}
          options={[
            { value: 'normal', label: 'Standard' },
            { value: 'large', label: 'Large' },
            { value: 'larger', label: 'Extra large' },
          ]}
        />
        <CheckboxField
          label={t('settings.contrast')}
          checked={settings.highContrast}
          onChange={(e) => update({ highContrast: e.target.checked })}
          hint="Darker text and stronger borders."
        />
        <CheckboxField
          label={t('settings.motion')}
          checked={settings.reducedMotion}
          onChange={(e) => update({ reducedMotion: e.target.checked })}
          hint="Turns off transitions. Your device's reduced-motion setting is always respected."
        />
      </Card>
      <BackendStatusCard />
    </>
  )
}
