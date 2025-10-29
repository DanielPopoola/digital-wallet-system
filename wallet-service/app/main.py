from app.exceptions import WalletNotFoundError, InsufficientBalanceError, OptimisticLockError
from app.services import kafka_producer
from app.controllers import wallet_router, user_router


from contextlib import asynccontextmanager
import logging


from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting wallet service")

    await kafka_producer.start()
    logger.info("Kafka producer started")

    yield

    await kafka_producer.stop()
    logger.info("App stopped, Kafka disconnected")


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(WalletNotFoundError)
async def wallet_not_found_handler(request: Request, exc: WalletNotFoundError):
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc)}
    )

@app.exception_handler(InsufficientBalanceError)
async def insufficient_balance_handler(request: Request, exc: InsufficientBalanceError):
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)}
    )

@app.exception_handler(OptimisticLockError)
async def optimistic_lock_handler(request: Request, exc: OptimisticLockError):
    return JSONResponse(
        status_code=409,
        content={"detail": str(exc)}
    )

app.include_router(wallet_router)
app.include_router(user_router)

@app.get("/")
async def root():
    return {"message": "Digital Wallet API", "status": "running"}