from app.services.dvr_service import DVRService
from app.schemas import DahuaDVRCreate
import logging

async def process_dvr_host(self, host: str, logger_adapter: logging.LoggerAdapter) -> bool:
    try:

        dvr_service = DVRService(self.db)
        raw_data = await dvr_service.fetch_dvr_data(host)
        if not raw_data:
            logger_adapter.warning(f"DVR {host} не вдалося отримати дані.")
            return False
        dvr_data = DahuaDVRCreate(
            hostname=host,
            device_type="dahua_dvr",
            name=raw_data.get("name"),
            port=raw_data.get("port", 37777)
        ).model_dump(exclude_unset=True)
        dvr_id = await self.computer_repo.async_upsert_dvr(dvr=DahuaDVRCreate(**dvr_data), hostname=host)
        await self.db.commit()
        logger_adapter.info(f"DVR {host} успішно оброблено.")
        return True
    except Exception as e:
        logger_adapter.error(f"Помилка при обробці DVR {host}: {e}", exc_info=True)
        await self.db.rollback()
        return False