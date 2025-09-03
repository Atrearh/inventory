import { formatInTimeZone } from 'date-fns-tz';
import { uk } from 'date-fns/locale';

export const formatDateInUserTimezone = (
  date: string | Date | undefined | null,
  timezone: string,
  formatString: string = 'dd.MM.yyyy HH:mm:ss'
): string => {
  if (!date) return '-';
  try {
    const parsedDate = typeof date === 'string' ? new Date(date) : date;
    if (isNaN(parsedDate.getTime())) {
      console.error(`Invalid date: ${date}`);
      return 'Невірна дата';
    }
    return formatInTimeZone(parsedDate, timezone, formatString, { locale: uk });
  } catch (error) {
    console.error(`Error formatting date: date=${date}, timezone=${timezone}`, error);
    return 'Невірна дата';
  }
};