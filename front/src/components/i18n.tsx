import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import HttpBackend from 'i18next-http-backend';
import LanguageDetector from 'i18next-browser-languagedetector';

i18n
  .use(HttpBackend) 
  .use(LanguageDetector) 
  .use(initReactI18next)
  .init({
    fallbackLng: 'ua', 
    debug: import.meta.env.DEV,
    interpolation: {
      escapeValue: false
    },
    backend: {
      loadPath: '/locales/translation.{{lng}}.json'
    },
    detection: {
      order: ['querystring', 'localStorage', 'navigator'], 
      caches: ['localStorage'] 
    }
  });

export default i18n;
