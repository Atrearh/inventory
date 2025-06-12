import { Descriptions } from 'antd';
import { Computer } from '../types/schemas';

interface GeneralInfoProps {
  computer: Computer;
}

const GeneralInfo: React.FC<GeneralInfoProps> = ({ computer }) => (
  <Descriptions title="Характеристики" bordered column={2} size="small" style={{ marginBottom: 24 }}>
    <Descriptions.Item label="IP">{computer?.ip ?? '-'}</Descriptions.Item>
    <Descriptions.Item label="Имя ОС">{computer?.os_name ?? '-'}</Descriptions.Item>
    <Descriptions.Item label="Версия ОС">{computer?.os_version ?? '-'}</Descriptions.Item>
    <Descriptions.Item label="Процессор">{computer?.cpu ?? '-'}</Descriptions.Item>
    <Descriptions.Item label="RAM">{computer?.ram ?? '-'} MB</Descriptions.Item>
    <Descriptions.Item label="MAC">{computer?.mac ?? '-'}</Descriptions.Item>
    <Descriptions.Item label="Материнская плата">{computer?.motherboard ?? '-'}</Descriptions.Item>
    <Descriptions.Item label="Последний запуск">
      {computer?.last_boot ? new Date(computer.last_boot).toLocaleString('ru-RU') : '-'}
    </Descriptions.Item>
    <Descriptions.Item label="Виртуальный">{computer?.is_virtual ? 'Да' : 'Нет'}</Descriptions.Item>
    <Descriptions.Item label="Статус">{computer?.status ?? '-'}</Descriptions.Item>
    <Descriptions.Item label="Check Status">{computer?.check_status ?? '-'}</Descriptions.Item>
  </Descriptions>
);

export default GeneralInfo;