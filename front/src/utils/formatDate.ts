// src/utils/formatDate.ts
export function formatDate(date: string | Date | undefined, locale: string = 'ru-RU'): string {
  if (!date) return '-';
  return new Date(date).toLocaleString(locale);
}