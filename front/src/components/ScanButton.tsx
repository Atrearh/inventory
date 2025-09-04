// src/components/ScanButton.tsx
import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { startScan, getScanStatus } from '../api/api';
import { ScanTask } from '../types/schemas';
import { Button, Progress, notification } from 'antd';

const ScanButton: React.FC = () => {
  const [taskId, setTaskId] = useState<string | null>(null);

  const { data: scanStatus } = useQuery<ScanTask>({
    queryKey: ['scanStatus', taskId],
    queryFn: () => getScanStatus(taskId!),
    enabled: !!taskId,
    refetchInterval: taskId ? 2000 : false, // Опрос каждые 2 секунды
  });

  const startScanMutation = useMutation({
    mutationFn: startScan,
    onSuccess: (data) => {
      setTaskId(data.task_id);
      notification.success({
        message: 'Сканирование запущено',
        description: `Task ID: ${data.task_id}`,
      });
    },
    onError: (error: Error) => {
      notification.error({
        message: 'Ошибка запуска сканирования',
        description: error.message,
      });
    },
  });

  const handleClick = () => {
    startScanMutation.mutate();
  };

  const progressPercent =
    scanStatus && scanStatus.scanned_hosts > 0
      ? (scanStatus.successful_hosts / scanStatus.scanned_hosts) * 100
      : 0;

  return (
    <div>
      <Button
        type="primary"
        onClick={handleClick}
        loading={startScanMutation.isPending}
        disabled={!!taskId && scanStatus?.status === 'running'}
      >
        Запустить сканирование
      </Button>
      {taskId && scanStatus && (
        <div style={{ marginTop: 8 }}>
          <Progress
            percent={progressPercent}
            status={
              scanStatus.status === 'failed'
                ? 'exception'
                : scanStatus.status === 'completed'
                ? 'success'
                : 'active'
            }
          />
          <p>
            Статус: {scanStatus.status} ({scanStatus.successful_hosts}/{scanStatus.scanned_hosts} хостов обработано)
          </p>
          {scanStatus.error && <p style={{ color: 'red' }}>Ошибка: {scanStatus.error}</p>}
        </div>
      )}
    </div>
  );
};

export default ScanButton;