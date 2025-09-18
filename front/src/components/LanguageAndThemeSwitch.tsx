import { Button, Space } from "antd";
import { useTranslation } from "react-i18next";
import { useAppContext } from "../context/AppContext";
import { GlobalOutlined, SunOutlined, MoonOutlined } from "@ant-design/icons";

// Компонент для мовної панелі та перемикача тем
const LanguageAndThemeSwitch: React.FC = () => {
  const { t } = useTranslation();
  const { dark, toggleTheme, changeLanguage, language } = useAppContext();

  // Перемикання мови між українською та англійською
  const toggleLanguage = () => {
    changeLanguage(language === "uk" ? "en" : "uk");
  };

  return (
    <Space>
      <Button
        size="small"
        icon={<GlobalOutlined />}
        onClick={toggleLanguage}
        aria-label={t("switch_language", "Переключити мову")}
      >
        {language === "uk" ? "EN" : "UA"}
      </Button>
      <Button
        size="small"
        icon={dark ? <SunOutlined /> : <MoonOutlined />}
        onClick={toggleTheme}
        aria-label={t("switch_theme", "Переключити тему")}
      >
        {t(dark ? "light_theme" : "dark_theme", dark ? "Світла" : "Темна")}
      </Button>
    </Space>
  );
};

export default LanguageAndThemeSwitch;