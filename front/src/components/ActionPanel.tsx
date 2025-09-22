import { Button, notification, Space, Select, Modal } from "antd";
import { useQuery } from "@tanstack/react-query";
import {
  startHostScan,
  updatePolicies,
  restartPrintSpooler,
  getScriptsList,
  executeScript,
} from "../api/api";
import { useState, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useApiMutation } from "../hooks/useApiMutation";
import { AxiosError } from "axios";

interface ActionPanelProps {
  hostname?: string;
  hostnames?: string[];
}

const ActionPanel: React.FC<ActionPanelProps> = ({ hostname, hostnames }) => {
  const { t } = useTranslation();
  const [selectedScript, setSelectedScript] = useState<string | null>(null);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [scriptOutput, setScriptOutput] = useState<
    { hostname: string; output: string; error: string }[]
  >([]);

  // Normalize hostname(s) to an array
  const hosts = useMemo(() => {
    if (hostnames) return hostnames;
    if (hostname) return [hostname];
    return [];
  }, [hostname, hostnames]);

  const { data: scripts = [], isLoading: isScriptsLoading } = useQuery({
    queryKey: ["scripts"],
    queryFn: getScriptsList,
  });

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

  const { mutate: scanHost, isPending: isScanLoading } = useApiMutation<
    ScanHostResponse[],
    void
  >({
    mutationFn: () =>
      Promise.all(hosts.map((host) => startHostScan(host))),
    successMessage: t("scan_started"),
    invalidateQueryKeys: [["computers"], ["tasks"]],
    useNotification: true,
    onSuccessCallback: (data) => {
      data.forEach((result, index) => {
        notification.success({
          message: t("scan_started"),
          description: t("scan_task_id", { task_id: result.task_id, hostname: hosts[index] }),
        });
      });
    },
    onErrorCallback: (error: Error | AxiosError) => {
      notification.error({
        message: t("scan_failed"),
        description: t("scan_failed_description", { error: error.message }),
      });
    },
  });

  const { mutate: runGpUpdate, isPending: isGpUpdateLoading } = useApiMutation<
    ActionResponse[],
    void
  >({
    mutationFn: () =>
      Promise.all(hosts.map((host) => updatePolicies(host))),
    successMessage: t("update_policies"),
    useNotification: true,
    onSuccessCallback: (data) => {
      data.forEach((result, index) => {
        notification.success({
          message: t("update_policies"),
          description: `${hosts[index]}: ${result.output || t("operation_successful")}`,
        });
      });
    },
    onErrorCallback: (error: Error | AxiosError) => {
      notification.error({
        message: t("update_policies_failed"),
        description: t("update_policies_failed_description", { error: error.message }),
      });
    },
  });

  const { mutate: restartSpooler, isPending: isSpoolerLoading } = useApiMutation<
    ActionResponse[],
    void
  >({
    mutationFn: () =>
      Promise.all(hosts.map((host) => restartPrintSpooler(host))),
    successMessage: t("restart_print"),
    useNotification: true,
    onSuccessCallback: (data) => {
      data.forEach((result, index) => {
        notification.success({
          message: t("restart_print"),
          description: `${hosts[index]}: ${result.output || t("operation_successful")}`,
        });
      });
    },
    onErrorCallback: (error: Error | AxiosError) => {
      notification.error({
        message: t("restart_print_failed"),
        description: t("restart_print_failed_description", { error: error.message }),
      });
    },
  });

  const { mutate: runScript, isPending: isScriptLoading } = useApiMutation<
    ScriptExecutionResponse[],
    string
  >({
    mutationFn: (scriptName: string) =>
      Promise.all(hosts.map((host) => executeScript(host, scriptName))),
    successMessage: t("script_execution"),
    useNotification: true,
    onSuccessCallback: (data) => {
      setScriptOutput(
        data.map((result, index) => ({
          hostname: hosts[index],
          output: result.output || "",
          error: result.error || "",
        })),
      );
      setIsModalVisible(true);
      notification.success({
        message: t("script_execution"),
        description: t("script_executed", { script: selectedScript }),
      });
    },
    onErrorCallback: (error: Error | AxiosError) => {
      notification.error({
        message: t("script_execution_failed"),
        description: t("script_execution_failed_description", { error: error.message }),
      });
    },
  });

  const handleScriptSelect = (value: string) => {
    setSelectedScript(value);
  };

  const handleModalClose = () => {
    setIsModalVisible(false);
    setScriptOutput([]);
  };

  const isActionDisabled = hosts.length === 0;

  return (
    <Space wrap>
      <Button
        type="primary"
        onClick={() => scanHost()}
        loading={isScanLoading}
        disabled={isActionDisabled}
      >
        {t("scan_host", "Scan host")}
      </Button>
      <Button
        onClick={() => runGpUpdate()}
        loading={isGpUpdateLoading}
        disabled={isActionDisabled}
      >
        {t("update_policies", "Update policies")}
      </Button>
      <Button
        onClick={() => restartSpooler()}
        loading={isSpoolerLoading}
        disabled={isActionDisabled}
      >
        {t("restart_print", "Restart print")}
      </Button>
      <Select
        style={{ width: 200 }}
        placeholder={t("select_script", "Select script")}
        onChange={handleScriptSelect}
        loading={isScriptsLoading}
        disabled={isScriptsLoading || scripts.length === 0 || isActionDisabled}
      >
        {scripts.map((script) => (
          <Select.Option key={script} value={script}>
            {script}
          </Select.Option>
        ))}
      </Select>
      <Button
        onClick={() => selectedScript && runScript(selectedScript)}
        disabled={!selectedScript || isScriptLoading || isActionDisabled}
        loading={isScriptLoading}
      >
        {t("execute_script", "Execute script")}
      </Button>
      <Modal
        title={t("script_execution_result", { script: selectedScript })}
        open={isModalVisible}
        onCancel={handleModalClose}
        footer={[
          <Button key="close" onClick={handleModalClose}>
            {t("close", "Close")}
          </Button>,
        ]}
        width={800}
      >
        {scriptOutput.map((result, index) => (
          <div key={index} style={{ marginBottom: "16px" }}>
            <h4>{result.hostname}</h4>
            <pre style={{ maxHeight: "400px", overflow: "auto" }}>
              {result.output && (
                <div>
                  <strong>{t("output", "Output")}:</strong>
                  <br />
                  {result.output}
                </div>
              )}
              {result.error && (
                <div style={{ color: "red", marginTop: "16px" }}>
                  <strong>{t("error", "Error")}:</strong>
                  <br />
                  {result.error}
                </div>
              )}
            </pre>
          </div>
        ))}
      </Modal>
    </Space>
  );
};

export default ActionPanel;