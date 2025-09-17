# app/services/ad_service.py
import logging
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from ldap3 import ALL, Connection, Server
from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import CheckStatus, Computer, Domain
from ..repositories.computer_repository import ComputerRepository
from ..services.encryption_service import EncryptionService

logger = logging.getLogger(__name__)


class ADService:
    def __init__(self, repo: ComputerRepository, encryption_service: EncryptionService):
        self.repo = repo
        self.encryption_service = encryption_service

    def get_ad_computers(self, domain: Domain) -> List[dict]:
        """Отримує список комп'ютерів із Active Directory для вказаного домену."""
        logger.debug(f"Початок сканування AD для домену: {domain.name}")

        if not all(
            [
                domain.server_url,
                domain.username,
                domain.encrypted_password,
                domain.ad_base_dn,
            ]
        ):
            logger.error(f"Відсутні необхідні дані для домену {domain.name}")
            raise ValueError("Усі поля (server_url, username, password, ad_base_dn) є обов'язковими для підключення до LDAP")

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
                attributes=[
                    "dNSHostName",
                    "operatingSystem",
                    "objectGUID",
                    "whenCreated",
                    "whenChanged",
                    "userAccountControl",
                    "description",
                    "lastLogon",
                ],
            )
            logger.debug(f"Знайдено записів: {len(conn.entries)}")

            computers = []
            for entry in conn.entries:
                dns_hostname = entry.dNSHostName.value if entry.dNSHostName else None
                if not dns_hostname:
                    logger.warning(f"Запис {entry.entry_dn} не має 'dNSHostName'")
                    continue
                enabled = not (int(entry.userAccountControl.value) & 2)
                object_guid = str(entry.objectGUID.value).strip("{}") if entry.objectGUID else None
                if not object_guid:
                    logger.warning(f"Запис {entry.entry_dn} не має 'objectGUID'")
                    continue
                computers.append(
                    {
                        "hostname": dns_hostname,
                        "os_name": (entry.operatingSystem.value if entry.operatingSystem else None),
                        "object_guid": object_guid,
                        "when_created": (entry.whenCreated.value if entry.whenCreated else None),
                        "when_changed": (entry.whenChanged.value if entry.whenChanged else None),
                        "enabled": enabled,
                        "ad_notes": (entry.description.value if entry.description else None),
                        "last_logon": (entry.lastLogon.value if entry.lastLogon else None),
                        "domain_id": domain.id,
                    }
                )
                logger.debug(f"Знайдено хост: {dns_hostname}, enabled: {enabled}, object_guid: {object_guid}")
            logger.info(f"Знайдено {len(computers)} комп'ютерів у AD для домену {domain.name}")
            return computers
        except Exception as e:
            logger.error(
                f"Помилка підключення до LDAP для домену {domain.name}: {str(e)}",
                exc_info=False,
            )
            raise
        finally:
            if conn and conn.bound:
                conn.unbind()

    async def _prepare_computer_data(self, ad_computer: Dict) -> Dict:
        """Підготовка даних комп'ютера з AD для створення або оновлення."""
        return {
            "hostname": ad_computer["hostname"],
            "os_name": ad_computer["os_name"],
            "when_created": ad_computer["when_created"],
            "when_changed": ad_computer["when_changed"],
            "enabled": ad_computer["enabled"],
            "ad_notes": ad_computer["ad_notes"],
            "last_logon": ad_computer["last_logon"],
            "check_status": (CheckStatus.disabled if not ad_computer["enabled"] else CheckStatus.unreachable),
            "domain_id": ad_computer["domain_id"],
            "object_guid": ad_computer["object_guid"],
        }

    async def _compare_computer_data(self, db_computer: Computer, ad_data: Dict) -> Tuple[bool, Dict]:
        """Порівнює дані комп'ютера з БД та AD, повертає чи є зміни та словник оновлень."""
        update_data = {
            "hostname": ad_data["hostname"],
            "os_name": ad_data["os_name"],
            "when_created": ad_data["when_created"],
            "when_changed": ad_data["when_changed"],
            "enabled": ad_data["enabled"],
            "ad_notes": ad_data["ad_notes"],
            "last_logon": ad_data["last_logon"],
            "check_status": ad_data["check_status"],
            "domain_id": ad_data["domain_id"],
            "object_guid": ad_data["object_guid"],
        }
        changed_fields = []
        for key, value in update_data.items():
            db_value = getattr(db_computer, key)
            if value is not None and db_value != value:
                changed_fields.append((key, db_value, value))

        has_changes = len(changed_fields) > 0
        if has_changes:
            logger.debug(
                f"Комп'ютер {db_computer.hostname} (GUID: {db_computer.object_guid}) має зміни: "
                f"{', '.join(f'{field} з {old} на {new}' for field, old, new in changed_fields)}",
                extra={
                    "hostname": db_computer.hostname,
                    "changed_fields": changed_fields,
                },
            )

        return has_changes, update_data

    async def _get_computer_by_hostname_and_domain(self, db: AsyncSession, hostname: str, domain_id: int) -> Optional[Computer]:
        """Отримує комп'ютер за hostname та domain_id."""
        logger.debug(f"Перевірка наявності комп'ютера з hostname={hostname} і domain_id={domain_id}")
        try:
            return await self.repo.get_computer_by_hostname_and_domain(db, hostname, domain_id)
        except Exception as e:
            logger.error(
                f"Помилка пошуку комп'ютера за hostname={hostname} і domain_id={domain_id}: {str(e)}",
                exc_info=True,
            )
            raise

    async def _check_duplicate_hostnames_in_ad(self, computers: List[Dict], domain: Domain) -> List[Dict]:
        """Перевіряє та обробляє дублікати hostname у списку комп'ютерів з AD."""
        hostname_count = defaultdict(list)
        for computer in computers:
            hostname_count[computer["hostname"].lower()].append(computer)

        unique_computers = []
        for hostname, comp_list in hostname_count.items():
            if len(comp_list) > 1:
                logger.warning(f"Знайдено {len(comp_list)} дублікатів hostname {hostname} у домені {domain.name}")
                # Вибираємо найновіший запис за when_changed
                latest_computer = max(comp_list, key=lambda c: c["when_changed"] or datetime.min)
                logger.info(f"Вибрано найновіший запис для {hostname}: GUID={latest_computer['object_guid']}")
                unique_computers.append(latest_computer)
            else:
                unique_computers.append(comp_list[0])
        return unique_computers

    async def scan_and_update_ad(self, db: AsyncSession, domain: Domain, batch_size: int = 1000) -> None:
        """Асинхронно сканує AD та оновлює комп'ютери в БД з пакетною обробкою."""
        logger.info(f"Початок сканування та оновлення AD для домену {domain.name}, batch_size={batch_size}")

        try:
            # Крок 1: Отримуємо дані з AD і перевіряємо дублікати hostname
            start_time = datetime.utcnow()
            computers_from_ad = self.get_ad_computers(domain)
            computers_from_ad = await self._check_duplicate_hostnames_in_ad(computers_from_ad, domain)
            ad_guids = {c["object_guid"] for c in computers_from_ad}
            logger.debug(f"Отримано {len(computers_from_ad)} унікальних комп'ютерів з AD за {(datetime.utcnow() - start_time).total_seconds():.2f} сек")

            # Крок 2: Отримуємо дані з БД
            start_time = datetime.utcnow()
            existing_computers = await self.repo.get_all_computers_by_domain_id(db, domain_id=domain.id)
            db_computers_dict = {c.object_guid: c for c in existing_computers if c.object_guid}
            db_hostname_domain_dict = {(c.hostname.lower(), c.domain_id): c for c in existing_computers}
            logger.debug(f"Отримано {len(existing_computers)} комп'ютерів з БД за {(datetime.utcnow() - start_time).total_seconds():.2f} сек")

            # Крок 3: Визначаємо дії
            computers_to_create = []
            computers_to_update = []
            computers_to_delete = []

            start_time = datetime.utcnow()
            for ad_computer in computers_from_ad:
                ad_guid = ad_computer["object_guid"]
                hostname = ad_computer["hostname"].lower()
                domain_id = ad_computer["domain_id"]

                computer_data = await self._prepare_computer_data(ad_computer)

                # Спершу шукаємо за GUID - найнадійніший спосіб
                db_computer = db_computers_dict.get(ad_guid)

                if db_computer:
                    # Знайдено за GUID, перевіряємо на зміни
                    has_changes, update_data = await self._compare_computer_data(db_computer, computer_data)
                    if has_changes:
                        logger.debug(f"Комп'ютер {hostname} (GUID: {ad_guid}) має зміни і буде оновлено.")
                        computers_to_update.append((db_computer, update_data))
                else:
                    # Не знайдено за GUID, шукаємо за hostname + domain_id
                    db_computer_by_hostname = db_hostname_domain_dict.get((hostname, domain_id))
                    if db_computer_by_hostname:
                        # Знайдено за іменем, але GUID інший (або відсутній). Оновлюємо існуючий запис.
                        logger.debug(
                            f"Комп'ютер {hostname} знайдено за іменем, але з іншим GUID. Оновлюємо GUID з {db_computer_by_hostname.object_guid} на {ad_guid}."
                        )
                        has_changes, update_data = await self._compare_computer_data(db_computer_by_hostname, computer_data)
                        computers_to_update.append((db_computer_by_hostname, update_data))
                    else:
                        # Не знайдено ні за GUID, ні за іменем. Це новий комп'ютер.
                        logger.debug(f"Комп'ютер {hostname} (GUID: {ad_guid}) буде створено.")
                        computers_to_create.append(computer_data)

            for db_computer in existing_computers:
                if db_computer.object_guid and db_computer.object_guid not in ad_guids:
                    logger.debug(f"Комп'ютер {db_computer.hostname} (GUID: {db_computer.object_guid}) видалено з AD")
                    computers_to_delete.append(db_computer.object_guid)

            logger.debug(
                f"Порівняння завершено за {(datetime.utcnow() - start_time).total_seconds():.2f} сек: "
                f"створити={len(computers_to_create)}, оновити={len(computers_to_update)}, видалити={len(computers_to_delete)}"
            )

            # Крок 4: Пакетне створення комп'ютерів
            start_time = datetime.utcnow()
            for i in range(0, len(computers_to_create), batch_size):
                batch = computers_to_create[i : i + batch_size]
                logger.info(f"Створення {len(batch)} нових комп'ютерів")
                try:
                    await db.execute(
                        insert(Computer),
                        [
                            {
                                "hostname": c["hostname"],
                                "os_name": c["os_name"],
                                "when_created": c["when_created"],
                                "when_changed": c["when_changed"],
                                "enabled": c["enabled"],
                                "ad_notes": c["ad_notes"],
                                "last_logon": c["last_logon"],
                                "check_status": c["check_status"],
                                "domain_id": c["domain_id"],
                                "object_guid": c["object_guid"],
                                "last_updated": datetime.utcnow(),
                            }
                            for c in batch
                        ],
                    )
                except IntegrityError as e:
                    logger.error(
                        f"Помилка цілісності при створенні комп'ютерів: {str(e)}",
                        exc_info=True,
                    )
                    for c in batch:
                        existing_computer = await self._get_computer_by_hostname_and_domain(db, c["hostname"], c["domain_id"])
                        if existing_computer:
                            logger.warning(f"Дубльований комп'ютер: {c['hostname']} (domain_id={c['domain_id']}), оновлюємо замість створення")
                            has_changes, update_data = await self._compare_computer_data(existing_computer, c)
                            if has_changes or existing_computer.object_guid != c["object_guid"]:
                                update_data["object_guid"] = c["object_guid"]
                                for key, value in update_data.items():
                                    setattr(existing_computer, key, value)
                                existing_computer.last_updated = datetime.utcnow()
                                computers_to_update.append((existing_computer, update_data))
                        else:
                            logger.error(f"Невідома помилка для {c['hostname']} (domain_id={c['domain_id']}): {str(e)}")
                    continue  # Продовжуємо обробку інших пакетів

            logger.debug(f"Створення завершено за {(datetime.utcnow() - start_time).total_seconds():.2f} сек")

            # Крок 5: Пакетне оновлення комп'ютерів
            start_time = datetime.utcnow()
            for db_computer, update_data in computers_to_update:
                logger.info(f"Оновлення комп'ютера: {db_computer.hostname} (ID: {db_computer.id})")
                for key, value in update_data.items():
                    setattr(db_computer, key, value)
                db_computer.last_updated = datetime.utcnow()
            logger.debug(f"Оновлення завершено за {(datetime.utcnow() - start_time).total_seconds():.2f} сек")

            # Крок 6: Пакетне позначення видалених комп'ютерів
            start_time = datetime.utcnow()
            for i in range(0, len(computers_to_delete), batch_size):
                batch = computers_to_delete[i : i + batch_size]
                logger.info(f"Позначення {len(batch)} комп'ютерів як видалених")
                for guid in batch:
                    await self.repo.async_update_computer_by_guid(
                        db,
                        guid,
                        {"enabled": False, "check_status": CheckStatus.is_deleted, "last_updated": datetime.utcnow()},
                    )
            logger.debug(f"Видалення завершено за {(datetime.utcnow() - start_time).total_seconds():.2f} сек")

            # Крок 7: Фіксація транзакції
            await db.commit()
            logger.info(
                f"Успішно оброблено {len(computers_from_ad)} комп'ютерів AD для домену {domain.name}: "
                f"створено={len(computers_to_create)}, оновлено={len(computers_to_update)}, видалено={len(computers_to_delete)}"
            )

        except Exception as e:
            logger.error(
                f"Помилка сканування AD для домену {domain.name}: {str(e)}",
                exc_info=True,
            )
            await db.rollback()
            raise ValueError(f"Помилка сканування AD: {str(e)}")
