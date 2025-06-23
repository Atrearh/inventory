// src/components/AdminPanel.tsx
import { Button } from 'antd';
import { useMutation } from '@tanstack/react-query';
import { startScan, startADScan } from '../api/api'; // Добавляем startADScan
//import { useAuth } from '../context/AuthContext';

interface MutationResponse {
  status: string;
  task_id: string;
}

const AdminPanel: React.FC = () => {
  //const { isAuthenticated } = useAuth();
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

  //if (!isAuthenticated) {return <div>Доступ запрещен. Пожалуйста, войдите как администратор.</div>; }

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
      >
        Опросить АД
      </Button>
    </div>
  );
};

export default AdminPanel;