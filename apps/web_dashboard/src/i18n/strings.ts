/**
 * UI strings. English is complete and authoritative.
 * Hindi is a DRAFT that has not been reviewed by a native speaker; any key missing
 * from a draft table falls back to English. Settings tells users this.
 */
export const LANGUAGES = {
  en: { label: 'English', draft: false },
  hi: { label: 'हिन्दी (Hindi)', draft: true },
} as const

export type UiLanguage = keyof typeof LANGUAGES

export const en = {
  'app.name': 'SNEHA',
  'app.tagline': 'Memory and activity support, shared with the people who care.',
  'nav.main': 'Main',
  'nav.dashboard': 'Dashboard',
  'nav.patients': 'People I care for',
  'nav.clinician': 'My patients',
  'nav.settings': 'Settings',
  'nav.signOut': 'Sign out',
  'nav.skip': 'Skip to main content',
  'tab.overview': 'Profile',
  'tab.memories': 'Memory Bank',
  'tab.observations': 'Observations',
  'tab.history': 'Activity history',
  'tab.analytics': 'Activity trends',
  'tab.reports': 'Reports',
  'tab.people': 'Family & devices',
  'tab.consent': 'Consent & data',
  'tab.progress': 'Progress & suggestions',
  'tab.preferences': 'Interests & preferences',
  'action.save': 'Save',
  'action.cancel': 'Cancel',
  'action.retry': 'Try again',
  'action.delete': 'Delete',
  'action.close': 'Close',
  'state.loading': 'Loading…',
  'state.offline': 'You are offline. Changes cannot be saved until the connection returns.',
  'state.unreachable': 'The SNEHA server cannot be reached right now. Please try again shortly.',
  'login.title': 'Sign in',
  'login.email': 'Email',
  'login.password': 'Password',
  'login.submit': 'Sign in',
  'login.noAccount': 'New to SNEHA?',
  'login.register': 'Create an account',
  'register.title': 'Create an account',
  'settings.title': 'Settings',
  'settings.language': 'Language',
  'settings.textSize': 'Text size',
  'settings.contrast': 'Extra high contrast',
  'settings.motion': 'Reduce motion',
  'footer.disclaimer':
    'SNEHA is an assistive tool for activities and memory support. It does not diagnose any condition.',
} as const

export type StringKey = keyof typeof en

export const hi: Partial<Record<StringKey, string>> = {
  'app.tagline': 'स्मृति और गतिविधि सहायता, उनके साथ जो परवाह करते हैं।',
  'nav.dashboard': 'डैशबोर्ड',
  'nav.patients': 'जिनकी मैं देखभाल करता/करती हूँ',
  'nav.clinician': 'मेरे मरीज़',
  'nav.settings': 'सेटिंग्स',
  'nav.signOut': 'साइन आउट',
  'nav.skip': 'मुख्य सामग्री पर जाएँ',
  'tab.overview': 'प्रोफ़ाइल',
  'tab.memories': 'स्मृति बैंक',
  'tab.observations': 'अवलोकन',
  'tab.history': 'गतिविधि इतिहास',
  'tab.analytics': 'गतिविधि रुझान',
  'tab.reports': 'रिपोर्ट',
  'tab.people': 'परिवार और उपकरण',
  'tab.consent': 'सहमति और डेटा',
  'action.save': 'सहेजें',
  'action.cancel': 'रद्द करें',
  'action.retry': 'फिर से कोशिश करें',
  'action.delete': 'हटाएँ',
  'action.close': 'बंद करें',
  'state.loading': 'लोड हो रहा है…',
  'login.title': 'साइन इन करें',
  'login.email': 'ईमेल',
  'login.password': 'पासवर्ड',
  'login.submit': 'साइन इन करें',
  'settings.title': 'सेटिंग्स',
  'settings.language': 'भाषा',
  'settings.textSize': 'अक्षर का आकार',
}

export const TABLES: Record<UiLanguage, Partial<Record<StringKey, string>>> = { en, hi }

export function translate(lang: UiLanguage, key: StringKey): string {
  return TABLES[lang][key] ?? en[key]
}
