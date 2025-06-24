// src/components/AdminPanel.tsx
import { Button } from 'antd';
import { useMutation } from '@tanstack/react-query';
import { startScan, startADScan, restartServer } from '../api/api';

// Интерфейс для ответа от сканирования
interface MutationResponse {
  status: string;
  task_id: string;
}

// Интерфейс для ответа от перезапуска
interface RestartResponse {
  message: string;
}

const AdminPanel: React.FC = () => {
  const { mutate: restartServerMutation, isPending: isRestartLoading } = useMutation<RestartResponse, Error, void>({
    mutationFn: restartServer,
    onSuccess: (data) => alert(`Сервер перезапускается: ${data.message}`),
    onError: (error: any) => alert(`Ошибка перезапуска: ${error.response?.data?.error || error.message}`),
  });

  const { mutate: startScanMutation, isPending: isScanLoading } = useMutation<MutationResponse, Error, void>({
    mutationFn: startScan,
    onSuccess: (data) => alert(`Сканирование запущено, task_id: ${data.task_id}`),
    onError: (error) => alert(`Ошибка: ${error.message}`),
  });

  const { mutate: startADScanMutation, isPending: isADScanLoading } = useMutation<MutationResponse, Error, void>({
    mutationFn: startADScan,
    onSuccess: (data) => alert(`Сканирование AD запущено, task_id: ${data.task_id}`),
    onError: (error) => alert(`Ошибка: ${error.message}`),
  });

  return (
    <div>
      <h2>Администрирование</h2>
      <Button
        type="primary"
        onClick={() => startScanMutation()}
        loading={isScanLoading}
        style={{ marginRight: '10px' }}
      >
        Запустить сканирование
      </Button>
      <Button
        type="primary"
        onClick={() => startADScanMutation()}
        loading={isADScanLoading}
        style={{ marginRight: '10px' }}
      >
        Опросить АД
      </Button>
      <Button
        type="primary"
        onClick={() => restartServerMutation()}
        loading={isRestartLoading}
        danger
      >
        Перезапустить сервер
      </Button>
    </div>
  );
};

export default AdminPanel;