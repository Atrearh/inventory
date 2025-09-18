import { useEffect } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import {
  Form,
  Select,
  Button,
  message,
  Switch,
  Spin,
  Card,
  Tabs,
  Typography,
} from "antd";
import { useTranslation } from "react-i18next";
import { apiRequest } from "../utils/apiUtils" 
import { useAppContext } from "../context/AppContext";
import { handleApiError } from "../utils/apiErrorHandler";
import SessionManagement from "./SessionManagement";
import { AxiosResponse } from "axios";

const { Title } = Typography;

interface SettingsData {}

const Settings: React.FC = () => {
  const { t } = useTranslation();
  const [form] = Form.useForm();
  const { language, changeLanguage, dark, toggleTheme, setPageTitle } = useAppContext();

  useEffect(() => {
    setPageTitle(t("settings", "Налаштування"));
  }, [setPageTitle, t]);

  const { data, isLoading, error } = useQuery<SettingsData, Error>({
    queryKey: ["settings"],
    queryFn: async () => {
      const response: AxiosResponse<SettingsData> = await apiRequest("get", "/settings");
      return response.data;
    },
  });

  const mutation = useMutation({
    mutationFn: async (values: {}) => {
      return await apiRequest("post", "/settings", values); 
    },
    onSuccess: () => {
      message.success(t("settings_updated", "Налаштування успішно оновлено!"));
    },
    onError: (error: Error) => {
      const apiError = handleApiError(error, t, t("error_updating_settings", "Помилка оновлення налаштувань"));
      message.error(apiError.message);
    },
  });

  useEffect(() => {
    if (data) {
      form.setFieldsValue({ language });
    }
  }, [data, language, form]);

  if (isLoading) {
    return (
      <Spin size="large" style={{ display: "block", margin: "50px auto" }} />
    );
  }

  if (error) {
    const apiError = handleApiError(error, t, t("error_loading_settings", "Помилка завантаження налаштувань"));
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
      label: t("general_settings", "Загальні налаштування"),
      children: (
        <Form
          form={form}
          layout="vertical"
          onFinish={(values) => {
            if (values.language) changeLanguage(values.language);
            mutation.mutate(values);
          }}
          style={{ maxWidth: 400 }}
        >
          <Form.Item
            label={t("language", "Мова")}
            name="language"
            initialValue={language}
            rules={[
              {
                required: true,
                message: t("select_language", "Будь ласка, оберіть мову"),
              },
            ]}
            tooltip={t(
              "language_tooltip",
              "Виберіть мову інтерфейсу системи.",
            )}
          >
            <Select
              placeholder={t("select_language", "Оберіть мову")}
              options={[
                { value: "uk", label: "Українська" },
                { value: "en", label: "English" },
              ]}
            />
          </Form.Item>
          <Form.Item
            label={t("theme", "Тема")}
            tooltip={t("theme_tooltip", "Виберіть темну або світлу тему інтерфейсу.")}
          >
            <Switch
              checked={dark}
              onChange={toggleTheme}
              checkedChildren={t("dark", "Темна")}
              unCheckedChildren={t("light", "Світла")}
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
      label: t("security", "Безпека"),
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