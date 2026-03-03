from fastapi import FastAPI
from app.core.config import settings
from telegram import Update
import logging
from app.bot import run_bot, stop_bot
from contextlib import asynccontextmanager

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

bot_app = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up FastAPI application...")
    global bot_app
    bot_app = await run_bot()
    yield
    # Shutdown
    logger.info("Shutting down FastAPI application...")
    if bot_app:
        await stop_bot(bot_app)

app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

@app.get("/health")
async def health_check():
    return {"status": "ok", "environment": settings.ENVIRONMENT}

@app.post("/webhook")
async def telegram_webhook(update: dict):
    # If switching to webhooks in production, process updates here.
    # Currently defaults to polling in lifespan for development.
    return {"status": "ignored"}
