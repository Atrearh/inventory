import logging
from datetime import datetime
from typing import Union, AsyncGenerator, Dict, List, Optional, Tuple, Any
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload
from sqlmodel import func
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy import select, and_
from .. import models
from ..decorators import log_function_call
from ..schemas import ComputerCreate, ComputerListItem

logger = logging.getLogger(__name__)


class ComputerRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _get_base_computer_query(self):
        """Базовий запит для вибірки комп'ютерів з пов'язаними сутностями."""
        return select(models.Computer).options(
            selectinload(models.Computer.ip_addresses),
            selectinload(models.Computer.mac_addresses),
            selectinload(models.Computer.processors),
            selectinload(models.Computer.video_cards),
            selectinload(models.Computer.physical_disks).selectinload(models.PhysicalDisk.logical_disks),
            selectinload(models.Computer.os),
            selectinload(models.Computer.installed_software).selectinload(models.InstalledSoftware.software_details),
            selectinload(models.Computer.roles),
            selectinload(models.Computer.logical_disks),
            selectinload(models.Computer.domain),
        )

    def _apply_computer_filters(
        self,
        query,
        hostname: Optional[str] = None,
        os_name: Optional[str] = None,
        check_status: Optional[str] = None,
        server_filter: Optional[str] = None,
        domain_id: Optional[int] = None,
        ip_range: Optional[str] = None,
        guid_not_null: bool = False,
    ):
        """Централізована логіка застосування фільтрів до запитів."""
        if hostname:
            query = query.filter(models.Computer.hostname.ilike(f"%{hostname}%"))
        if os_name:
            query = query.join(models.OperatingSystem).filter(models.OperatingSystem.name.ilike(f"%{os_name}%"))
        if check_status:
            query = query.filter(models.Computer.check_status == check_status)
        if server_filter == "server":
            query = query.join(models.OperatingSystem).filter(models.OperatingSystem.name.ilike("%Server%"))
        elif server_filter == "client":
            query = query.filter(~models.Computer.os_name.ilike("%server%"))
        if domain_id:
            query = query.filter(models.Computer.domain_id == domain_id)
        if ip_range and ip_range != "none":
            query = query.join(models.IPAddress).filter(models.IPAddress.address.ilike(f"{ip_range}%"))
        if guid_not_null:
            query = query.filter(models.Computer.object_guid.isnot(None))
        return query

    async def _computer_to_pydantic(self, computers: List[models.Computer]) -> List[ComputerListItem]:
        """Перетворює список моделей Computer у Pydantic-схему ComputerListItem."""
        try:
            return [ComputerListItem.model_validate(comp, from_attributes=True) for comp in computers]
        except Exception as e:
            logger.error(f"Помилка перетворення в Pydantic-схему: {str(e)}")
            raise

    def _build_computer_query_light(
        self,
        hostname: Optional[str] = None,
        os_name: Optional[str] = None,
        check_status: Optional[str] = None,
        server_filter: Optional[str] = None,
    ):
        """Легкий запит для потокового виведення з мінімальними зв’язками."""
        query = select(models.Computer).options(
            selectinload(models.Computer.ip_addresses),
        )
        return self._apply_computer_filters(
            query,
            hostname=hostname,
            os_name=os_name,
            check_status=check_status,
            server_filter=server_filter,
        )

    @log_function_call
    async def get_computer(
        self,
        id: Optional[int] = None,
        guid: Optional[str] = None,
        hostname: Optional[str] = None,
        domain_id: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        stream: bool = False,
        page: int = 1,
        limit: int = 10,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
    ) -> Union[
        Tuple[List[ComputerListItem], int],
        Tuple[AsyncGenerator[ComputerListItem, None], None],
    ]:
        """
        Базовий метод для отримання комп'ютерів за ідентифікатором, GUID, hostname або фільтрами.
        Повертає список або генератор (якщо stream=True) та загальну кількість (для пагінації).
        """
        try:
            query = self._get_base_computer_query()

            # Застосування фільтрів за ідентифікаторами
            if id is not None:
                query = query.filter(models.Computer.id == id)
            if guid is not None:
                query = query.filter(models.Computer.object_guid == guid)
            if hostname is not None:
                query = query.filter(models.Computer.hostname.ilike(hostname.lower()))
            if domain_id is not None:
                query = query.filter(models.Computer.domain_id == domain_id)

            # Застосування додаткових фільтрів
            if filters:
                query = self._apply_computer_filters(
                    query,
                    hostname=filters.get("hostname"),
                    os_name=filters.get("os_name"),
                    check_status=filters.get("check_status"),
                    server_filter=filters.get("server_filter"),
                    domain_id=filters.get("domain_id"),
                    ip_range=filters.get("ip_range"),
                    guid_not_null=filters.get("guid_not_null", False),
                )

            # Виключення видалених комп'ютерів
            query = query.filter(
                and_(
                    models.Computer.check_status != "disabled",
                    models.Computer.check_status != "is_deleted",
                )
            )

            # Сортування
            if sort_by:
                sort_column = None
                if sort_by == "hostname":
                    sort_column = models.Computer.hostname
                elif sort_by == "last_updated":
                    sort_column = models.Computer.last_updated
                elif sort_by == "os_name":
                    query = query.join(models.OperatingSystem)
                    sort_column = models.OperatingSystem.name
                else:
                    logger.warning(f"Непідтримуваний параметр сортування: {sort_by}")
                    sort_column = models.Computer.hostname

                if sort_order and sort_order.lower() == "desc":
                    query = query.order_by(sort_column.desc())
                else:
                    query = query.order_by(sort_column.asc())

            # Обробка потокового виведення
            if stream:
                query = self._build_computer_query_light(
                    hostname=filters.get("hostname"),
                    os_name=filters.get("os_name"),
                    check_status=filters.get("check_status"),
                    server_filter=filters.get("server_filter"),
                )
                result = await self.db.stream(query)

                async def generator():
                    async for row in result:
                        computer_obj = row[0]
                        yield ComputerListItem.model_validate(computer_obj, from_attributes=True)

                return generator(), None

            # Підрахунок загальної кількості для пагінації
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await self.db.execute(count_query)
            total = total_result.scalar_one()

            # Пагінація
            query = query.offset((page - 1) * limit).limit(limit)

            # Виконання запиту
            result = await self.db.execute(query)
            computers = result.unique().scalars().all()

            # Перетворення в Pydantic-модель
            pydantic_computers = await self._computer_to_pydantic(computers)

            return pydantic_computers, total

        except SQLAlchemyError as e:
            logger.error(f"Помилка отримання комп'ютерів: {str(e)}", exc_info=True)
            raise

    async def create_computer(self, data: Dict[str, Any]) -> models.Computer:
        """Базовий метод для створення комп'ютера."""
        try:
            computer = models.Computer(**data)
            self.db.add(computer)
            await self.db.flush()
            logger.debug(
                f"Комп'ютер створено з ID {computer.id}",
                extra={"hostname": data.get("hostname")},
            )
            return computer
        except SQLAlchemyError as e:
            logger.error(
                f"Помилка створення комп'ютера: {str(e)}",
                extra={"hostname": data.get("hostname")},
            )
            await self.db.rollback()
            raise

    async def update_computer(self, id: int, data: Dict[str, Any]) -> None:
        """Базовий метод для оновлення комп'ютера за ID."""
        try:
            await self.db.execute(models.Computer.__table__.update().where(models.Computer.id == id).values(**data))
            logger.debug("Комп'ютер оновлено за ID", extra={"computer_id": id})
        except SQLAlchemyError as e:
            logger.error(
                f"Помилка оновлення комп'ютера за ID: {str(e)}",
                extra={"computer_id": id},
            )
            await self.db.rollback()
            raise

    async def delete_computer(self, id: int) -> bool:
        """Базовий метод для видалення комп'ютера за ID."""
        try:
            result = await self.db.execute(select(models.Computer).filter(models.Computer.id == id))
            computer = result.scalars().first()
            if not computer:
                logger.warning("Комп'ютер не знайдено", extra={"computer_id": id})
                return False
            await self.db.delete(computer)
            await self.db.commit()
            logger.debug("Комп'ютер видалено", extra={"computer_id": id})
            return True
        except SQLAlchemyError as e:
            logger.error(
                f"Помилка видалення комп'ютера: {str(e)}",
                extra={"computer_id": id},
            )
            await self.db.rollback()
            raise

    @log_function_call
    async def get_or_create_computer(self, computer_data: Dict[str, Any], hostname: str) -> models.Computer:
        """Обгортка: отримує або створює комп'ютер за hostname."""
        try:
            computers, _ = await self.get_computer(hostname=hostname)
            db_computer = computers[0] if computers else None

            if db_computer:
                for key, value in computer_data.items():
                    setattr(db_computer, key, value)
            else:
                db_computer = await self.create_computer(computer_data)

            logger.debug("Комп’ютер отримано або створено", extra={"hostname": hostname})
            return db_computer
        except SQLAlchemyError as e:
            logger.error(
                f"Помилка при отриманні/створенні комп’ютера: {str(e)}",
                extra={"hostname": hostname},
            )
            raise

    async def async_upsert_computer(self, computer: ComputerCreate, hostname: str, mode: str = "Full") -> int:
        """Обгортка: оновлює або створює комп'ютер."""
        try:
            computer_data = computer.model_dump(
                include={
                    "hostname",
                    "os_name",
                    "os_version",
                    "ram",
                    "motherboard",
                    "last_boot",
                    "check_status",
                    "object_guid",
                    "when_created",
                    "when_changed",
                    "enabled",
                    "ad_notes",
                    "local_notes",
                }
            )
            logger.debug(f"Дані для оновлення: {computer_data}", extra={"hostname": hostname})

            protected_fields = ["when_created", "when_changed", "enabled", "ad_notes"]
            computer_data = {k: v for k, v in computer_data.items() if k not in protected_fields or v is not None}

            if not computer_data.get("when_created"):
                logger.debug(
                    "Відсутній when_created у даних сканування, пропускаємо оновлення",
                    extra={"hostname": hostname},
                )
            if not computer_data.get("ad_notes"):
                logger.debug(
                    "Відсутній ad_notes у даних сканування, пропускаємо оновлення",
                    extra={"hostname": hostname},
                )

            computer_data["last_updated"] = datetime.utcnow()
            if mode == "Full":
                computer_data["last_full_scan"] = datetime.utcnow()

            db_computer = await self.get_or_create_computer(computer_data, hostname)
            await self.db.flush()
            await self.db.commit()
            logger.debug(
                f"Комп’ютер збережено з ID {db_computer.id}",
                extra={"hostname": hostname},
            )

            return db_computer.id
        except SQLAlchemyError as e:
            logger.error(f"Помилка збереження комп’ютера: {str(e)}", extra={"hostname": hostname})
            await self.db.rollback()
            raise

    async def get_all_computers_with_guid(self, domain_id: Optional[int] = None) -> List[models.Computer]:
        """Обгортка: отримує всі комп'ютери з непорожнім GUID."""
        try:
            computers, _ = await self.get_computer(filters={"guid_not_null": True, "domain_id": domain_id})
            return [computer for computer in computers]
        except SQLAlchemyError as e:
            logger.error(f"Помилка отримання комп'ютерів з GUID: {str(e)}", exc_info=True)
            raise

    async def get_computer_by_hostname_and_domain(self, hostname: str, domain_id: int) -> Optional[models.Computer]:
        """Обгортка: отримує комп'ютер за hostname та domain_id."""
        try:
            computers, _ = await self.get_computer(hostname=hostname, domain_id=domain_id)
            return computers[0] if computers else None
        except SQLAlchemyError as e:
            logger.error(
                f"Помилка пошуку комп'ютера за hostname={hostname} і domain_id={domain_id}: {str(e)}",
                exc_info=True,
            )
            raise

    async def async_update_computer_check_status(self, hostname: str, check_status: str) -> Optional[models.Computer]:
        """Обгортка: оновлює check_status комп'ютера за hostname."""
        try:
            computers, _ = await self.get_computer(hostname=hostname)
            db_computer = computers[0] if computers else None
            if not db_computer:
                logger.warning("Комп’ютер не знайдено", extra={"hostname": hostname})
                return None
            new_check_status = models.CheckStatus(check_status)
            if db_computer.check_status != new_check_status:
                await self.update_computer(db_computer.id, {"check_status": new_check_status})
                logger.debug(f"Статус оновлено до {check_status}", extra={"hostname": hostname})
            return db_computer
        except ValueError:
            logger.error(
                f"Недопустиме значення check_status: {check_status}",
                extra={"hostname": hostname},
            )
            raise
        except SQLAlchemyError as e:
            logger.error(f"Помилка оновлення статусу: {str(e)}", extra={"hostname": hostname})
            raise

    async def get_computers_list(
        self,
        domain_id: Optional[int] = None,
        check_status: Optional[str] = None,
        os_name: Optional[str] = None,
        ip_range: Optional[str] = None,
        server_filter: Optional[str] = None,
        hostname: Optional[str] = None,
        page: int = 1,
        limit: int = 10,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
    ) -> Tuple[List[ComputerListItem], int]:
        """Обгортка: отримує список комп'ютерів із пагінацією та фільтрами."""
        try:
            filters = {
                "hostname": hostname,
                "os_name": os_name,
                "check_status": check_status,
                "server_filter": server_filter,
                "domain_id": domain_id,
                "ip_range": ip_range,
            }
            return await self.get_computer(
                filters=filters,
                page=page,
                limit=limit,
                sort_by=sort_by,
                sort_order=sort_order,
            )
        except SQLAlchemyError as e:
            logger.error(f"Помилка при отриманні списку комп'ютерів: {str(e)}", exc_info=True)
            raise

    @log_function_call
    async def get_computer_details_by_id(self, computer_id: int) -> Optional[models.Computer]:
        """
        Отримує детальну інформацію про комп'ютер за його ID з усіма пов'язаними даними.

        Args:
            computer_id: ID комп'ютера.

        Returns:
            Об'єкт models.Computer або None, якщо комп'ютер не знайдено.
        """
        try:
            query = self._get_base_computer_query().filter(models.Computer.id == computer_id)
            result = await self.db.execute(query)
            computer = result.scalars().first()
            return computer
        except SQLAlchemyError as e:
            logger.error(f"Помилка отримання комп'ютера {computer_id}: {str(e)}", exc_info=True)
            raise

    async def get_computer_by_hostname(self, hostname: str) -> Optional[models.Computer]:
        """Обгортка: отримує комп'ютер за hostname."""
        try:
            computers, _ = await self.get_computer(hostname=hostname)
            return computers[0].model_validate(computers[0], from_attributes=True) if computers else None
        except SQLAlchemyError as e:
            logger.error(
                f"Помилка отримання комп'ютера за hostname: {str(e)}",
                extra={"hostname": hostname},
            )
            raise

    async def stream_computers(
        self,
        hostname: Optional[str] = None,
        os_name: Optional[str] = None,
        check_status: Optional[str] = None,
        server_filter: Optional[str] = None,
    ) -> AsyncGenerator[ComputerListItem, None]:
        """Обгортка: потокове отримання комп'ютерів із фільтрами."""
        try:
            filters = {
                "hostname": hostname,
                "os_name": os_name,
                "check_status": check_status,
                "server_filter": server_filter,
            }
            async for computer in (await self.get_computer(filters=filters, stream=True))[0]:
                yield computer
        except SQLAlchemyError as e:
            logger.error(f"Помилка потокового отримання комп’ютерів: {str(e)}")
            raise

    async def get_all_hosts(self) -> List[str]:
        """Обгортка: отримує список усіх hostname."""
        try:
            result = await self.db.execute(select(models.Computer.hostname))
            return [row[0] for row in result.fetchall()]
        except SQLAlchemyError as e:
            logger.error(f"Помилка отримання хостів: {str(e)}")
            raise
