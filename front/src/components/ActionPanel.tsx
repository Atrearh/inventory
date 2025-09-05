import { Button, notification, Space, Select, Modal } from 'antd';
import {  useQuery } from '@tanstack/react-query';
import { startHostScan, updatePolicies, restartPrintSpooler, getScriptsList, executeScript } from '../api/api';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useApiMutation } from '../hooks/useApiMutation';

interface ActionPanelProps {
  hostname: string;
}

const ActionPanel: React.FC<ActionPanelProps> = ({ hostname }) => {
  const { t } = useTranslation();
  const [selectedScript, setSelectedScript] = useState<string | null>(null);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [scriptOutput, setScriptOutput] = useState<{ output: string; error: string } | null>(null);

  const { data: scripts = [], isLoading: isScriptsLoading } = useQuery({
    queryKey: ['scripts'],
    queryFn: getScriptsList,
  });

  // Типи для відповідей API
  interface ScanHostResponse {
    task_id: string;
  }

  interface ActionResponse {
    output: string;
    error: string;
  }

  interface ScriptExecutionResponse {
    output: string;
    error: string;
  }

  const { mutate: scanHost, isPending: isScanLoading } = useApiMutation<ScanHostResponse, void>({
    mutationFn: () => startHostScan(hostname),
    successMessage: t('scan_started'),
    invalidateQueryKeys: [['computers'], ['tasks']],
    useNotification: true,
    onSuccessCallback: (data) => {
      notification.success({
        message: t('scan_started'),
        description: t('scan_task_id', { task_id: data.task_id }),
      });
    },
  });

  const { mutate: runGpUpdate, isPending: isGpUpdateLoading } = useApiMutation<ActionResponse, void>({
    mutationFn: () => updatePolicies(hostname),
    successMessage: t('update_policies'),
    useNotification: true,
    onSuccessCallback: (data) => {
      notification.success({
        message: t('update_policies'),
        description: data.output || t('operation_successful'), // Використовуємо output замість message
      });
    },
  });

  const { mutate: restartSpooler, isPending: isSpoolerLoading } = useApiMutation<ActionResponse, void>({
    mutationFn: () => restartPrintSpooler(hostname),
    successMessage: t('restart_print'),
    useNotification: true,
    onSuccessCallback: (data) => {
      notification.success({
        message: t('restart_print'),
        description: data.output || t('operation_successful'), // Використовуємо output замість message
      });
    },
  });

  const { mutate: runScript, isPending: isScriptLoading } = useApiMutation<ScriptExecutionResponse, string>({
    mutationFn: (scriptName: string) => executeScript(hostname, scriptName),
    successMessage: t('script_execution'),
    useNotification: true,
    onSuccessCallback: (data) => {
      setScriptOutput(data);
      setIsModalVisible(true);
      notification.success({
        message: t('script_execution'),
        description: t('script_executed', { script: selectedScript }),
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
        {t('scan_host', 'Scan host')}
      </Button>
      <Button onClick={() => runGpUpdate()} loading={isGpUpdateLoading}>
        {t('update_policies', 'Update policies')}
      </Button>
      <Button onClick={() => restartSpooler()} loading={isSpoolerLoading}>
        {t('restart_print', 'Restart print')}
      </Button>
      <Select
        style={{ width: 200 }}
        placeholder={t('select_script', 'Select script')}
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
        {t('execute_script', 'Execute script')}
      </Button>
      <Modal
        title={t('script_execution_result', { script: selectedScript })}
        open={isModalVisible}
        onCancel={handleModalClose}
        footer={[
          <Button key="close" onClick={handleModalClose}>
            {t('close', 'Close')}
          </Button>,
        ]}
        width={800}
      >
        <pre style={{ maxHeight: '400px', overflow: 'auto' }}>
          {scriptOutput?.output && (
            <div>
              <strong>{t('output', 'Output')}:</strong>
              <br />
              {scriptOutput.output}
            </div>
          )}
          {scriptOutput?.error && (
            <div style={{ color: 'red', marginTop: '16px' }}>
              <strong>{t('error', 'Error')}:</strong>
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