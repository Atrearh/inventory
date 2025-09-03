import { useState, useEffect } from 'react';
import { useTimezone } from '../context/TimezoneContext';
import { formatDateInUserTimezone } from '../utils/formatDate';
import styles from './ServerTimeWidget.module.css';

const ServerTimeWidget: React.FC = () => {
  const { timezone } = useTimezone();
  const [currentTime, setCurrentTime] = useState(new Date());

  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentTime(new Date());
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  const formattedTime = formatDateInUserTimezone(currentTime, timezone, 'dd.MM.yyyy HH:mm:ss');

  return (
    <div className={styles.container}>
      <span>Поточний час: {formattedTime}</span>
    </div>
  );
};

export default ServerTimeWidget;