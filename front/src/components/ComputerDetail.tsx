import { Descriptions, Button, Modal, Input, notification } from 'antd';
import { useState } from 'react';
import { Computer } from '../types/schemas';
import { EditOutlined } from '@ant-design/icons';
import { apiInstance } from '../api/api';

interface GeneralInfoProps {
  computer: Computer;
  lastCheckDate: Date | null;
  lastCheckColor: string;
}

const GeneralInfo: React.FC<GeneralInfoProps> = ({ computer, lastCheckDate, lastCheckColor }) => {
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [localNotes, setLocalNotes] = useState(computer.local_notes || '');

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
      <Descriptions title="Характеристики" bordered column={2} size="small" style={{ marginBottom: 24 }}>
        <Descriptions.Item label="IP">{computer.ip_addresses && computer.ip_addresses.length > 0 ? computer.ip_addresses[0].address : '-'}</Descriptions.Item>
        <Descriptions.Item label="Назва ОС">{computer.os_name ?? '-'}</Descriptions.Item>
        <Descriptions.Item label="Версія ОС">{computer.os_version ?? '-'}</Descriptions.Item>
        <Descriptions.Item label="Процесор">{computer.processors && computer.processors.length > 0 ? computer.processors[0].name : '-'}</Descriptions.Item>
        <Descriptions.Item label="RAM">{computer.ram ?? '-'} МБ</Descriptions.Item>
        <Descriptions.Item label="MAC">{computer.mac_addresses && computer.mac_addresses.length > 0 ? computer.mac_addresses[0].address : '-'}</Descriptions.Item>
        <Descriptions.Item label="Материнська плата">{computer.motherboard ?? '-'}</Descriptions.Item>
        <Descriptions.Item label="Перезавантажений">
          {computer.last_boot ? new Date(computer.last_boot).toLocaleString('uk-UA') : '-'}
        </Descriptions.Item>
        <Descriptions.Item label="Остання перевірка">
          {lastCheckDate ? (
            <span style={{ color: lastCheckColor }}>
              {lastCheckDate.toLocaleString('uk-UA')}
            </span>
          ) : '-'}
        </Descriptions.Item>
        <Descriptions.Item label="Дата створення в AD">
          {computer.when_created ? new Date(computer.when_created).toLocaleString('uk-UA') : '-'}
        </Descriptions.Item>
        <Descriptions.Item label="Дата зміни в AD">
          {computer.when_changed ? new Date(computer.when_changed).toLocaleString('uk-UA') : '-'}
        </Descriptions.Item>
        <Descriptions.Item label="AD Enabled">{computer.enabled !== null ? (computer.enabled ? 'Так' : 'Ні') : '-'}</Descriptions.Item>
        {computer.is_deleted && (
          <Descriptions.Item label="Видалено">{computer.is_deleted ? 'Так' : '-'}</Descriptions.Item>
        )}
        <Descriptions.Item label="Примітки AD">{computer.ad_notes ?? '-'}</Descriptions.Item>
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