import { Button, message, notification, Space, Select, Modal } from 'antd';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { startHostScan, updatePolicies, restartPrintSpooler, getScriptsList, executeScript } from '../api/api';
import { useState } from 'react';

interface ActionPanelProps {
  hostname: string;
}

const ActionPanel: React.FC<ActionPanelProps> = ({ hostname }) => {
  const [selectedScript, setSelectedScript] = useState<string | null>(null);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [scriptOutput, setScriptOutput] = useState<{ output: string; error: string } | null>(null);
  const queryClient = useQueryClient();

  const { data: scripts = [], isLoading: isScriptsLoading } = useQuery({
    queryKey: ['scripts'],
    queryFn: getScriptsList,
  });

  const { mutate: scanHost, isPending: isScanLoading } = useMutation({
    mutationFn: () => startHostScan(hostname),
    onSuccess: (data) => {
      notification.success({
        message: 'Сканування розпочато',
        description: `Task ID: ${data.task_id}`,
      });
      // Інвалідуємо запити комп'ютерів і завдань після сканування
      queryClient.invalidateQueries({ queryKey: ['computers'] });
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
    },
    onError: (error: any) => {
      notification.error({
        message: 'Помилка сканування',
        description: error.message,
      });
    },
  });

  const { mutate: runGpUpdate, isPending: isGpUpdateLoading } = useMutation({
    mutationFn: () => updatePolicies(hostname),
    onSuccess: (data) => {
      notification.success({
        message: 'Оновлення політик',
        description: data.message,
      });
    },
    onError: (error: any) => {
      notification.error({
        message: 'Помилка оновлення політик',
        description: error.message,
      });
    },
  });

  const { mutate: restartSpooler, isPending: isSpoolerLoading } = useMutation({
    mutationFn: () => restartPrintSpooler(hostname),
    onSuccess: (data) => {
      notification.success({
        message: 'Перезапуск друку',
        description: data.message,
      });
    },
    onError: (error: any) => {
      notification.error({
        message: 'Помилка перезапуску друку',
        description: error.message,
      });
    },
  });

  const { mutate: runScript, isPending: isScriptLoading } = useMutation({
    mutationFn: (scriptName: string) => executeScript(hostname, scriptName),
    onSuccess: (data) => {
      setScriptOutput(data);
      setIsModalVisible(true);
      notification.success({
        message: 'Виконання скрипту',
        description: `Скрипт ${selectedScript} виконано`,
      });
    },
    onError: (error: any) => {
      notification.error({
        message: 'Помилка виконання скрипту',
        description: error.message,
      });
    },
  });

  const handleScriptSelect = (value: string) => {
    setSelectedScript(value);
  };

  const handleModalClose = () => {
    setIsModalVisible(false);
    setScriptOutput(null);
  };

  return (
    <Space wrap>
      <Button type="primary" onClick={() => scanHost()} loading={isScanLoading}>
        Сканувати хост
      </Button>
      <Button onClick={() => runGpUpdate()} loading={isGpUpdateLoading}>
        Оновити політики
      </Button>
      <Button onClick={() => restartSpooler()} loading={isSpoolerLoading}>
        Перезапустити друк
      </Button>
      <Select
        style={{ width: 200 }}
        placeholder="Виберіть скрипт"
        onChange={handleScriptSelect}
        loading={isScriptsLoading}
        disabled={isScriptsLoading || scripts.length === 0}
      >
        {scripts.map((script) => (
          <Select.Option key={script} value={script}>
            {script}
          </Select.Option>
        ))}
      </Select>
      <Button
        onClick={() => selectedScript && runScript(selectedScript)}
        disabled={!selectedScript || isScriptLoading}
        loading={isScriptLoading}
      >
        Виконати скрипт
      </Button>
      <Modal
        title={`Результат виконання скрипту ${selectedScript}`}
        open={isModalVisible}
        onCancel={handleModalClose}
        footer={[
          <Button key="close" onClick={handleModalClose}>
            Закрити
          </Button>,
        ]}
        width={800}
      >
        <pre style={{ maxHeight: '400px', overflow: 'auto' }}>
          {scriptOutput?.output && (
            <div>
              <strong>Вивід:</strong>
              <br />
              {scriptOutput.output}
            </div>
          )}
          {scriptOutput?.error && (
            <div style={{ color: 'red', marginTop: '16px' }}>
              <strong>Помилка:</strong>
              <br />
              {scriptOutput.error}
            </div>
          )}
        </pre>
      </Modal>
    </Space>
  );
};

export default ActionPanel;