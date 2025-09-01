import { Tabs } from 'antd';
import { useTranslation } from 'react-i18next';

interface DashboardMenuProps {
  activeTab: string;
  onTabChange: (key: string) => void;
}

const DashboardMenu: React.FC<DashboardMenuProps> = ({ activeTab, onTabChange }) => {
  const { t } = useTranslation();

  return (
    <Tabs
      key={activeTab}
      activeKey={activeTab}
      onChange={onTabChange}
      items={[
        { key: 'summary', label: t('summary') },
        { key: 'low_disk_space', label: t('low_disk_space') },
        { key: 'subnets', label: t('subnets') },
      ]}
      style={{ marginBottom: 16 }}
    />
  );
};

export default DashboardMenu;