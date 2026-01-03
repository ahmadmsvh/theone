import json
import asyncio
from typing import Optional, Dict, Any
from uuid import UUID
import os

import aio_pika
from shared.logging_config import get_logger
from shared.config import get_settings
from shared.rabbitmq import RabbitMQConsumer, RabbitMQConnection
from shared.models import InventoryMessage, MessageType
from app.core.database import get_db_manager
from app.repositories.order_repository import OrderRepository
from app.repositories.payment_repository import PaymentRepository
from app.services.order_service import OrderService
from app.services.payment_service import PaymentService
from app.core.product_client import ProductServiceClient
from app.models import OrderStatus, Payment
from app.core.events import publish_order_cancelled_event

logger = get_logger(__name__, "order-service")

MAX_RETRIES = 3
RETRY_DELAY_BASE = 2


class InventoryEventConsumer:
    """Event consumer for inventory events, specifically inventory.unavailable"""
    
    def __init__(self):
        self.settings = get_settings()
        self._consumer: Optional[RabbitMQConsumer] = None
        self._connection: Optional[RabbitMQConnection] = None
        self._service_name = "order-service"
        self._running = False
        self._consumer_task: Optional[asyncio.Task] = None
    
    async def _get_connection(self) -> RabbitMQConnection:
        if self._connection is None:
            try:
                self._connection = RabbitMQConnection()
                await self._connection.connect()
                logger.info("RabbitMQ connection established for inventory event consumer")
            except Exception as e:
                logger.error(f"Failed to initialize RabbitMQ connection: {e}")
                raise
        return self._connection
    
    def _get_db_session(self):
        """Get database session"""
        db_manager = get_db_manager()
        return db_manager.get_session()
    
    async def _handle_inventory_unavailable(self, message_data: Dict[str, Any]) -> bool:
        """
        Handle inventory.unavailable event.
        Cancels the order and refunds payment if applicable.
        """
        try:
            inventory_message = InventoryMessage(**message_data)
            order_id_str = inventory_message.order_id
            
            if not order_id_str:
                logger.warning(f"inventory.unavailable event missing order_id: {message_data}")
                return False
            
            order_id = UUID(order_id_str)
            product_id = inventory_message.product_id
            
            logger.info(
                f"Processing inventory.unavailable event for order {order_id}, product {product_id}"
            )
            
            db_session = self._get_db_session()
            try:
                order_repo = OrderRepository(db_session)
                payment_repo = PaymentRepository(db_session)
                product_client = ProductServiceClient()
                payment_service = PaymentService()
                order_service = OrderService(
                    repository=order_repo,
                    product_client=product_client,
                    payment_repository=payment_repo,
                    payment_service=payment_service
                )
                
                # Get the order
                order = order_repo.get_order_by_id(order_id)
                if not order:
                    logger.warning(f"Order {order_id} not found for inventory.unavailable event")
                    return False
                
                # Skip if order is already cancelled or completed
                if order.status in [OrderStatus.CANCELLED, OrderStatus.DELIVERED]:
                    logger.info(
                        f"Order {order_id} is already {order.status.value}, skipping cancellation"
                    )
                    return True
                
                # Cancel the order
                old_status = order.status
                cancelled_order = order_service.cancel_order(order_id)
                order_repo.commit()
                
                logger.info(f"Order {order_id} cancelled due to inventory.unavailable")
                
                # Publish order cancelled event
                await publish_order_cancelled_event(cancelled_order)
                
                # Refund payment if order was paid
                if old_status == OrderStatus.PAID:
                    # Find the successful payment
                    payment = (
                        payment_repo.db.query(Payment)
                        .filter(Payment.order_id == order_id, Payment.status == "succeeded")
                        .first()
                    )
                    
                    if payment and payment.transaction_id:
                        try:
                            from decimal import Decimal
                            refund_result = await payment_service.refund_payment(
                                transaction_id=payment.transaction_id,
                                amount=Decimal(str(payment.amount))
                            )
                            logger.info(
                                f"Refund processed for order {order_id}, "
                                f"transaction_id: {payment.transaction_id}, "
                                f"refund_id: {refund_result.get('refund_id')}"
                            )
                        except Exception as refund_error:
                            logger.error(
                                f"Failed to refund payment for order {order_id}, "
                                f"transaction_id: {payment.transaction_id}: {refund_error}",
                                exc_info=True
                            )
                            # Continue even if refund fails - order is already cancelled
                    else:
                        logger.warning(
                            f"No successful payment found for order {order_id} to refund"
                        )
                
                return True
                
            finally:
                db_session.close()
                
        except Exception as e:
            logger.error(
                f"Error handling inventory.unavailable event: {e}",
                exc_info=True
            )
            return False
    
    async def _process_with_retry(
        self,
        message_data: Dict[str, Any],
        handler: callable,
        max_retries: int = MAX_RETRIES
    ) -> bool:
        """Process message with retry logic"""
        for attempt in range(max_retries):
            try:
                return await handler(message_data)
            except Exception as e:
                if attempt < max_retries - 1:
                    delay = RETRY_DELAY_BASE * (2 ** attempt)
                    logger.warning(
                        f"Error processing message (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {delay}s..."
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
            
            logger.info(
                f"Received message: {message_data.get('message_id', 'unknown')}, "
                f"type: {message_type}, routing_key: {routing_key}"
            )
            
            handler = None
            if message_type == MessageType.INVENTORY_UNAVAILABLE.value or routing_key == "inventory.unavailable":
                handler = self._handle_inventory_unavailable
            
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
            logger.error(f"Unexpected error processing message: {e}", exc_info=True)
            await message.nack(requeue=False)
    
    async def _create_consumer(self) -> RabbitMQConsumer:
        connection = await self._get_connection()
        
        consumer = InventoryEventRabbitMQConsumer(
            queue_name="inventory_events",
            routing_keys=["inventory.unavailable"],
            connection=connection,
            event_handler=self
        )
        
        return consumer
    
    async def _run_consumer(self):
        try:
            self._running = True
            logger.info("Starting inventory event consumer...")
            
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
    
    async def start(self):
        """Start the event consumer"""
        if self._running:
            logger.warning("Event consumer is already running")
            return
        
        try:
            self._consumer_task = asyncio.create_task(self._run_consumer())
            logger.info("Inventory event consumer task started")
        except Exception as e:
            logger.error(f"Failed to start inventory event consumer: {e}", exc_info=True)
            self._running = False
            raise
    
    async def stop(self):
        """Stop the event consumer"""
        if not self._running:
            return
        
        self._running = False
        
        try:
            if self._consumer:
                await self._consumer.stop_consuming()
            
            if self._consumer_task:
                self._consumer_task.cancel()
                try:
                    await self._consumer_task
                except asyncio.CancelledError:
                    pass
            
            if self._connection:
                await self._connection.close()
            
            logger.info("Inventory event consumer stopped")
            
        except Exception as e:
            logger.error(f"Error stopping inventory event consumer: {e}")


class InventoryEventRabbitMQConsumer(RabbitMQConsumer):
    """Custom RabbitMQ consumer for inventory events"""
    
    def __init__(self, queue_name: str, routing_keys: list, connection, event_handler):
        super().__init__(queue_name, routing_keys, connection, callback=None)
        self.event_handler = event_handler
    
    async def process_message(self, message: aio_pika.IncomingMessage):
        await self.event_handler._process_message_async(message)


_event_consumer: Optional[InventoryEventConsumer] = None


async def get_event_consumer() -> InventoryEventConsumer:
    global _event_consumer
    if _event_consumer is None:
        _event_consumer = InventoryEventConsumer()
    return _event_consumer


async def start_event_consumer():
    consumer = await get_event_consumer()
    await consumer.start()


async def stop_event_consumer():
    global _event_consumer
    if _event_consumer:
        await _event_consumer.stop()
        _event_consumer = None
