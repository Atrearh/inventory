import { useMutation, useQueryClient } from '@tanstack/react-query';
import { message, notification } from 'antd';
import { useTranslation } from 'react-i18next';
import { AxiosError } from 'axios';
import { QueryKey } from '@tanstack/react-query';

// Тип для структури помилки API
interface ApiErrorDetail {
  loc?: string[];
  msg: string;
}

// Утилітна функція для уніфікованої обробки помилок
const getErrorMessage = (error: Error | AxiosError, t: (key: string, options?: any) => string): string => {
  if ((error as AxiosError).response?.data) {
    const detail = (error as AxiosError).response!.data as { detail?: string | ApiErrorDetail[] };
    if (detail.detail) {
      if (Array.isArray(detail.detail)) {
        return detail.detail
          .map((err: ApiErrorDetail) => `${err.loc?.join('.') || 'error'}: ${err.msg}`)
          .join('; ');
      }
      return detail.detail as string;
    }
  }
  return error.message || t('error');
};

interface UseApiMutationOptions<TData, TVariables> {
  mutationFn: (variables: TVariables) => Promise<TData>;
  successMessage?: string;
  errorMessage?: string;
  invalidateQueryKeys?: QueryKey[];
  onSuccessCallback?: (data: TData) => void;
  onErrorCallback?: (error: Error | AxiosError) => void;
  useNotification?: boolean;
}

export const useApiMutation = <TData = unknown, TVariables = void>({
  mutationFn,
  successMessage,
  errorMessage,
  invalidateQueryKeys = [],
  onSuccessCallback,
  onErrorCallback,
  useNotification = false,
}: UseApiMutationOptions<TData, TVariables>) => {
  const queryClient = useQueryClient();
  const { t } = useTranslation();

  return useMutation({
    mutationFn,
    onSuccess: (data: TData) => {
      if (successMessage) {
        if (useNotification) {
          notification.success({ message: successMessage });
        } else {
          message.success(successMessage);
        }
      }
      if (invalidateQueryKeys.length > 0) {
        invalidateQueryKeys.forEach(key => {
          queryClient.invalidateQueries({ queryKey: key });
        });
      }
      onSuccessCallback?.(data);
    },
    onError: (error: Error | AxiosError) => {
      const apiError = getErrorMessage(error, t);
      const finalErrorMessage = errorMessage || apiError;
      if (useNotification) {
        notification.error({ message: finalErrorMessage });
      } else {
        message.error(finalErrorMessage);
      }
      onErrorCallback?.(error);
    },
  });
};