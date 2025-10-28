import asyncio
import json
import logging
from typing import Optional
from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError


from app.config import get_settings
from shared.schemas import WalletEvent, TransferCompletedEvent, TransferFailedEvent


logger = logging.getLogger(__name__)
settings = get_settings()


class KafkaProducerService:
    def __init__(self):
        self.bootstrap_servers = settings.kafka_broker
        self.topic = settings.kafka_topic
        self.producer: Optional[AIOKafkaProducer] = None

    async def start(self):
        for attempt in range(5):
            try:
                self.producer = AIOKafkaProducer(
                    bootstrap_servers=self.bootstrap_servers,
                    value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
                    acks="all",
                )
                await self.producer.start()
                logger.info(f"Kafka producer started: {self.bootstrap_servers}")
                return
            except Exception as e:
                logger.error(f"Failed to start Kafka producer (attempt {attempt+1}): {e}")
                await asyncio.sleep(2 ** attempt)
        raise RuntimeError("Kafka producer could not be started after retries")
    
    async def stop(self):
        if self.producer:
            await self.producer.stop()
            logger.info("Kafka producer stopped")

    async def publish_event(self, event: WalletEvent) -> bool:
        if not self.producer:
            logger.error("Kafka producer not initialized")
            raise

        try:
            event_dict = event.model_dump(mode='json')
            if isinstance(event, (TransferCompletedEvent, TransferFailedEvent)):
                keys = [event.from_wallet_id.encode("utf-8"), event.to_wallet_id.encode("utf-8")]
            else:
                keys = [event.wallet_id.encode("utf-8")]

            for key in keys:
                await self.producer.send_and_wait(self.topic, value=event_dict, key=key)

            logger.info(f"Published event: {event.event_type} for wallet {keys}")
            return True
        except KafkaError as e:
            logger.error(f"Kafka error publishing event: {e}")
            return False
        except Exception as e:
            logger.error(f"Error publishing event: {e}")
            return False


kafka_producer = KafkaProducerService()