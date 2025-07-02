// src/components/GeneralInfo.tsx
import { Descriptions } from 'antd';
import { Computer } from '../types/schemas';

interface GeneralInfoProps {
  computer: Computer;
  lastCheckDate: Date | null;
  lastCheckColor: string;
}

const GeneralInfo: React.FC<GeneralInfoProps> = ({ computer, lastCheckDate, lastCheckColor }) => (
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
    <Descriptions.Item label="Віртуальний">{computer.is_virtual ? 'Так' : 'Ні'}</Descriptions.Item>
    <Descriptions.Item label="Остання перевірка">
      {lastCheckDate ? (
        <span style={{ color: lastCheckColor }}>
          {lastCheckDate.toLocaleString('uk-UA')}
        </span>
      ) : '-'}
    </Descriptions.Item>
  </Descriptions>
);

export default GeneralInfo;