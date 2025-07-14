// src/components/DashboardMenu.tsx

import { Tabs } from 'antd';

interface DashboardMenuProps {
  activeTab: string;
  onTabChange: (key: string) => void;
}

const DashboardMenu: React.FC<DashboardMenuProps> = ({ activeTab, onTabChange }) => {
  return (
    <Tabs
      activeKey={activeTab}
      onChange={onTabChange}
      items={[
        { key: 'summary', label: 'Загальна статистика' },
        { key: 'low_disk_space', label: 'Низький обсяг диска' },
      ]}
      style={{ marginBottom: 16 }}
    />
  );
};

export default DashboardMenu;