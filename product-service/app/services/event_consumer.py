import json
import asyncio
from typing import Optional, Dict, Any, Callable
from datetime import datetime
import os

import aio_pika
from shared.logging_config import get_logger
from shared.config import get_settings
from shared.rabbitmq import RabbitMQConsumer, RabbitMQConnection
from shared.models import OrderMessage, MessageType
from app.core.database import get_db_manager
from app.repositories.product_repository import ProductRepository

logger = get_logger(__name__, os.getenv("SERVICE_NAME"))

MAX_RETRIES = 3
RETRY_DELAY_BASE = 2  


class OrderEventConsumer:
    def __init__(self):
        self.settings = get_settings()
        self._consumer: Optional[RabbitMQConsumer] = None
        self._connection: Optional[RabbitMQConnection] = None
        self._service_name = os.getenv("SERVICE_NAME", "product-service")
        self._running = False
        self._consumer_task: Optional[asyncio.Task] = None
    
    async def _get_connection(self) -> RabbitMQConnection:
        if self._connection is None:
            try:
                self._connection = RabbitMQConnection()
                await self._connection.connect()
                logger.info("RabbitMQ connection established for consumer")
            except Exception as e:
                logger.error(f"Failed to initialize RabbitMQ connection: {e}")
                raise
        return self._connection
    
    def _get_db_manager(self):
        return get_db_manager()
    
    async def _handle_order_completed(self, message_data: Dict[str, Any]) -> bool:

        try:
            order_message = OrderMessage(**message_data)
            order_id = order_message.order_id
            items = order_message.items
            
            logger.info(f"Processing order.completed event for order {order_id}")
            
            db_manager = self._get_db_manager()
            await db_manager.connect()
            database = await db_manager.get_database()
            repository = ProductRepository(database)
            
            processed_items = []
            errors = []
            
            for item in items:
                try:
                    product_id = item.get("product_id")
                    quantity = item.get("quantity", 0)
                    
                    if not product_id or quantity <= 0:
                        logger.warning(f"Invalid item in order {order_id}: {item}")
                        continue
                        
                    updated_product = await repository.complete_order_deduction(
                        product_id=str(product_id),
                        quantity=int(quantity)
                    )
                    
                    if updated_product:
                        processed_items.append({
                            "product_id": product_id,
                            "quantity": quantity,
                            "new_stock": updated_product.stock,
                            "new_reserved_stock": updated_product.reserved_stock
                        })
                        logger.info(
                            f"Completed order deduction for product {product_id}: "
                            f"deducted {quantity}, new stock: {updated_product.stock}, "
                            f"new reserved: {updated_product.reserved_stock}"
                        )
                    else:
                        errors.append(f"Product {product_id} not found")
                        logger.error(f"Product {product_id} not found for order {order_id}")
                        
                except ValueError as e:
                    error_msg = f"Validation error for product {item.get('product_id')}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
                except Exception as e:
                    error_msg = f"Error processing item {item.get('product_id')}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg, exc_info=True)
            
            if errors:
                logger.warning(
                    f"Order {order_id} completed with {len(errors)} errors: {errors}"
                )
                return len(processed_items) > 0
            
            logger.info(
                f"Successfully processed order.completed for order {order_id}: "
                f"{len(processed_items)} items processed"
            )
            return True
            
        except Exception as e:
            logger.error(f"Error handling order.completed event: {e}", exc_info=True)
            return False
    
    async def _handle_order_cancelled(self, message_data: Dict[str, Any]) -> bool:
        try:
            order_message = OrderMessage(**message_data)
            order_id = order_message.order_id
            items = order_message.items
            
            logger.info(f"Processing order.cancelled event for order {order_id}")
            
            db_manager = self._get_db_manager()
            await db_manager.connect()
            database = await db_manager.get_database()
            repository = ProductRepository(database)
            
            processed_items = []
            errors = []
            
            for item in items:
                try:
                    product_id = item.get("product_id")
                    quantity = item.get("quantity", 0)
                    
                    if not product_id or quantity <= 0:
                        logger.warning(f"Invalid item in order {order_id}: {item}")
                        continue
                    
                    updated_product = await repository.release_stock(
                        product_id=str(product_id),
                        quantity=int(quantity)
                    )
                    
                    if updated_product:
                        processed_items.append({
                            "product_id": product_id,
                            "quantity": quantity,
                            "new_reserved_stock": updated_product.reserved_stock
                        })
                        logger.info(
                            f"Released inventory for product {product_id}: "
                            f"released {quantity}, new reserved: {updated_product.reserved_stock}"
                        )
                    else:
                        errors.append(f"Product {product_id} not found")
                        logger.error(f"Product {product_id} not found for order {order_id}")
                        
                except ValueError as e:
                    error_msg = f"Validation error for product {item.get('product_id')}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
                except Exception as e:
                    error_msg = f"Error processing item {item.get('product_id')}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg, exc_info=True)
            
            if errors:
                logger.warning(
                    f"Order {order_id} cancelled with {len(errors)} errors: {errors}"
                )       
                return len(processed_items) > 0
            
            logger.info(
                f"Successfully processed order.cancelled for order {order_id}: "
                f"{len(processed_items)} items processed"
            )
            return True
            
        except Exception as e:
            logger.error(f"Error handling order.cancelled event: {e}", exc_info=True)
            return False
    
    async def _process_with_retry(
        self,
        message_data: Dict[str, Any],
        handler: Callable,
        max_retries: int = MAX_RETRIES
    ) -> bool:
        last_error = None
        
        for attempt in range(max_retries):
            try:
                result = await handler(message_data)
                if result:
                    return True
                logger.warning(f"Handler returned False, not retrying")
                return False
                
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    delay = RETRY_DELAY_BASE ** attempt
                    logger.warning(
                        f"Error processing message (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {delay} seconds..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"Failed to process message after {max_retries} attempts: {e}",
                        exc_info=True
                    )
        
        return False
    
    async def _process_message_async(self, message: aio_pika.IncomingMessage):
        try:
            message_data = json.loads(message.body.decode('utf-8'))
            message_type = message_data.get("message_type")
            routing_key = message.routing_key or message_type
            
            logger.info(f"Received message: {message_data.get('message_id', 'unknown')}, type: {message_type}, routing_key: {routing_key}")
            
            handler = None
            if message_type == MessageType.ORDER_COMPLETED.value or routing_key == "order.completed":
                handler = self._handle_order_completed
            elif message_type == MessageType.ORDER_CANCELLED.value or routing_key == "order.cancelled":
                handler = self._handle_order_cancelled
            elif message_type == MessageType.ORDER_UPDATED.value:
                status = message_data.get("status", "")
                if status.lower() == "completed":
                    handler = self._handle_order_completed
                elif status.lower() == "cancelled":
                    handler = self._handle_order_cancelled
            
            if handler is None:
                logger.warning(f"Unknown message type or routing key: {message_type}/{routing_key}")
                await message.ack()
                return
            
            success = await self._process_with_retry(message_data, handler)
            
            if success:
                logger.info(f"Successfully processed message {message_data.get('message_id', 'unknown')}")
                await message.ack()
            else:
                logger.error(f"Failed to process message {message_data.get('message_id', 'unknown')} after retries")
                await message.nack(requeue=False)
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode message: {e}")
            await message.nack(requeue=False)
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            await message.nack(requeue=True)
    
    async def _create_consumer(self) -> RabbitMQConsumer:
        connection = await self._get_connection()
        
        routing_keys = ["order.completed", "order.cancelled"]
        
        consumer = OrderEventRabbitMQConsumer(
            queue_name="order_events",
            routing_keys=routing_keys,
            connection=connection,
            event_handler=self
        )
        
        return consumer
    
    async def _run_consumer(self):
        try:
            self._running = True
            logger.info("Starting order event consumer...")
            
            self._consumer = await self._create_consumer()
            await self._consumer.setup_queue()
            
            await self._consumer.start_consuming()
            
            while self._running:
                await asyncio.sleep(1)
            
        except asyncio.CancelledError:
            logger.info("Consumer task cancelled")
            self._running = False
        except Exception as e:
            logger.error(f"Error in consumer loop: {e}", exc_info=True)
            self._running = False
            raise
    
    def start(self):
        if self._running:
            logger.warning("Consumer is already running")
            return
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                raise RuntimeError("Event loop is closed")
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        self._consumer_task = loop.create_task(self._run_consumer())
        logger.info("Order event consumer task started")
    
    async def stop(self):
        self._running = False
        if self._consumer_task:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass
        
        if self._consumer:
            try:
                await self._consumer.stop_consuming()
                logger.info("Stopped order event consumer")
            except Exception as e:
                logger.error(f"Error stopping consumer: {e}")
        
        if self._connection:
            try:
                await self._connection.close()
            except Exception as e:
                logger.error(f"Error closing connection: {e}")


class OrderEventRabbitMQConsumer(RabbitMQConsumer):
    
    def __init__(self, queue_name: str, routing_keys: list, connection, event_handler):
        super().__init__(queue_name, routing_keys, connection, callback=None)
        self.event_handler = event_handler
    
    async def process_message(self, message: aio_pika.IncomingMessage):
        await self.event_handler._process_message_async(message)


_event_consumer: Optional[OrderEventConsumer] = None

def get_event_consumer() -> OrderEventConsumer:
    global _event_consumer
    if _event_consumer is None:
        _event_consumer = OrderEventConsumer()
    return _event_consumer
