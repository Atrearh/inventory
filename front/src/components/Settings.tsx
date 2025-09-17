import { useEffect } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import {
  Form,
  Select,
  Button,
  message,
  Spin,
  Card,
  Tabs,
  Typography,
} from "antd";
import { useTranslation } from "react-i18next";
import { apiInstance } from "../api/api";
import { useTimezone } from "../context/TimezoneContext";
import { usePageTitle } from "../context/PageTitleContext";
import { handleApiError } from "../utils/apiErrorHandler";
import SessionManagement from "./SessionManagement";

const availableTimezones = Intl.supportedValuesOf("timeZone");
const logLevels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"];
const { Title } = Typography;

interface SettingsData {
  timezone: string;
  log_level: string;
}

const Settings: React.FC = () => {
  const { t } = useTranslation();
  const [form] = Form.useForm();
  const { timezone, setTimezone, isLoading: isTimezoneLoading } = useTimezone();
  const { setPageTitle } = usePageTitle();

  useEffect(() => {
    setPageTitle(t("settings", "Налаштування"));
  }, [setPageTitle, t]);

  const { data, isLoading, error } = useQuery<SettingsData, Error>({
    queryKey: ["settings"],
    queryFn: async () => {
      const response = await apiInstance.get("/settings");
      return response.data;
    },
    enabled: !isTimezoneLoading,
  });

  const mutation = useMutation({
    mutationFn: async (values: { timezone: string; log_level: string }) => {
      return await apiInstance.post("/settings", values);
    },
    onSuccess: (data) => {
      message.success(t("settings_updated", "Налаштування успішно оновлено!"));
      if (data.data.timezone) {
        setTimezone(data.data.timezone);
      }
    },
    onError: (error: Error) => {
      const apiError = handleApiError(
        error,
        t("error_updating_settings", "Помилка оновлення налаштувань"),
      );
      message.error(apiError.message);
    },
  });

  useEffect(() => {
    if (data) {
      form.setFieldsValue({
        timezone: data.timezone || timezone,
        log_level: data.log_level || "INFO",
      });
    }
  }, [data, timezone, form]);

  if (isLoading || isTimezoneLoading) {
    return (
      <Spin size="large" style={{ display: "block", margin: "50px auto" }} />
    );
  }

  if (error) {
    const apiError = handleApiError(
      error,
      t("error_loading_settings", "Помилка завантаження налаштувань"),
    );
    return (
      <div>
        {t("error_loading_settings", "Помилка завантаження налаштувань")}:{" "}
        {apiError.message}
      </div>
    );
  }

  const tabItems = [
    {
      key: "general",
      label: t("general_settings"),
      children: (
        <Form
          form={form}
          layout="vertical"
          onFinish={(values) => mutation.mutate(values)}
          style={{ maxWidth: 400 }}
        >
          <Form.Item
            label={t("timezone", "Часовий пояс")}
            name="timezone"
            rules={[
              {
                required: true,
                message: t(
                  "select_timezone",
                  "Будь ласка, оберіть часовий пояс",
                ),
              },
            ]}
            tooltip={t(
              "timezone_tooltip",
              "Усі дати та час у системі будуть відображатися відповідно до цього налаштування.",
            )}
          >
            <Select
              showSearch
              placeholder={t("select_timezone", "Оберіть часовий пояс")}
              optionFilterProp="children"
              filterOption={(input, option) =>
                (option?.label ?? "")
                  .toLowerCase()
                  .includes(input.toLowerCase())
              }
              options={availableTimezones.map((tz) => ({
                value: tz,
                label: tz,
              }))}
            />
          </Form.Item>
          <Form.Item
            label={t("log_level", "Рівень логування")}
            name="log_level"
            rules={[
              {
                required: true,
                message: t(
                  "select_log_level",
                  "Будь ласка, оберіть рівень логування",
                ),
              },
            ]}
            tooltip={t(
              "log_level_tooltip",
              "Визначає деталізацію логів системи.",
            )}
          >
            <Select
              placeholder={t("select_log_level", "Оберіть рівень логування")}
              options={logLevels.map((level) => ({
                value: level,
                label: level,
              }))}
            />
          </Form.Item>
          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              loading={mutation.isPending}
            >
              {t("save", "Зберегти")}
            </Button>
          </Form.Item>
        </Form>
      ),
    },
    {
      key: "security",
      label: t("security"),
      children: <SessionManagement />,
    },
  ];

  return (
    <div style={{ padding: "24px" }}>
      <Card>
        <Title level={3} style={{ marginBottom: 24 }}>
          {t("settings", "Налаштування")}
        </Title>
        <Tabs defaultActiveKey="general" items={tabItems} />
      </Card>
    </div>
  );
};

export default Settings;
