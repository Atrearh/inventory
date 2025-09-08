import { useCallback } from 'react';
import { notification } from 'antd';
import { useTranslation } from 'react-i18next';
import { handleApiError } from '../utils/apiErrorHandler';
import { AxiosError } from 'axios';

interface ApiErrorResponse {
  detail?: string;
  message?: string;
  errors?: any;
}

export const useErrorHandler = () => {
  const { t } = useTranslation();

  const handleError = useCallback(
    (error: AxiosError<ApiErrorResponse> | any, defaultMessage?: string) => {
      const errorObj = handleApiError(error, t, defaultMessage);
      notification.error({
        message: t('error'),
        description: errorObj.message,
      });
      return errorObj;
    },
    [t]
  );

  return handleError;
};