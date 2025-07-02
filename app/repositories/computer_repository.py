from typing import List, Optional, Tuple
from datetime import datetime
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
import logging
from .. import models, schemas
from sqlalchemy.orm import selectinload
logger = logging.getLogger(__name__)

class ComputerRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_or_create_computer(self, computer_data: dict, hostname: str) -> models.Computer:
        try:
            result = await self.db.execute(
                select(models.Computer).where(models.Computer.hostname == hostname)
            )
            db_computer = result.scalars().first()

            if db_computer:
                # Оновлюємо лише змінені поля
                for key, value in computer_data.items():
                    setattr(db_computer, key, value)
            else:
                db_computer = models.Computer(**computer_data)
                self.db.add(db_computer)

            await self.db.flush()
            return db_computer
        except Exception as e:
            logger.error(f"Помилка при отриманні/створенні комп’ютера {hostname}: {str(e)}")
            raise

    async def async_upsert_computer(self, computer: schemas.ComputerCreate, hostname: str, mode: str = "Full") -> int:
        try:
            computer_data = computer.model_dump(
                include={
                    "hostname", "os_name", "os_version", "ram",
                    "motherboard", "last_boot", "is_virtual", "check_status"
                }
            )
            computer_data["last_updated"] = datetime.utcnow()
            if mode == "Full":
                computer_data["last_full_scan"] = datetime.utcnow()

            db_computer = await self._get_or_create_computer(computer_data, hostname)
            return db_computer.id
        except SQLAlchemyError as e:
            logger.error(f"Помилка бази даних при збереженні комп’ютера {hostname}: {str(e)}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Помилка збереження комп’ютера {hostname}: {str(e)}", exc_info=True)
            raise

    async def _computer_to_pydantic(self, computer: models.Computer) -> schemas.ComputerList:
        logger.debug(f"Преобразование компьютера {computer.id} в Pydantic-схему")
        try:
            logger.debug(f"Raw data: roles={len(computer.roles)}, software={len(computer.software)}, disks={len(computer.disks)}"
                         f"ram={computer.ram}")
            
            result = schemas.ComputerList(
                id=computer.id,
                hostname=computer.hostname,
                ip_addresses=[schemas.IPAddress(address=ip.address) for ip in computer.ip_addresses] if computer.ip_addresses else [],
                mac_addresses=[schemas.MACAddress(address=mac.address) for mac in computer.mac_addresses] if computer.mac_addresses else [],
                os_name=computer.os_name,
                os_version=computer.os_version,
                ram=computer.ram,
                motherboard=computer.motherboard,
                last_boot=computer.last_boot,
                last_full_scan=computer.last_full_scan,
                is_virtual=computer.is_virtual,
                check_status=computer.check_status.value if computer.check_status else None,
                last_updated=computer.last_updated.isoformat() if computer.last_updated else None,
                disks=[schemas.Disk(
                    device_id=disk.device_id,
                    model=disk.model or "Unknown",
                    total_space=disk.total_space,
                    free_space=disk.free_space,
                    serial=disk.serial,
                    interface=disk.interface,
                    media_type=disk.media_type,
                    volume_label=disk.volume_label
                ) for disk in computer.disks] if computer.disks else [],
                software=[schemas.Software(
                    name=soft.name,
                    version=soft.version or "Unknown",
                    install_date=soft.install_date.isoformat() if soft.install_date else None,
                    action=soft.action or "Installed",
                    is_deleted=soft.is_deleted
                ) for soft in computer.software] if computer.software else [],
                roles=[schemas.Role(name=role.name) for role in computer.roles] if computer.roles else [],
                video_cards=[schemas.VideoCard(
                    name=card.name,
                    driver_version=card.driver_version
                ) for card in computer.video_cards] if computer.video_cards else [],
                processors=[schemas.Processor(
                    name=proc.name,
                    number_of_cores=proc.number_of_cores,
                    number_of_logical_processors=proc.number_of_logical_processors
                ) for proc in computer.processors] if computer.processors else []
            )
            logger.debug(f"Transformed data: roles={len(result.roles or [])}, software={len(result.software or [])}, "
                        f"disks={len(result.disks or [])}, "
                        f"disks_data={[{'device_id': d.device_id, 'total_space': d.total_space, 'free_space': d.free_space} for d in result.disks]}"
                        f"ram={computer.ram}")
            return result
        except Exception as e:
            logger.error(f"Ошибка преобразования компьютера {computer.id} в Pydantic-схему: {str(e)}")
            raise

    async def get_computers(
        self,
        hostname: Optional[str] = None,
        os_name: Optional[str] = None,
        check_status: Optional[str] = None,
        sort_by: str = "hostname",
        sort_order: str = "asc",
        page: int = 1,
        limit: int = 10,
        server_filter: Optional[str] = None,
    ) -> Tuple[List[schemas.ComputerList], int]:
        logger.debug(f"Запрос компьютеров с фильтрами: hostname={hostname}, os_name={os_name}, server_filter={server_filter}")

        try:
            query = select(models.Computer).options(
                selectinload(models.Computer.disks),
                selectinload(models.Computer.software),
                selectinload(models.Computer.roles),
                selectinload(models.Computer.video_cards),
                selectinload(models.Computer.processors),
                selectinload(models.Computer.ip_addresses),
                selectinload(models.Computer.mac_addresses)
            )

            if hostname:
                query = query.filter(models.Computer.hostname.ilike(f"%{hostname}%"))
            if os_name:
                query = query.filter(models.Computer.os_name.ilike(f"%{os_name}%"))
            if check_status:
                query = query.filter(models.Computer.check_status == check_status)
            if server_filter == "server":
                query = query.filter(models.Computer.os_name.ilike("%server%"))
            elif server_filter == "client":
                query = query.filter(~models.Computer.os_name.ilike("%server%"))

            if sort_by in ["hostname", "os_name", "last_updated"]:
                order_column = getattr(models.Computer, sort_by)
                if sort_order.lower() == "desc":
                    order_column = order_column.desc()
                query = query.order_by(order_column)
            else:
                query = query.order_by(models.Computer.hostname)

            count_query = select(func.count()).select_from(query.subquery())
            result = await self.db.execute(count_query)
            total = result.scalar()

            query = query.offset((page - 1) * limit).limit(limit)
            result = await self.db.execute(query)
            computers = result.scalars().all()

            pydantic_computers = [await self._computer_to_pydantic(computer) for computer in computers]
            return pydantic_computers, total

        except SQLAlchemyError as e:
            logger.error(f"Ошибка базы данных при получении списка компьютеров: {str(e)}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Неожиданная ошибка при получении списка компьютеров: {str(e)}", exc_info=True)
            raise

    async def async_get_computer_by_id(self, computer_id: int) -> Optional[schemas.ComputerList]:
        logger.debug(f"Запрос компьютера по ID: {computer_id}")
        try:
            stmt = select(models.Computer).options(
                selectinload(models.Computer.roles),
                selectinload(models.Computer.disks),
                selectinload(models.Computer.software),
                selectinload(models.Computer.ip_addresses),
                selectinload(models.Computer.processors),
                selectinload(models.Computer.mac_addresses),
                selectinload(models.Computer.video_cards)
            ).filter(models.Computer.id == computer_id)

            result = await self.db.execute(stmt)
            computer = result.scalars().first()

            if computer:
                logger.debug(
                    f"Компьютер {computer.id}: roles={len(computer.roles)}, "
                    f"software={len(computer.software)}, disks={len(computer.disks)}, "
                    f"ip_addresses={len(computer.ip_addresses)}, processors={len(computer.processors)}, "
                    f"mac_addresses={len(computer.mac_addresses)}, video_cards={len(computer.video_cards)}"
                )
                return await self._computer_to_pydantic(computer)
            else:
                logger.warning(f"Компьютер с ID {computer_id} не найден")
                return None
        except SQLAlchemyError as e:
            logger.error(f"Ошибка базы данных при получении компьютера ID {computer_id}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Неизвестная ошибка при получении компьютера ID {computer_id}: {str(e)}")
            raise
        
    async def async_update_computer_check_status(self, hostname: str, check_status: str) -> Optional[models.Computer]:
        try:
            result = await self.db.execute(
                select(models.Computer).filter(models.Computer.hostname == hostname)
            )
            db_computer = result.scalar_one_or_none()
            if db_computer:
                try:
                    new_check_status = models.CheckStatus(check_status)
                except ValueError:
                    logger.error(f"Недопустиме значення check_status: {check_status}")
                    return None
                if db_computer.check_status != new_check_status:
                    db_computer.check_status = new_check_status
                    db_computer.last_updated = datetime.utcnow()
                    logger.info(f"Оновлено check_status для {hostname}: {new_check_status}")
                return db_computer
            return None
        except Exception as e:
            logger.error(f"Помилка оновлення check_status для {hostname}: {str(e)}", exc_info=True)
            raise