import { Typography, Button } from 'antd';
import { useNavigate } from 'react-router-dom';

const { Title, Paragraph } = Typography;

const NotFound: React.FC = () => {
  const navigate = useNavigate();

  return (
    <div style={{ padding: 24, textAlign: 'center' }}>
      <Title level={2}>Страница не найдена</Title>
      <Paragraph>Запрошенный маршрут не существует.</Paragraph>
      <Button type="primary" onClick={() => navigate('/computers')}>
        Вернуться к списку компьютеров
      </Button>
    </div>
  );
};

export default NotFound;