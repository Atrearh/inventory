// src/hooks/useErrorHandler.ts
import { useCallback } from 'react';
import { notification } from 'antd';
import { useTranslation } from 'react-i18next';
import { handleApiError } from '../utils/apiErrorHandler';

interface ApiErrorResponse {
  detail?: string;
  message?: string;
  errors?: any;
}

export const useErrorHandler = () => {
  const { t } = useTranslation();

  const handleError = useCallback(
    (error: any, defaultMessage?: string) => {
      const errorObj = handleApiError(error, defaultMessage);
      notification.error({
        message: t('error', 'Помилка'),
        description: errorObj.message,
      });
      return errorObj;
    },
    [t]
  );

  return handleError;
};