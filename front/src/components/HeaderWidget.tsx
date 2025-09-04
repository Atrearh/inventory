import { useState, useEffect, useCallback, useContext } from 'react';
import { useTranslation } from 'react-i18next';
import { Button, Space, Dropdown, MenuProps, Badge, Typography } from 'antd';
import { useAuth } from '../context/AuthContext';
import { useTimezone } from '../context/TimezoneContext';
import { ThemeContext } from '../context/ThemeContext';
import { formatDateInUserTimezone } from '../utils/formatDate';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getTasks } from '../api/tasks.api';
import LanguageAndThemeSwitch from './LanguageAndThemeSwitch';
import { LogoutOutlined, DownOutlined } from '@ant-design/icons';
import styles from './HeaderWidget.module.css';

interface Task {
  id: string;
  name: string;
  status: string;
  created_at: string;
}

const HeaderWidget: React.FC = () => {
  const { t } = useTranslation();
  const { user, logout } = useAuth();
  const { timezone } = useTimezone();
  const { dark } = useContext(ThemeContext);
  const queryClient = useQueryClient();
  const [currentTime, setCurrentTime] = useState(new Date());

  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentTime(new Date());
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  const { data: tasks = [], isLoading: isTasksLoading } = useQuery<Task[], Error>({
    queryKey: ['tasks'],
    queryFn: getTasks,
    refetchInterval: 15000,
    enabled: !!user,
  });

  const handleLogout = useCallback(() => {
    logout();
    queryClient.clear();
  }, [logout, queryClient]);

  const formattedTime = formatDateInUserTimezone(currentTime, timezone, 'dd.MM.yyyy HH:mm:ss');

  const taskMenuItems: MenuProps['items'] = tasks.length > 0 ? tasks.map((task) => ({
    key: task.id,
    label: (
      <div>
        <Typography.Text strong>{task.name || `Сканування ${task.id}`}</Typography.Text>
        <br />
        <Typography.Text type="secondary">
          {t('status')}: {task.status} | {formatDateInUserTimezone(task.created_at, timezone, 'HH:mm:ss')}
        </Typography.Text>
      </div>
    ),
  })) : [{
    key: 'no-tasks',
    label: t('no_active_tasks', 'Немає активних завдань'),
    disabled: true,
  }];

  return (
    <div className={styles.container}>
      <Space align="center">
        <Typography.Text style={{ color: dark ? '#d9d9d9' : '#000' }}>
          {formattedTime}
        </Typography.Text>
        {user && (
          <>
            <Typography.Text strong style={{ color: dark ? '#d9d9d9' : '#000' }}>
              {user.username}
            </Typography.Text>
            <Dropdown
              menu={{ items: taskMenuItems }}
              trigger={['click']}
              disabled={isTasksLoading}
            >
              <Button size="small" type={dark ? 'default' : 'primary'}>
                <Badge count={tasks.length} size="small">
                  {t('tasks', 'Завдання')} <DownOutlined />
                </Badge>
              </Button>
            </Dropdown>
            <LanguageAndThemeSwitch />
            <Button
              size="small"
              icon={<LogoutOutlined />}
              onClick={handleLogout}
              aria-label={t('logout', 'Вийти')}
              type={dark ? 'default' : 'primary'}
            >
              {t('logout', 'Вийти')}
            </Button>
          </>
        )}
        {!user && <LanguageAndThemeSwitch />}
      </Space>
    </div>
  );
};

export default HeaderWidget;