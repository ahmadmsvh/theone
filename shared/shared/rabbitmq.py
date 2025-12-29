import json
import logging
import asyncio
from typing import Callable, Optional, Dict, Any, List
from functools import wraps

import aio_pika
from aio_pika import Message, DeliveryMode
from aio_pika.abc import AbstractChannel, AbstractConnection, AbstractExchange
from aio_pika.exceptions import AMQPConnectionError, AMQPChannelError

from .config import get_settings
from .models import BaseMessage

logger = logging.getLogger(__name__)


class RabbitMQConnection:
    
    def __init__(self, connection_url: Optional[str] = None):
        self.settings = get_settings()
        self.connection_url = connection_url or self.settings.rabbitmq.url
        self._connection: Optional[AbstractConnection] = None
        self._channel: Optional[AbstractChannel] = None
        self._exchange: Optional[AbstractExchange] = None
    
    async def connect(self):    
        if self._connection is None or self._connection.is_closed:
            try:
                self._connection = await aio_pika.connect_robust(self.connection_url)
                self._channel = await self._connection.channel()
                
                self._exchange = await self._channel.declare_exchange(
                    self.settings.rabbitmq.exchange,
                    aio_pika.ExchangeType.TOPIC,
                    durable=True
                )
                
                logger.info("RabbitMQ connection established successfully")
            except AMQPConnectionError as e:
                logger.error(f"Failed to connect to RabbitMQ: {e}")
                raise
        return self._connection
    
    async def get_channel(self) -> AbstractChannel: 
        if self._channel is None or self._channel.is_closed:
            await self.connect()
        return self._channel
    
    async def get_exchange(self) -> AbstractExchange:
        if self._exchange is None:
            await self.connect()
        return self._exchange
    
    async def close(self):
        try:
            if self._channel and not self._channel.is_closed:
                await self._channel.close()
            if self._connection and not self._connection.is_closed:
                await self._connection.close()
            logger.info("RabbitMQ connection closed")
        except Exception as e:
            logger.error(f"Error closing RabbitMQ connection: {e}")
    
    async def health_check(self) -> bool:
        try:
            if self._connection is None or self._connection.is_closed:
                await self.connect()
            return self._connection.is_closed == False
        except Exception as e:
            logger.error(f"RabbitMQ health check failed: {e}")
            return False


class RabbitMQPublisher:    
    
    def __init__(self, connection: Optional[RabbitMQConnection] = None):
        self.connection = connection or RabbitMQConnection()
        self.settings = get_settings()
    
    async def publish(self, message: BaseMessage, routing_key: Optional[str] = None):
        try:
            exchange = await self.connection.get_exchange()
            routing_key = routing_key or message.message_type.value
            
            message_body = message.model_dump_json()
            
            await exchange.publish(
                Message(
                    message_body.encode(),
                    delivery_mode=DeliveryMode.PERSISTENT,
                    content_type='application/json',
                    correlation_id=message.correlation_id,
                ),
                routing_key=routing_key,
            )
            
            logger.info(f"Published message {message.message_id} with routing key {routing_key}")
        except (AMQPConnectionError, AMQPChannelError) as e:
            logger.error(f"Failed to publish message: {e}")
            raise
    
    async def publish_raw(self, message_body: str, routing_key: str, headers: Optional[Dict[str, Any]] = None):
        try:
            exchange = await self.connection.get_exchange()
            
            await exchange.publish(
                Message(
                    message_body.encode(),
                    delivery_mode=DeliveryMode.PERSISTENT,
                    content_type='application/json',
                    headers=headers or {},
                ),
                routing_key=routing_key,
            )
            
            logger.info(f"Published raw message with routing key {routing_key}")
        except (AMQPConnectionError, AMQPChannelError) as e:
            logger.error(f"Failed to publish raw message: {e}")
            raise


class RabbitMQConsumer:
    
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
        self._queue: Optional[aio_pika.abc.AbstractQueue] = None
    
    async def setup_queue(self):
        channel = await self.connection.get_channel()
        exchange = await self.connection.get_exchange()
        
        self._queue = await channel.declare_queue(
            self.queue_name,
            durable=True
        )
        
        for routing_key in self.routing_keys:
            await self._queue.bind(exchange, routing_key=routing_key)
        
        await channel.set_qos(prefetch_count=self.settings.rabbitmq.prefetch_count)
        
        logger.info(f"Queue {self.queue_name} setup complete with routing keys: {self.routing_keys}")
    
    async def process_message(self, message: aio_pika.IncomingMessage):
        try:
            message_data = json.loads(message.body.decode('utf-8'))
            logger.info(f"Received message: {message_data.get('message_id', 'unknown')}")
            
            if self.callback:
                if asyncio.iscoroutinefunction(self.callback):
                    await self.callback(message_data, message.properties, message)
                else:
                    self.callback(message_data, message.properties, message)
            
            await message.ack()
            
        except json.JSONDecodeError as e:   
            logger.error(f"Failed to decode message: {e}")
            await message.nack(requeue=False)  
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            await message.nack(requeue=True)  
    
    async def start_consuming(self):
        if self._queue is None:
            await self.setup_queue()
        
        logger.info(f"Started consuming from queue: {self.queue_name}")
        await self._queue.consume(self.process_message, no_ack=False)
    
    async def stop_consuming(self):
        try:
            if self._queue:
                await self._queue.cancel()
            logger.info("Stopped consuming messages")
        except Exception as e:
            logger.error(f"Error stopping consumer: {e}")


def retry_on_connection_error(max_retries: int = 3):
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except (AMQPConnectionError, AMQPChannelError) as e:
                    if attempt == max_retries - 1:
                        raise
                    logger.warning(f"Connection error (attempt {attempt + 1}/{max_retries}): {e}")
                    await asyncio.sleep(2 ** attempt)  
            return None
        return wrapper
    return decorator
