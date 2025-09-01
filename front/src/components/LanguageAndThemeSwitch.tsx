import React, { useContext } from 'react';
import { Button, Space } from 'antd';
import { useTranslation } from 'react-i18next';
import { ThemeContext } from '../context/ThemeContext';
import { GlobalOutlined, SunOutlined, MoonOutlined } from '@ant-design/icons'; 

// Компонент для мовної панелі та перемикача тем
const LanguageAndThemeSwitch: React.FC = () => {
  const { i18n, t } = useTranslation();
  const { dark, setDark } = useContext(ThemeContext);

  // Перемикання мови між українською та англійською
  const toggleLanguage = () => {
    i18n.changeLanguage(i18n.language === 'ua' ? 'en' : 'ua');
  };

  // Перемикання теми
  const toggleTheme = () => {
    setDark(!dark);
  };

  return (
    <Space
      style={{
        position: 'fixed',
        bottom: 16,
        right: 16,
        zIndex: 999, // Залишаємо високий zIndex, але нижче кнопки згортання
      }}
    >
      <Button
        size="small"
        icon={<GlobalOutlined />}
        onClick={toggleLanguage}
        aria-label={t('switch_language')}
      >
        {i18n.language === 'ua' ? 'EN' : 'UA'}
      </Button>
      <Button
        size="small"
        icon={dark ? <SunOutlined /> : <MoonOutlined />} // Іконка залежно від теми
        onClick={toggleTheme}
        aria-label={t('switch_theme')}
      >
        {t(dark ? 'light_theme' : 'dark_theme')}
      </Button>
    </Space>
  );
};

export default LanguageAndThemeSwitch;