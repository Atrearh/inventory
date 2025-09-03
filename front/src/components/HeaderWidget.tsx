import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Button, Space, Dropdown, MenuProps, Badge, List, Typography } from 'antd';
import { useAuth } from '../context/AuthContext';
import { useTimezone } from '../context/TimezoneContext';
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
  const [currentTime, setCurrentTime] = useState(new Date());
  const queryClient = useQueryClient();

  // Оновлення часу кожну секунду
  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentTime(new Date());
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  // Запит списку активних завдань (з таблиці scan_tasks)
  const { data: tasks = [], isLoading: isTasksLoading } = useQuery<Task[], Error>({
    queryKey: ['tasks'],
    queryFn: getTasks,
    refetchInterval: 30000, // Оновлюємо кожні 30 секунд
    enabled: !!user, // Запит тільки для авторизованих користувачів
  });

  // Обробка логауту
  const handleLogout = useCallback(() => {
    logout();
    queryClient.clear(); // Очищаємо кеш при логауті
  }, [logout, queryClient]);

  // Форматування часу
  const formattedTime = formatDateInUserTimezone(currentTime, timezone, 'dd.MM.yyyy HH:mm:ss');

  // Елементи меню для списку завдань
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
        <Typography.Text>{formattedTime}</Typography.Text>
        {user && (
          <>
            <Typography.Text strong>{user.username}</Typography.Text>
            <Dropdown
              menu={{ items: taskMenuItems }}
              trigger={['click']}
              disabled={isTasksLoading}
            >
              <Button size="small">
                <Badge count={tasks.length} size="small">
                  {t('tasks', 'Завдання')} <DownOutlined />
                </Badge>
              </Button>
            </Dropdown>
            <Button
              size="small"
              icon={<LogoutOutlined />}
              onClick={handleLogout}
              aria-label={t('logout', 'Вийти')}
            >
              {t('logout', 'Вийти')}
            </Button>
          </>
        )}
        <LanguageAndThemeSwitch />
      </Space>
    </div>
  );
};

export default HeaderWidget;