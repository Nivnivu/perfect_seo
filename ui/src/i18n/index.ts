import { createI18n } from 'vue-i18n'
import en from './locales/en.json'
import he from './locales/he.json'
import de from './locales/de.json'

// RTL language codes — extend this list as new locales are added
const RTL_LOCALES = ['he', 'ar', 'fa', 'ur', 'yi', 'dv', 'ps', 'sd']

export interface LocaleEntry {
  code: string
  name: string   // display name in the native script
}

// Registry of available locales — add your locale here when contributing
export const SUPPORTED_LOCALES: LocaleEntry[] = [
  { code: 'en', name: 'English' },
  { code: 'he', name: 'עברית' },
  { code: 'de', name: 'Deutsch' }
] 

export function isRtl(locale: string): boolean {
  return RTL_LOCALES.includes(locale)
}

/** Apply locale to the <html> element (dir + lang). Call whenever locale changes. */
export function applyLocaleToDocument(locale: string): void {
  document.documentElement.setAttribute('lang', locale)
  document.documentElement.setAttribute('dir', isRtl(locale) ? 'rtl' : 'ltr')
}

const saved = localStorage.getItem('locale') ?? 'en'
// Apply immediately so the page doesn't flash LTR before Vue mounts
applyLocaleToDocument(saved)

const i18n = createI18n({
  legacy: false,          // Composition API mode — $t still available in templates
  locale: saved,
  fallbackLocale: 'en',
  messages: { en, he, de },
  // Add your locale messages object here when contributing a new language:
  // messages: { en, he, ar, fr, de, ... }
})

export default i18n
