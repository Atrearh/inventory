import { formatInTimeZone } from 'date-fns-tz';
import { uk } from 'date-fns/locale';

export const formatDateInUserTimezone = (
  date: string | Date | undefined | null,
  timezone: string,
  formatString: string = 'dd.MM.yyyy HH:mm:ss'
): string => {
  if (!date) return '-';
  try {
    return formatInTimeZone(new Date(date), timezone, formatString, { locale: uk });
  } catch (error) {
    console.error(`Invalid date or timezone: date=${date}, timezone=${timezone}`, error);
    return 'Невірна дата';
  }
};