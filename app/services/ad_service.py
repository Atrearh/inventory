import logging
from ldap3 import Server, Connection, ALL
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from ..settings import settings
from ..repositories.computer_repository import ComputerRepository
from ..models import CheckStatus
from datetime import datetime 

logger = logging.getLogger(__name__)

class ADService:
    def __init__(self, repo: ComputerRepository):
        self.repo = repo

    def get_ad_computers(self) -> List[dict]:
        """Получает список компьютеров из Active Directory."""
        logger.debug("Начало процесса сканирования AD")
        if not all([settings.ad_server_url, settings.domain, settings.ad_username, settings.ad_password]):
            logger.error("Отсутствуют учетные данные AD в настройках")
            raise ValueError("Учетные данные AD обязательны для подключения к LDAP")

        server = Server(settings.ad_server_url, get_info=ALL)
        try:
            conn = Connection(server, user=settings.ad_username, password=settings.ad_password, auto_bind=True)
            base_dn = settings.ad_base_dn or "dc=" + ",dc=".join(settings.domain.split('.'))
            logger.debug(f"Выполняется поиск с base DN: {base_dn}, filter: (objectClass=computer)")

            conn.search(
                search_base=base_dn,
                search_filter="(objectClass=computer)",
                attributes=["dNSHostName", "operatingSystem", "objectGUID", "whenCreated", "whenChanged", "userAccountControl", "description", "lastLogon"]
            )
            logger.debug(f"Найдено записей: {len(conn.entries)}")

            computers = []
            for entry in conn.entries:
                dns_hostname = entry.dNSHostName.value if entry.dNSHostName else None
                if not dns_hostname:
                    logger.warning(f"Запись {entry.entry_dn} не имеет 'dNSHostName'")
                    continue
                enabled = not (int(entry.userAccountControl.value) & 2)
                object_guid = str(entry.objectGUID.value).strip('{}') if entry.objectGUID else None
                if not object_guid:
                    logger.warning(f"Запись {entry.entry_dn} не имеет 'objectGUID'")
                    continue
                computers.append({
                    "hostname": dns_hostname,
                    "os_name": entry.operatingSystem.value if entry.operatingSystem else None,
                    "object_guid": object_guid,
                    "when_created": entry.whenCreated.value if entry.whenCreated else None,
                    "when_changed": entry.whenChanged.value if entry.whenChanged else None,
                    "enabled": enabled,
                    "ad_notes": entry.description.value if entry.description else None,
                    "last_logon": entry.lastLogon.value if entry.lastLogon else None
                })
                logger.debug(f"Найден хост: {dns_hostname}, enabled: {enabled}, object_guid: {object_guid}")
            logger.info(f"Найдено {len(computers)} компьютеров в AD")
            return computers
        except Exception as e:
            logger.error(f"Ошибка подключения к LDAP: {str(e)}", exc_info=False)
            raise
        finally:
            if conn and conn.bound:
                conn.unbind()

    async def scan_and_update_ad(self, db: AsyncSession) -> None:
        """Сканирует AD и обновляет базу данных."""
        logger.info("Начало сканирования и обновления AD")
        computers = self.get_ad_computers()
        ad_guids = {c["object_guid"] for c in computers}

        # Обновление или создание записей
        for computer_data in computers:
            computer_data["last_updated"] = datetime.utcnow()
            computer_data["check_status"] = CheckStatus.disabled if not computer_data["enabled"] else CheckStatus.unreachable

            # Проверка за object_guid
            existing_computer = await self.repo.get_computer_by_guid(db, computer_data["object_guid"])
            if existing_computer:
                # Если компьютер существует, обновляем его поля
                logger.info(f"Обновление компьютера: {computer_data['hostname']} (GUID: {computer_data['object_guid']})")
                update_data = {
                    "hostname": computer_data["hostname"],
                    "os_name": computer_data["os_name"],
                    "when_created": computer_data["when_created"],
                    "when_changed": computer_data["when_changed"],
                    "enabled": computer_data["enabled"],
                    "ad_notes": computer_data["ad_notes"],
                    "last_updated": computer_data["last_updated"],
                    "last_logon": computer_data["last_logon"],
                    "check_status": computer_data["check_status"]
                }
                await self.repo.async_update_computer_by_guid(db, computer_data["object_guid"], update_data)
            else:
                # Если компьютера нет, создаем новый
                logger.info(f"Создание нового компьютера: {computer_data['hostname']} (GUID: {computer_data['object_guid']})")
                computer_data["check_status"] = CheckStatus.unreachable
                await self.repo.async_create_computer(db, computer_data)

        # Пометка удаленных компьютеров
        existing_computers = await self.repo.get_all_computers_with_guid(db)
        for computer in existing_computers:
            if computer.object_guid and computer.object_guid not in ad_guids:
                logger.info(f"Компьютер {computer.hostname} (GUID: {computer.object_guid}) удален из AD")
                await self.repo.async_update_computer_by_guid(
                    db,
                    computer.object_guid,
                    {
                        "enabled": False,
                        "last_updated": datetime.utcnow(),
                        "check_status": CheckStatus.is_deleted
                    }
                )

        await db.commit()
        logger.info(f"Успешно обработано {len(computers)} компьютеров AD")