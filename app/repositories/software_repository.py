import logging
import asyncio
from datetime import datetime
from typing import List, Optional
from time import perf_counter
from aiocache import Cache, cached
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from pydantic import BaseModel
from .. import models

logger = logging.getLogger(__name__)

class SoftwareItem(BaseModel):
    name: str
    version: Optional[str] = None
    publisher: Optional[str] = None
    install_date: Optional[datetime] = None

class SoftwareRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    @cached(ttl=300, cache=Cache.MEMORY, key_builder=lambda *args, **kwargs: f"software_catalog_{hash(str(kwargs))}")
    async def _get_software_catalog(self, name: str, version: Optional[str], publisher: Optional[str]) -> Optional[models.SoftwareCatalog]:
        start_time = perf_counter()
        try:
            result = await self.db.execute(
                select(models.SoftwareCatalog).where(
                    models.SoftwareCatalog.name == name,
                    models.SoftwareCatalog.version == (version or "Unknown"),
                    models.SoftwareCatalog.publisher == (publisher or "Unknown"),
                )
            )
            catalog_entry = result.scalar_one_or_none()
            logger.debug(f"Запит до SoftwareCatalog для {name} виконано за {perf_counter() - start_time:.4f}с")
            return catalog_entry
        except Exception as e:
            logger.error(f"Помилка при отриманні запису SoftwareCatalog: {str(e)}")
            raise

    async def update_installed_software(self, db_computer: models.Computer, new_software_list: List[SoftwareItem]) -> None:
        """
        Updates installed software for a computer using the new logic.
        1. Finds or creates entries in `software_catalog`.
        2. Synchronizes the `installed_software` linking table.
        """
        start_time = perf_counter()
        logger.debug(f"Оновлення ПЗ для комп’ютера {db_computer.id}")
        try:
            # Get all current software installations for this computer
            current_installations_result = await self.db.execute(
                select(models.InstalledSoftware)
                .options(selectinload(models.InstalledSoftware.software_details))
                .where(models.InstalledSoftware.computer_id == db_computer.id)
            )
            current_installations = current_installations_result.scalars().all()

            current_software_map = {
                (
                    inst.software_details.name,
                    inst.software_details.version,
                    inst.software_details.publisher,
                ): inst
                for inst in current_installations
            }

            incoming_software_keys = set()
            new_catalog_entries = []
            new_installations = []

            # Process incoming software list
            for software_item in new_software_list:
                if not software_item.name:
                    logger.warning(f"Пропущено ПЗ без назви: {software_item}")
                    continue

                software_key = (
                    software_item.name,
                    software_item.version or "Unknown",
                    software_item.publisher or "Unknown",
                )
                incoming_software_keys.add(software_key)

                # Find or create catalog entry
                catalog_entry = await self._get_software_catalog(
                    software_item.name,
                    software_item.version,
                    software_item.publisher
                )

                if not catalog_entry:
                    catalog_entry = models.SoftwareCatalog(
                        name=software_item.name,
                        version=software_item.version or "Unknown",
                        publisher=software_item.publisher or "Unknown",
                    )
                    new_catalog_entries.append(catalog_entry)

                # Check if this software is already linked to the computer
                if software_key in current_software_map:
                    installation_record = current_software_map[software_key]
                    if installation_record.removed_on is not None:
                        installation_record.removed_on = None
                else:
                    new_installation = models.InstalledSoftware(
                        computer_id=db_computer.id,
                        software_id=catalog_entry.id if catalog_entry.id else None,  # Will be set after flush
                        install_date=software_item.install_date,
                        detected_on=datetime.utcnow(),
                    )
                    new_installations.append((new_installation, catalog_entry))

            # Add new catalog entries
            if new_catalog_entries:
                self.db.add_all(new_catalog_entries)
                await self.db.flush()

            # Update software_id for new installations
            for installation, catalog_entry in new_installations:
                if not installation.software_id:
                    installation.software_id = catalog_entry.id
                self.db.add(installation)

            # Mark software that is no longer present as removed
            removed_count = 0
            for key, installation in current_software_map.items():
                if key not in incoming_software_keys and installation.removed_on is None:
                    installation.removed_on = datetime.utcnow()
                    removed_count += 1

            await self.db.commit()
            logger.debug(
                f"Оновлення ПЗ завершено для комп’ютера {db_computer.id}: "
                f"додано {len(new_installations)} нових, позначено видаленими {removed_count} за {perf_counter() - start_time:.4f}с"
            )

        except Exception as e:
            logger.error(f"Помилка оновлення ПЗ для комп’ютера {db_computer.id}: {str(e)}", exc_info=True)
            await self.db.rollback()
            raise