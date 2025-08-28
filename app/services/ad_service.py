# app/services/ad_service.py
import logging
from ldap3 import Server, Connection, ALL
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from ..repositories.computer_repository import ComputerRepository
from ..models import CheckStatus, Domain
from ..services.encryption_service import EncryptionService
from datetime import datetime 

logger = logging.getLogger(__name__)

class ADService:
    def __init__(self, repo: ComputerRepository, encryption_service: EncryptionService):
        self.repo = repo
        self.encryption_service = encryption_service  # Додаємо сервіс шифрування для роботи з паролями

    def get_ad_computers(self, domain: Domain) -> List[dict]:
        """Отримує список комп'ютерів із Active Directory для вказаного домену."""
        logger.debug(f"Початок сканування AD для домену: {domain.name}")
        
        # Перевіряємо наявність необхідних даних
        if not all([domain.server_url, domain.username, domain.encrypted_password, domain.ad_base_dn]):
            logger.error(f"Відсутні необхідні дані для домену {domain.name}")
            raise ValueError("Усі поля (server_url, username, password, ad_base_dn) є обов'язковими для підключення до LDAP")

        # Дешифруємо пароль
        try:
            password = self.encryption_service.decrypt(domain.encrypted_password)
            logger.debug(f"Пароль для домену {domain.name} успішно дешифровано")
        except Exception as e:
            logger.error(f"Помилка дешифрування пароля для домену {domain.name}: {str(e)}")
            raise ValueError(f"Помилка дешифрування пароля: {str(e)}")

        server = Server(domain.server_url, get_info=ALL)
        try:
            conn = Connection(server, user=domain.username, password=password, auto_bind=True)
            base_dn = domain.ad_base_dn
            logger.debug(f"Виконується пошук з base DN: {base_dn}, filter: (objectClass=computer)")

            conn.search(
                search_base=base_dn,
                search_filter="(objectClass=computer)",
                attributes=["dNSHostName", "operatingSystem", "objectGUID", "whenCreated", "whenChanged", "userAccountControl", "description", "lastLogon"]
            )
            logger.debug(f"Знайдено записів: {len(conn.entries)}")

            computers = []
            for entry in conn.entries:
                dns_hostname = entry.dNSHostName.value if entry.dNSHostName else None
                if not dns_hostname:
                    logger.warning(f"Запис {entry.entry_dn} не має 'dNSHostName'")
                    continue
                enabled = not (int(entry.userAccountControl.value) & 2)
                object_guid = str(entry.objectGUID.value).strip('{}') if entry.objectGUID else None
                if not object_guid:
                    logger.warning(f"Запис {entry.entry_dn} не має 'objectGUID'")
                    continue
                computers.append({
                    "hostname": dns_hostname,
                    "os_name": entry.operatingSystem.value if entry.operatingSystem else None,
                    "object_guid": object_guid,
                    "when_created": entry.whenCreated.value if entry.whenCreated else None,
                    "when_changed": entry.whenChanged.value if entry.whenChanged else None,
                    "enabled": enabled,
                    "ad_notes": entry.description.value if entry.description else None,
                    "last_logon": entry.lastLogon.value if entry.lastLogon else None,
                    "domain_id": domain.id  # Додаємо domain_id для зв’язку з доменом
                })
                logger.debug(f"Знайдено хост: {dns_hostname}, enabled: {enabled}, object_guid: {object_guid}")
            logger.info(f"Знайдено {len(computers)} комп'ютерів у AD для домену {domain.name}")
            return computers
        except Exception as e:
            logger.error(f"Помилка підключення до LDAP для домену {domain.name}: {str(e)}", exc_info=False)
            raise
        finally:
            if conn and conn.bound:
                conn.unbind()

async def scan_and_update_ad(self, db: AsyncSession, domain: Domain) -> None:
    logger.info(f"Початок сканування та оновлення AD для домену {domain.name}")
    computers_from_ad = self.get_ad_computers(domain)
    ad_guids = {c["object_guid"] for c in computers_from_ad}

    for computer_data in computers_from_ad:
        computer_data["check_status"] = CheckStatus.disabled if not computer_data["enabled"] else CheckStatus.unreachable

        # Крок 1: Спробувати знайти за GUID
        db_computer = await self.repo.get_computer_by_guid(db, computer_data["object_guid"])

        # Крок 2: Якщо не знайдено, спробувати знайти за hostname
        if not db_computer:
            db_computer = await self.repo.get_computer_by_hostname(db, computer_data["hostname"])

        update_data = {
            "hostname": computer_data["hostname"],
            "os_name": computer_data["os_name"],
            "when_created": computer_data["when_created"],
            "when_changed": computer_data["when_changed"],
            "enabled": computer_data["enabled"],
            "ad_notes": computer_data["ad_notes"],
            "last_logon": computer_data["last_logon"],
            "check_status": computer_data["check_status"],
            "domain_id": computer_data["domain_id"],
            "object_guid": computer_data["object_guid"]
        }

        if db_computer:
            # Якщо комп'ютер знайдено (за GUID або hostname), оновлюємо його
            logger.info(f"Оновлення комп'ютера: {computer_data['hostname']} (ID: {db_computer.id})")
            for key, value in update_data.items():
                setattr(db_computer, key, value)
        else:
            # Якщо комп'ютера немає, створюємо новий
            logger.info(f"Створення нового комп'ютера: {computer_data['hostname']}")
            await self.repo.async_create_computer(db, update_data)

        # Позначка видалених комп'ютерів
        existing_computers = await self.repo.get_all_computers_with_guid(db, domain_id=domain.id)
        for computer in existing_computers:
            if computer.object_guid and computer.object_guid not in ad_guids:
                logger.info(f"Комп'ютер {computer.hostname} (GUID: {computer.object_guid}) видалено з AD")
                await self.repo.async_update_computer_by_guid(
                    db,
                    computer.object_guid,
                    {
                        "enabled": False,
                        "check_status": CheckStatus.is_deleted
                    }
                )

    await db.commit()
    logger.info(f"Успішно оброблено {len(computers_from_ad)} комп'ютерів AD для домену {domain.name}")