// src/components/ActivityLog.tsx
import { Card, List } from 'antd';
import { useScanEvents } from '../hooks/useScanEvents';

const ActivityLog: React.FC = () => {
  const events = useScanEvents();
  return (
    <Card title="Останні дії" style={{ width: 300, position: 'fixed', right: 16, top: 80 }}>
      <List
        size="small"
        dataSource={[...events].reverse().slice(0, 10)}
        renderItem={(item) => (
          <List.Item>
            <span>{item.task_id}</span> — <strong>{item.status}</strong>
          </List.Item>
        )}
      />
    </Card>
  );
};
export default ActivityLog;
