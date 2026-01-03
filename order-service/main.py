from fastapi import FastAPI
import os
from contextlib import asynccontextmanager

from app.api.v1 import orders
from app.core.database import init_db
from app.core.product_client import close_product_client
from app.core.event_consumer import start_event_consumer, stop_event_consumer
from shared.logging_config import setup_logging, get_logger
from shared.config import get_settings

settings = get_settings()
setup_logging(service_name=os.getenv("SERVICE_NAME", "order-service"), log_level=settings.app.log_level)
logger = get_logger(__name__, os.getenv("SERVICE_NAME", "order-service"))
logger.debug(f'log level: {settings.app.log_level}')


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting order-service...")
    try:
        init_db()
        logger.info("Database initialized")
        
        # Start event consumer for inventory events
        try:
            await start_event_consumer()
            logger.info("Event consumer started")
        except Exception as e:
            logger.error(f"Error starting event consumer: {e}", exc_info=True)
            # Don't fail startup if event consumer fails - service can still function
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise
    
    yield
    
    logger.info("Shutting down order-service...")
    try:
        await stop_event_consumer()
        logger.info("Event consumer stopped")
    except Exception as e:
        logger.error(f"Error stopping event consumer: {e}", exc_info=True)
    
    await close_product_client()
    logger.info("Order service shut down complete")


app = FastAPI(
    title="Order Service",
    description="Order management service for TheOne ecommerce platform",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(orders.router)


@app.get("/")
def read_root():
    return {"message": "order-service", "status": "running"}


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "order-service"}


# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8002)
