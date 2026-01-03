from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict


class MessageType(str, Enum):
    ORDER_CREATED = "order.created"
    ORDER_UPDATED = "order.updated"
    ORDER_COMPLETED = "order.completed"
    ORDER_CANCELLED = "order.cancelled"
    ORDER_PAID = "order.paid"
    PRODUCT_CREATED = "product.created"
    PRODUCT_UPDATED = "product.updated"
    INVENTORY_UPDATED = "inventory.updated"
    INVENTORY_RESERVED = "inventory.reserved"
    INVENTORY_RELEASED = "inventory.released"
    INVENTORY_UNAVAILABLE = "inventory.unavailable"
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    NOTIFICATION_SENT = "notification.sent"


class BaseMessage(BaseModel):
    model_config = ConfigDict(use_enum_values=True)
    
    message_id: str = Field(..., description="Unique message identifier")
    message_type: MessageType = Field(..., description="Type of message")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Message timestamp")
    source_service: str = Field(..., description="Service that generated the message")
    correlation_id: Optional[str] = Field(None, description="Correlation ID for request tracing")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class OrderMessage(BaseMessage):
    order_id: str = Field(..., description="Order identifier")
    user_id: str = Field(..., description="User identifier")
    status: str = Field(..., description="Order status")
    total_amount: float = Field(..., description="Total order amount")
    items: List[Dict[str, Any]] = Field(default_factory=list, description="Order items")


class ProductMessage(BaseMessage):
    product_id: str = Field(..., description="Product identifier")
    name: str = Field(..., description="Product name")
    price: float = Field(..., description="Product price")
    stock: int = Field(..., description="Product stock quantity")
    category: Optional[str] = Field(None, description="Product category")


class InventoryMessage(BaseMessage):
    product_id: str = Field(..., description="Product identifier")
    sku: Optional[str] = Field(None, description="Product SKU")
    quantity_change: Optional[int] = Field(None, description="Quantity change (for inventory.updated)")
    quantity: Optional[int] = Field(None, description="Quantity (for reserved/released)")
    total_stock: int = Field(..., description="Total stock quantity")
    reserved_stock: int = Field(..., description="Reserved stock quantity")
    available_stock: int = Field(..., description="Available stock quantity")
    order_id: Optional[str] = Field(None, description="Order ID (for reserved/released events)")


class UserMessage(BaseMessage):
    user_id: str = Field(..., description="User identifier")
    email: str = Field(..., description="User email")
    username: Optional[str] = Field(None, description="Username")
    role: Optional[str] = Field(None, description="User role")


class NotificationMessage(BaseMessage):
    user_id: str = Field(..., description="Target user identifier")
    notification_type: str = Field(..., description="Type of notification")
    title: str = Field(..., description="Notification title")
    body: str = Field(..., description="Notification body")
    channel: str = Field(..., description="Notification channel (email, sms, push)")
    priority: str = Field(default="normal", description="Notification priority")


class HealthCheckResponse(BaseModel):
    service: str = Field(..., description="Service name")
    status: str = Field(..., description="Service status")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: Optional[str] = Field(None, description="Service version")
    dependencies: Dict[str, str] = Field(default_factory=dict, description="Dependency statuses")


class ErrorResponse(BaseModel):
    error: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Error code")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")

