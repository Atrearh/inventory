import { useEffect } from "react";
import { Typography, Button } from "antd";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { usePageTitle } from "../context/PageTitleContext";

const { Title, Paragraph } = Typography;

const NotFound: React.FC = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { setPageTitle } = usePageTitle();

  useEffect(() => {
    setPageTitle(t("not_found", "Сторінка не знайдена"));
  }, [setPageTitle, t]);

  return (
    <div style={{ padding: 24, textAlign: "center" }}>
      <Paragraph>
        {t("not_found_message", "Запрошений маршрут не існує.")}
      </Paragraph>
      <Button type="primary" onClick={() => navigate("/computers")}>
        {t("back_to_computers", "Повернутися до списку комп’ютерів")}
      </Button>
    </div>
  );
};

export default NotFound;
