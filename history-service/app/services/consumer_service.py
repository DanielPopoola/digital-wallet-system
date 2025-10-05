import asyncio
import json
import logging
from contextlib import contextmanager
from typing import Optional
from aiokafka import AIOKafkaConsumer


from app.config import get_settings
from app.database import SessionLocal
from app.services.history_service import HistoryService
from app.schemas import (
    EventType,
    WalletCreatedEvent,
    WalletFundedEvent,
    TransferCompletedEvent,
    TransferFailedEvent,
    WalletEvent,
)

logger = logging.getLogger(__name__)
settings = get_settings()


@contextmanager
def get_db_context():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def deserialize_event(event_dict: dict) -> Optional[WalletEvent]:
    try:
        event_type = event_dict.get('event_type')

        if event_type == EventType.WALLET_CREATED.value:
            return WalletCreatedEvent(**event_dict)
        
        elif event_type == EventType.WALLET_FUNDED.value:
            return WalletFundedEvent(**event_dict)
        
        elif event_type == EventType.TRANSFER_COMPLETED.value:
            return TransferCompletedEvent(**event_dict)
        
        elif event_type == EventType.TRANSFER_FAILED.value:
            return TransferFailedEvent(**event_dict)
        
        else:
            logger.error(f"Unknown event type: {event_type}")
            return None
        
    except Exception as e:
        logger.error(f"Failed to deserialize event: {e}, data: {event_dict}")
        return None


class KafkaConsumerService:
    def __init__(self):
        self.bootstrap_servers = settings.kafka_broker
        self.topic = settings.kafka_topic
        self.group_id = "history-service-group"
        self.consumer: Optional[AIOKafkaConsumer] = None
        self._shutdown = False

    def request_shutdown(self):
        logger.info("Shutdown requested for Kafka consumer")
        self._shutdown = True

    async def start(self):
        for attempt in range(5):
            try:
                self.consumer = AIOKafkaConsumer(
                    self.topic,
                    bootstrap_servers=self.bootstrap_servers,
                    group_id=self.group_id,
                    auto_offset_reset='earliest',
                    enable_auto_commit=False,
                    value_deserializer=lambda m: json.loads(m.decode('utf-8'))
                )
                await self.consumer.start()
                logger.info(
                    f"Kafka consumer started: topic={self.topic}, "
                    f"group={self.group_id}"
                )
                return
            except Exception as e:
                logger.error(f"Failed to start Kafka consumer (attempt {attempt+1}): {e}")
                await asyncio.sleep(2 ** attempt)

        raise RuntimeError("Kafka consumer could not be started after retries")
    
    async def stop(self):
        if self.consumer:
            await self.consumer.stop()
            logger.info("Kafka consumer stopped")

    async def consume_events(self):
        global shutdown_requested
        logger.info("Starting to consume events...")

        try:
            async for message in self.consumer:
                if self._shutdown:
                    logger.info("Shutdown requested, stopping consumption...")
                    break

                try:
                    event_dict = message.value
                    logger.debug(f"Received message: {event_dict}")

                    event = deserialize_event(event_dict)
                    if event is None:
                        logger.error(f"Could not deserialize event, skipping: {event_dict}")
                        await self.consumer.commit()
                        continue

                    with get_db_context() as db:
                        history_service = HistoryService(db)
                        history_service.process_event(event)

                    await self.consumer.commit()

                except Exception as e:
                    logger.error(f"Error processing message: {e}", exc_info=True)
                    await asyncio.sleep(5)

        except Exception as e:
            logger.error(f"Consumer loop error: {e}", exc_info=True)
            raise
        finally:
            logger.info("Consumer loop ended")

kafka_consumer = KafkaConsumerService()
