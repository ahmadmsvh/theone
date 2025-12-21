import json
import logging
from typing import Callable, Optional, Dict, Any, List
from functools import wraps
import pika
from pika.exceptions import AMQPConnectionError, AMQPChannelError
from pika.adapters.blocking_connection import BlockingChannel

from .config import get_settings
from .models import BaseMessage

logger = logging.getLogger(__name__)


class RabbitMQConnection:
    """RabbitMQ connection manager"""
    
    def __init__(self, connection_url: Optional[str] = None):
        self.settings = get_settings()
        self.connection_url = connection_url or self.settings.rabbitmq.url
        self._connection: Optional[pika.BlockingConnection] = None
        self._channel: Optional[BlockingChannel] = None
    
    def connect(self):
        """Establish connection to RabbitMQ"""
        if self._connection is None or self._connection.is_closed:
            try:
                parameters = pika.URLParameters(self.connection_url)
                self._connection = pika.BlockingConnection(parameters)
                self._channel = self._connection.channel()
                
                # Declare exchange
                self._channel.exchange_declare(
                    exchange=self.settings.rabbitmq.exchange,
                    exchange_type='topic',
                    durable=True
                )
                
                logger.info("RabbitMQ connection established successfully")
            except AMQPConnectionError as e:
                logger.error(f"Failed to connect to RabbitMQ: {e}")
                raise
    
    @property
    def channel(self) -> BlockingChannel:
        """Get channel instance"""
        if self._channel is None or self._channel.is_closed:
            self.connect()
        return self._channel
    
    def close(self):
        """Close RabbitMQ connection"""
        try:
            if self._channel and not self._channel.is_closed:
                self._channel.close()
            if self._connection and not self._connection.is_closed:
                self._connection.close()
            logger.info("RabbitMQ connection closed")
        except Exception as e:
            logger.error(f"Error closing RabbitMQ connection: {e}")
    
    def health_check(self) -> bool:
        """Check RabbitMQ health"""
        try:
            if self._connection is None or self._connection.is_closed:
                self.connect()
            return self._connection.is_open
        except Exception as e:
            logger.error(f"RabbitMQ health check failed: {e}")
            return False


class RabbitMQPublisher:
    """Base class for publishing messages to RabbitMQ"""
    
    def __init__(self, connection: Optional[RabbitMQConnection] = None):
        self.connection = connection or RabbitMQConnection()
        self.settings = get_settings()
    
    def publish(self, message: BaseMessage, routing_key: Optional[str] = None):
        """
        Publish a message to RabbitMQ
        
        Args:
            message: Message object to publish
            routing_key: Optional routing key (defaults to message_type)
        """
        try:
            channel = self.connection.channel
            routing_key = routing_key or message.message_type.value
            
            message_body = message.model_dump_json()
            
            channel.basic_publish(
                exchange=self.settings.rabbitmq.exchange,
                routing_key=routing_key,
                body=message_body,
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Make message persistent
                    content_type='application/json',
                    correlation_id=message.correlation_id,
                )
            )
            
            logger.info(f"Published message {message.message_id} with routing key {routing_key}")
        except (AMQPConnectionError, AMQPChannelError) as e:
            logger.error(f"Failed to publish message: {e}")
            raise
    
    def publish_raw(self, message_body: str, routing_key: str, headers: Optional[Dict[str, Any]] = None):
        """
        Publish raw message to RabbitMQ
        
        Args:
            message_body: JSON string message body
            routing_key: Routing key
            headers: Optional message headers
        """
        try:
            channel = self.connection.channel
            
            properties = pika.BasicProperties(
                delivery_mode=2,
                content_type='application/json',
                headers=headers or {}
            )
            
            channel.basic_publish(
                exchange=self.settings.rabbitmq.exchange,
                routing_key=routing_key,
                body=message_body,
                properties=properties
            )
            
            logger.info(f"Published raw message with routing key {routing_key}")
        except (AMQPConnectionError, AMQPChannelError) as e:
            logger.error(f"Failed to publish raw message: {e}")
            raise


class RabbitMQConsumer:
    """Base class for consuming messages from RabbitMQ"""
    
    def __init__(
        self,
        queue_name: str,
        routing_keys: List[str],
        connection: Optional[RabbitMQConnection] = None,
        callback: Optional[Callable] = None
    ):
        self.connection = connection or RabbitMQConnection()
        self.settings = get_settings()
        self.queue_name = f"{self.settings.rabbitmq.queue_prefix}.{queue_name}"
        self.routing_keys = routing_keys
        self.callback = callback
    
    def setup_queue(self):
        """Setup queue and bindings"""
        channel = self.connection.channel
        
        # Declare queue
        channel.queue_declare(
            queue=self.queue_name,
            durable=True
        )
        
        # Bind queue to exchange with routing keys
        for routing_key in self.routing_keys:
            channel.queue_bind(
                exchange=self.settings.rabbitmq.exchange,
                queue=self.queue_name,
                routing_key=routing_key
            )
        
        # Set QoS
        channel.basic_qos(prefetch_count=self.settings.rabbitmq.prefetch_count)
        
        logger.info(f"Queue {self.queue_name} setup complete with routing keys: {self.routing_keys}")
    
    def process_message(self, ch: BlockingChannel, method, properties, body: bytes):
        """
        Process incoming message
        
        Args:
            ch: Channel
            method: Delivery method
            properties: Message properties
            body: Message body
        """
        try:
            message_data = json.loads(body.decode('utf-8'))
            logger.info(f"Received message: {message_data.get('message_id', 'unknown')}")
            
            if self.callback:
                self.callback(message_data, properties, method)
            
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode message: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
    
    def start_consuming(self):
        """Start consuming messages"""
        self.setup_queue()
        channel = self.connection.channel
        
        channel.basic_consume(
            queue=self.queue_name,
            on_message_callback=self.process_message
        )
        
        logger.info(f"Started consuming from queue: {self.queue_name}")
        try:
            channel.start_consuming()
        except KeyboardInterrupt:
            logger.info("Stopping consumer...")
            channel.stop_consuming()
    
    def stop_consuming(self):
        """Stop consuming messages"""
        try:
            channel = self.connection.channel
            channel.stop_consuming()
            logger.info("Stopped consuming messages")
        except Exception as e:
            logger.error(f"Error stopping consumer: {e}")


def retry_on_connection_error(max_retries: int = 3):
    """Decorator to retry operations on connection errors"""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (AMQPConnectionError, AMQPChannelError) as e:
                    if attempt == max_retries - 1:
                        raise
                    logger.warning(f"Connection error (attempt {attempt + 1}/{max_retries}): {e}")
                    import time
                    time.sleep(2 ** attempt)  # Exponential backoff
            return None
        return wrapper
    return decorator

