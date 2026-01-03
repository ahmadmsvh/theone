from uuid import uuid4
from datetime import datetime, timezone
from typing import Optional

from shared.rabbitmq import RabbitMQPublisher
from shared.models import OrderMessage, MessageType
from app.models import Order, OrderStatus
from shared.logging_config import get_logger

logger = get_logger(__name__, "order-service")


async def publish_order_created_event(order: Order):
    try:
        publisher = RabbitMQPublisher()
        
        items = [
            {
                "product_id": str(item.product_id),
                "sku": item.sku,
                "quantity": item.quantity,
                "price": float(item.price)
            }
            for item in order.items
        ]
        
        message = OrderMessage(
            message_id=str(uuid4()),
            message_type=MessageType.ORDER_CREATED,
            timestamp=datetime.now(timezone.utc),
            source_service="order-service",
            correlation_id=None,
            metadata={},
            order_id=str(order.id),
            user_id=str(order.user_id),
            status=order.status.value,
            total_amount=float(order.total),
            items=items
        )
        
        await publisher.publish(message, routing_key="order.created")
        logger.info(f"Published order.created event for order {order.id}")
        
    except Exception as e:
        logger.error(f"Error publishing order.created event for order {order.id}: {e}", exc_info=True)


async def publish_order_status_updated_event(order: Order, old_status: OrderStatus):
    try:
        publisher = RabbitMQPublisher()
        
        items = [
            {
                "product_id": str(item.product_id),
                "sku": item.sku,
                "quantity": item.quantity,
                "price": float(item.price)
            }
            for item in order.items
        ]
        
        message = OrderMessage(
            message_id=str(uuid4()),
            message_type=MessageType.ORDER_UPDATED,
            timestamp=datetime.now(timezone.utc),
            source_service="order-service",
            correlation_id=None,
            metadata={
                "old_status": old_status.value,
                "new_status": order.status.value
            },
            order_id=str(order.id),
            user_id=str(order.user_id),
            status=order.status.value,
            total_amount=float(order.total),
            items=items
        )
        
        await publisher.publish(message, routing_key="order.updated")
        logger.info(f"Published order.updated event for order {order.id} (status: {old_status.value} -> {order.status.value})")
        
    except Exception as e:
        logger.error(f"Error publishing order.updated event for order {order.id}: {e}", exc_info=True)


async def publish_order_cancelled_event(order: Order):
    try:
        publisher = RabbitMQPublisher()
        
        items = [
            {
                "product_id": str(item.product_id),
                "sku": item.sku,
                "quantity": item.quantity,
                "price": float(item.price)
            }
            for item in order.items
        ]
        
        message = OrderMessage(
            message_id=str(uuid4()),
            message_type=MessageType.ORDER_CANCELLED,
            timestamp=datetime.now(timezone.utc),
            source_service="order-service",
            correlation_id=None,
            metadata={},
            order_id=str(order.id),
            user_id=str(order.user_id),
            status=order.status.value,
            total_amount=float(order.total),
            items=items
        )
        
        await publisher.publish(message, routing_key="order.cancelled")
        logger.info(f"Published order.cancelled event for order {order.id}")
        
    except Exception as e:
        logger.error(f"Error publishing order.cancelled event for order {order.id}: {e}", exc_info=True)


async def publish_order_paid_event(order: Order, transaction_id: str, payment_method: Optional[str] = None):
    try:
        publisher = RabbitMQPublisher()
        
        items = [
            {
                "product_id": str(item.product_id),
                "sku": item.sku,
                "quantity": item.quantity,
                "price": float(item.price)
            }
            for item in order.items
        ]
        
        message = OrderMessage(
            message_id=str(uuid4()),
            message_type=MessageType.ORDER_PAID,
            timestamp=datetime.now(timezone.utc),
            source_service="order-service",
            correlation_id=None,
            metadata={
                "transaction_id": transaction_id,
                "payment_method": payment_method or "unknown"
            },
            order_id=str(order.id),
            user_id=str(order.user_id),
            status=order.status.value,
            total_amount=float(order.total),
            items=items
        )
        
        await publisher.publish(message, routing_key="order.paid")
        logger.info(f"Published order.paid event for order {order.id} (transaction_id: {transaction_id})")
        
    except Exception as e:
        logger.error(f"Error publishing order.paid event for order {order.id}: {e}", exc_info=True)

