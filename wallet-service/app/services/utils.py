import logging
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)


def db_transaction(func):
    async def wrapper(self, *args, **kwargs):
        try:
            return await func(self, *args, **kwargs)
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Integrity error: {e}")
            raise
    return wrapper

def retry_optimistic_update(entity_id: str, update_fn, db, retries: int = 3):
    for attempt in range(1, retries + 1):
        if update_fn():
            return
        logger.warning(f"Optimistic lock failed for {entity_id}, retry {attempt}/{retries}")
        db.rollback()
    raise Exception(f"Failed to update {entity_id} after {retries} retries")

def commit_and_refresh(db, entity):
    db.commit()
    db.refresh(entity)
    return entity