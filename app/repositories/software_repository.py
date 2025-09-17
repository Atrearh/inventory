import logging
from datetime import datetime
from typing import Any, Dict, List
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from .. import models

logger = logging.getLogger(__name__)


class SoftwareRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def update_installed_software(self, db_computer: models.Computer, new_software_list: List[Dict[str, Any]]) -> None:
        """
        Updates installed software for a computer using the new logic.
        1. Finds or creates entries in `software_catalog`.
        2. Synchronizes the `installed_software` linking table.
        """
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
            for software_item in new_software_list:
                name = software_item.get("name")
                version = software_item.get("version")
                publisher = software_item.get("publisher")

                if not name:
                    continue

                # Create a unique key for the software item
                software_key = (name, version, publisher)
                incoming_software_keys.add(software_key)

                # Find or create an entry in the software catalog
                catalog_entry_result = await self.db.execute(
                    select(models.SoftwareCatalog).where(
                        models.SoftwareCatalog.name == name,
                        models.SoftwareCatalog.version == version,
                        models.SoftwareCatalog.publisher == publisher,
                    )
                )
                catalog_entry = catalog_entry_result.scalar_one_or_none()

                if not catalog_entry:
                    catalog_entry = models.SoftwareCatalog(name=name, version=version, publisher=publisher)
                    self.db.add(catalog_entry)
                    await self.db.flush()  # Flush to get the new ID

                # Check if this software is already linked to the computer
                if software_key in current_software_map:
                    # If it was previously removed, mark it as re-detected
                    installation_record = current_software_map[software_key]
                    if installation_record.removed_on is not None:
                        installation_record.removed_on = None
                else:
                    # Link the new software to the computer
                    new_installation = models.InstalledSoftware(
                        computer_id=db_computer.id,
                        software_id=catalog_entry.id,
                        install_date=software_item.get("install_date"),
                        detected_on=datetime.utcnow(),
                    )
                    self.db.add(new_installation)

            # Mark software that is no longer present as removed
            for key, installation in current_software_map.items():
                if key not in incoming_software_keys and installation.removed_on is None:
                    installation.removed_on = datetime.utcnow()

            await self.db.flush()

        except Exception as e:
            logger.error(f"Error updating installed software for computer {db_computer.id}: {str(e)}", exc_info=True)
            await self.db.rollback()
            raise
