import { Button, message, Space, Select, Modal } from 'antd';
import { useMutation, useQuery } from '@tanstack/react-query';
import { startHostScan, updatePolicies, restartPrintSpooler, getScriptsList, executeScript } from '../api/api';
import { useState } from 'react';

interface ActionPanelProps {
  hostname: string;
}

const ActionPanel: React.FC<ActionPanelProps> = ({ hostname }) => {
  const [selectedScript, setSelectedScript] = useState<string | null>(null);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [scriptOutput, setScriptOutput] = useState<{ output: string; error: string } | null>(null);

  const { data: scripts = [], isLoading: isScriptsLoading } = useQuery({
    queryKey: ['scripts'],
    queryFn: getScriptsList,
  });

  const { mutate: scanHost, isPending: isScanLoading } = useMutation({
    mutationFn: () => startHostScan(hostname),
    onSuccess: (data) => message.success(`Сканирование начато, task_id: ${data.task_id}`),
    onError: (error: any) => message.error(`Ошибка сканирования: ${error.response?.data?.detail || error.message}`),
  });

  const { mutate: runGpUpdate, isPending: isGpUpdateLoading } = useMutation({
    mutationFn: () => updatePolicies(hostname),
    onSuccess: (data) => message.success(data.message),
    onError: (error: any) => message.error(`Ошибка обновления политик: ${error.response?.data?.detail || error.message}`),
  });

  const { mutate: restartSpooler, isPending: isSpoolerLoading } = useMutation({
    mutationFn: () => restartPrintSpooler(hostname),
    onSuccess: (data) => message.success(data.message),
    onError: (error: any) => message.error(`Ошибка перезапуска печати: ${error.response?.data?.detail || error.message}`),
  });

  const { mutate: runScript, isPending: isScriptLoading } = useMutation({
    mutationFn: (scriptName: string) => executeScript(hostname, scriptName),
    onSuccess: (data) => {
      setScriptOutput(data);
      setIsModalVisible(true);
      message.success(`Скрипт ${selectedScript} выполнен`);
    },
    onError: (error: any) => message.error(`Ошибка выполнения скрипта: ${error.response?.data?.detail || error.message}`),
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
        Сканировать хост
      </Button>
      <Button onClick={() => runGpUpdate()} loading={isGpUpdateLoading}>
        Обновить политики
      </Button>
      <Button onClick={() => restartSpooler()} loading={isSpoolerLoading}>
        Перезапустить печать
      </Button>
      <Select
        style={{ width: 200 }}
        placeholder="Выберите скрипт"
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
        Выполнить скрипт
      </Button>
      <Modal
        title={`Результат выполнения скрипта ${selectedScript}`}
        open={isModalVisible}
        onCancel={handleModalClose}
        footer={[
          <Button key="close" onClick={handleModalClose}>
            Закрыть
          </Button>,
        ]}
        width={800}
      >
        <pre style={{ maxHeight: '400px', overflow: 'auto' }}>
          {scriptOutput?.output && <div><strong>Вывод:</strong><br />{scriptOutput.output}</div>}
          {scriptOutput?.error && <div style={{ color: 'red', marginTop: '16px' }}><strong>Ошибка:</strong><br />{scriptOutput.error}</div>}
        </pre>
      </Modal>
    </Space>
  );
};

export default ActionPanel;