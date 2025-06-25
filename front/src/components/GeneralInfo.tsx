import { Descriptions } from 'antd';
import { Computer } from '../types/schemas';

interface GeneralInfoProps {
  computer: Computer;
}

const GeneralInfo: React.FC<GeneralInfoProps> = ({ computer }) => (
  <Descriptions title="Характеристики" bordered column={2} size="small" style={{ marginBottom: 24 }}>
    <Descriptions.Item label="IP">{computer?.ip ?? '-'}</Descriptions.Item>
    <Descriptions.Item label="Назва ОС">{computer?.os_name ?? '-'}</Descriptions.Item>
    <Descriptions.Item label="Версія ОС">{computer?.os_version ?? '-'}</Descriptions.Item>
    <Descriptions.Item label="Процесор">{computer?.cpu ?? '-'}</Descriptions.Item>
    <Descriptions.Item label="RAM">{computer?.ram ?? '-'} МБ</Descriptions.Item>
    <Descriptions.Item label="MAC">{computer?.mac ?? '-'}</Descriptions.Item>
    <Descriptions.Item label="Материнська плата">{computer?.motherboard ?? '-'}</Descriptions.Item>
    <Descriptions.Item label="Перезавантажений">
      {computer?.last_boot ? new Date(computer.last_boot).toLocaleString('uk-UA') : '-'}
    </Descriptions.Item>
    <Descriptions.Item label="Віртуальний">{computer?.is_virtual ? 'Так' : 'Ні'}</Descriptions.Item>
    <Descriptions.Item label="Статус перевірки">{computer?.check_status ?? '-'}</Descriptions.Item>
  </Descriptions>
);

export default GeneralInfo;