from app.controllers import history_router
from app.services import kafka_consumer
from contextlib import asynccontextmanager
import asyncio
import logging


from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting History Service...")

    await kafka_consumer.start()
    logger.info("Kafka consumer initialized")

    consumer_task = asyncio.create_task(kafka_consumer.consume_events())
    logger.info("Kafka consumer task started in background")

    yield 
    
    logger.info("Shutting down History Service...")
    
    await kafka_consumer.stop()

    try:
        await asyncio.wait_for(consumer_task, timeout=30.0)
    except asyncio.TimeoutError:
        logger.warning("Consumer task timeout, forcing cancellation...")
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            logger.info("Consumer task cancelled")
    
    logger.info("History Service shutdown complete")


app = FastAPI(title="History Service",lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(history_router)

@app.get("/")
async def root():
    return {"message": "History Service API", "status": "running"}
