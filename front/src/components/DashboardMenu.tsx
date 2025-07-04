// src/components/DashboardMenu.tsx
import { Tabs } from 'antd';
import { useState } from 'react';

interface DashboardMenuProps {
  onTabChange: (key: string) => void;
}

const DashboardMenu: React.FC<DashboardMenuProps> = ({ onTabChange }) => {
  const [activeKey, setActiveKey] = useState('summary');

  const handleTabChange = (key: string) => {
    setActiveKey(key);
    onTabChange(key);
  };

  return (
    <Tabs
      activeKey={activeKey}
      onChange={handleTabChange}
      items={[
        { key: 'summary', label: 'Загальна статистика' },
        { key: 'os_distribution', label: 'Розподіл ОС' },
        { key: 'low_disk_space', label: 'Низький обсяг диска' },
        { key: 'status_stats', label: 'Статуси компютерів' },
      ]}
      style={{ marginBottom: 16 }}
    />
  );
};

export default DashboardMenu;