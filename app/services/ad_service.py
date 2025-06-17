# app/services/ad_service.py
import logging
from ldap3 import Server, Connection, ALL
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from ..settings import settings
from ..repositories.computer_repository import ComputerRepository

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
                attributes=["dNSHostName", "operatingSystem", "objectGUID", "whenCreated", "whenChanged", "userAccountControl"]
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
                computers.append({
                    "hostname": dns_hostname,
                    "os_name": entry.operatingSystem.value if entry.operatingSystem else None,
                    "object_guid": object_guid,
                    "when_created": entry.whenCreated.value if entry.whenCreated else None,
                    "when_changed": entry.whenChanged.value if entry.whenChanged else None,
                    "enabled": enabled
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
        for computer_data in computers:
            await self.repo.async_upsert_ad_computer(computer_data)  # Убрали db, так как метод уже использует сессию из repo
        logger.info(f"Успешно обработано {len(computers)} компьютеров AD")