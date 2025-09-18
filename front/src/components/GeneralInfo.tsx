// front/src/components/GeneralInfo.tsx
import { Descriptions, Button, Modal, Input, notification } from "antd";
import { useState, memo } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { ComputerDetail } from "../types/schemas";
import { EditOutlined } from "@ant-design/icons";
import { apiRequest } from "../utils/apiUtils" 
import { useAppContext } from "../context/AppContext";
import { formatDateInUserTimezone } from "../utils/formatDate";
import { handleApiError } from "../utils/apiErrorHandler";


interface GeneralInfoProps {
  computer: ComputerDetail | undefined;
  lastCheckDate: Date | null;
  lastCheckColor: string;
}

const GeneralInfo: React.FC<GeneralInfoProps> = ({
  computer,
  lastCheckDate,
  lastCheckColor,
}) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [localNotes, setLocalNotes] = useState(computer?.local_notes || "");
  const [isModalVisible, setIsModalVisible] = useState(false);
  const { timezone } = useAppContext();

  if (!computer) {
    return <div>{t("no_computer_data", "Дані про комп'ютер недоступні")}</div>;
  }

  const handleEditNotes = () => {
    setLocalNotes(computer.local_notes || "");
    setIsModalVisible(true);
  };

  const handleSaveNotes = async () => {
    try {
      await apiRequest("put", `/computers/${computer.id}/local_notes`, {
        local_notes: localNotes,
      });
      notification.success({
        message: t("notes_saved", "Локальні примітки збережено"),
      });
      setIsModalVisible(false);
    } catch (error) {
      const apiError = handleApiError(error,t, t("error_saving_notes", "Помилка збереження приміток"));
      if ((error as any).response?.status === 401) {
        notification.error({
          message: t(
            "session_expired",
            "Ваша сесія закінчилася. Будь ласка, увійдіть знову.",
          ),
        });
        navigate("/login");
      } else {
        notification.error({ message: apiError.message });
      }
    }
  };

  return (
    <>
      {!computer.enabled && computer.when_changed && (
        <div style={{ color: "#faad14", marginBottom: 16, fontWeight: "bold" }}>
          {t("disabled_in_ad", "Відключено в AD з")}{" "}
          {formatDateInUserTimezone(computer.when_changed, timezone)}
        </div>
      )}
      <Descriptions
        title={t("specifications", "Характеристики")}
        bordered
        column={2}
        size="small"
        style={{ marginBottom: 24 }}
      >
        <Descriptions.Item label={t("ip_address", "IP")}>
          {computer.ip_addresses && computer.ip_addresses.length > 0
            ? computer.ip_addresses[0].address
            : "-"}
        </Descriptions.Item>
        {/* -- ЗМІНЕНО -- */}
        <Descriptions.Item label={t("os_name", "Назва ОС")}>
          {computer.os?.name ?? "-"}
        </Descriptions.Item>
        <Descriptions.Item label={t("os_version", "Версія ОС")}>
          {computer.os?.version ?? "-"}
        </Descriptions.Item>
        {/* -- КІНЕЦЬ ЗМІН -- */}
        <Descriptions.Item label={t("processor", "Процесор")}>
          {computer.processors && computer.processors.length > 0
            ? computer.processors[0].Name
            : "-"}
        </Descriptions.Item>
        <Descriptions.Item label={t("ram", "RAM")}>
          {computer.ram ?? "-"} {t("mb", "МБ")}
        </Descriptions.Item>
        <Descriptions.Item label={t("mac_address", "MAC")}>
          {computer.mac_addresses && computer.mac_addresses.length > 0
            ? computer.mac_addresses[0].address
            : "-"}
        </Descriptions.Item>
        <Descriptions.Item label={t("motherboard", "Материнська плата")}>
          {computer.motherboard ?? "-"}
        </Descriptions.Item>
        <Descriptions.Item label={t("last_boot", "Перезавантажений")}>
          {formatDateInUserTimezone(computer.last_boot, timezone)}
        </Descriptions.Item>
        <Descriptions.Item label={t("last_ad_login", "Останній вхід в AD")}>
          {formatDateInUserTimezone(computer.last_logon, timezone)}
        </Descriptions.Item>
        <Descriptions.Item label={t("last_check", "Остання перевірка")}>
          {lastCheckDate ? (
            <span style={{ color: lastCheckColor }}>
              {formatDateInUserTimezone(lastCheckDate, timezone)}
            </span>
          ) : (
            "-"
          )}
        </Descriptions.Item>
        <Descriptions.Item label={t("ad_created", "Дата створення в AD")}>
          {formatDateInUserTimezone(computer.when_created, timezone)}
        </Descriptions.Item>
        <Descriptions.Item label={t("ad_changed", "Дата зміни в AD")}>
          {formatDateInUserTimezone(computer.when_changed, timezone)}
        </Descriptions.Item>
        {computer.check_status === "is_deleted" && (
          <Descriptions.Item
            label={t("deleted_from_ad", "Видалено з AD")}
            span={2}
            style={{ color: "#ff4d4f", fontWeight: "bold" }}
          >
            {t("yes", "Так")}
          </Descriptions.Item>
        )}
        {computer.ad_notes && (
          <Descriptions.Item label={t("ad_notes", "Примітки AD")}>
            {computer.ad_notes}
          </Descriptions.Item>
        )}
        <Descriptions.Item
          label={t("local_notes", "Локальні примітки")}
          span={2}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            {computer.local_notes ?? "-"}
            <Button
              icon={<EditOutlined />}
              onClick={handleEditNotes}
              style={{ marginLeft: 8 }}
            />
          </div>
        </Descriptions.Item>
      </Descriptions>
      <Modal
        title={t("edit_local_notes", { hostname: computer.hostname })}
        open={isModalVisible}
        onOk={handleSaveNotes}
        onCancel={() => setIsModalVisible(false)}
        okText={t("save", "Зберегти")}
        cancelText={t("cancel", "Скасувати")}
      >
        <Input.TextArea
          value={localNotes}
          onChange={(e) => setLocalNotes(e.target.value)}
          rows={4}
          placeholder={t("enter_local_notes", "Введіть локальні примітки")}
        />
      </Modal>
    </>
  );
};

export default memo(GeneralInfo);
