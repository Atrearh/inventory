import { Descriptions, Button, Modal, Input, notification } from 'antd';
import { useState } from 'react';
import { Computer } from '../types/schemas';
import { EditOutlined } from '@ant-design/icons';
import { apiInstance } from '../api/api';
import { useTimezone } from '../context/TimezoneContext';
import { formatDateInUserTimezone } from '../utils/formatDate';

interface GeneralInfoProps {
  computer: Computer | undefined;
  lastCheckDate: Date | null;
  lastCheckColor: string;
}

const GeneralInfo: React.FC<GeneralInfoProps> = ({ computer, lastCheckDate, lastCheckColor }) => {
  const [localNotes, setLocalNotes] = useState(computer?.local_notes || '');
  const [isModalVisible, setIsModalVisible] = useState(false);
  const { timezone } = useTimezone();

  if (!computer) {
    return <div>Данные о компьютере недоступны</div>;
  }

  const handleEditNotes = () => {
    setLocalNotes(computer.local_notes || '');
    setIsModalVisible(true);
  };

  const handleSaveNotes = async () => {
    try {
      await apiInstance.put(`/computers/${computer.id}/local_notes`, { local_notes: localNotes });
      notification.success({ message: 'Локальні примітки збережено' });
      setIsModalVisible(false);
    } catch (error) {
      notification.error({ message: 'Помилка збереження приміток', description: (error as Error).message });
    }
  };

  return (
    <>
      {!computer.enabled && computer.when_changed && (
        <div style={{ color: '#faad14', marginBottom: 16, fontWeight: 'bold' }}>
          Відключено в AD з {formatDateInUserTimezone(computer.when_changed, timezone)}
        </div>
      )}
      <Descriptions title="Характеристики" bordered column={2} size="small" style={{ marginBottom: 24 }}>
        <Descriptions.Item label="IP">{computer.ip_addresses && computer.ip_addresses.length > 0 ? computer.ip_addresses[0].address : '-'}</Descriptions.Item>
        <Descriptions.Item label="Назва ОС">{computer.os_name ?? '-'}</Descriptions.Item>
        <Descriptions.Item label="Версія ОС">{computer.os_version ?? '-'}</Descriptions.Item>
        <Descriptions.Item label="Процесор">{computer.processors && computer.processors.length > 0 ? computer.processors[0].name : '-'}</Descriptions.Item>
        <Descriptions.Item label="RAM">{computer.ram ?? '-'} МБ</Descriptions.Item>
        <Descriptions.Item label="MAC">{computer.mac_addresses && computer.mac_addresses.length > 0 ? computer.mac_addresses[0].address : '-'}</Descriptions.Item>
        <Descriptions.Item label="Материнська плата">{computer.motherboard ?? '-'}</Descriptions.Item>
        <Descriptions.Item label="Перезавантажений">{formatDateInUserTimezone(computer.last_boot, timezone)} </Descriptions.Item>
        <Descriptions.Item label="Останній вхід в AD">{formatDateInUserTimezone(computer.last_logon, timezone)} </Descriptions.Item>
        <Descriptions.Item label="Остання перевірка">{lastCheckDate ? (<span style={{ color: lastCheckColor }}> {formatDateInUserTimezone(lastCheckDate, timezone)}
        </span>) : '-'}
        </Descriptions.Item>
        <Descriptions.Item label="Дата створення в AD"> {formatDateInUserTimezone(computer.when_created, timezone)} </Descriptions.Item>
        <Descriptions.Item label="Дата зміни в AD">{formatDateInUserTimezone(computer.when_changed, timezone)} </Descriptions.Item>
        {computer.check_status === 'is_deleted' && (<Descriptions.Item label="Видалено з AD" span={2} style={{ color: '#ff4d4f', fontWeight: 'bold' }}> "Так"  </Descriptions.Item>)}
        {computer.ad_notes && (<Descriptions.Item label="Примітки AD">{computer.ad_notes}</Descriptions.Item>)}
        <Descriptions.Item label="Локальні примітки" span={2}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {computer.local_notes ?? '-'}
            <Button
              icon={<EditOutlined />}
              onClick={handleEditNotes}
              style={{ marginLeft: 8 }}
            />
          </div>
        </Descriptions.Item>
      </Descriptions>
      <Modal
        title={`Редагування локальних приміток для ${computer.hostname}`}
        open={isModalVisible}
        onOk={handleSaveNotes}
        onCancel={() => setIsModalVisible(false)}
        okText="Зберегти"
        cancelText="Скасувати"
      >
        <Input.TextArea
          value={localNotes}
          onChange={(e) => setLocalNotes(e.target.value)}
          rows={4}
          placeholder="Введіть локальні примітки"
        />
      </Modal>
    </>
  );
};

export default GeneralInfo;