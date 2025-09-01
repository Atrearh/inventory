import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import HttpBackend from 'i18next-http-backend';
import LanguageDetector from 'i18next-browser-languagedetector';

i18n
  .use(HttpBackend) // завантаження JSON
  .use(LanguageDetector) // визначення мови користувача
  .use(initReactI18next)
  .init({
    fallbackLng: 'ua', // якщо мова не знайдена → українська
    debug: import.meta.env.DEV,
    interpolation: {
      escapeValue: false
    },
    backend: {
      loadPath: '/locales/{{lng}}/translation.json'
    },
    detection: {
      order: ['querystring', 'localStorage', 'navigator'], // черговість
      caches: ['localStorage'] // зберігаємо вибір у localStorage
    }
  });

export default i18n;
