from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field
from datetime import datetime
from app.models import OrderStatus


class CartItem(BaseModel):
    product_id: str = Field(..., description="Product ID")
    quantity: int = Field(..., gt=0, description="Quantity")


class OrderCreateRequest(BaseModel):
    items: List[CartItem] = Field(..., min_items=1, description="Cart items")


class OrderItemResponse(BaseModel):
    id: UUID
    product_id: str
    sku: str
    quantity: int
    price: float
    
    class Config:
        from_attributes = True


class OrderStatusHistoryResponse(BaseModel):
    status: OrderStatus
    timestamp: datetime
    
    class Config:
        from_attributes = True


class OrderResponse(BaseModel):
    id: UUID
    user_id: UUID
    status: OrderStatus
    total: float
    created_at: datetime
    updated_at: datetime
    items: List[OrderItemResponse]
    
    class Config:
        from_attributes = True


class OrderDetailResponse(BaseModel):
    id: UUID
    user_id: UUID
    status: OrderStatus
    total: float
    created_at: datetime
    updated_at: datetime
    items: List[OrderItemResponse]
    status_history: List[OrderStatusHistoryResponse]
    
    class Config:
        from_attributes = True


class OrderStatusUpdateRequest(BaseModel):
    status: OrderStatus = Field(..., description="New order status")


class OrderListResponse(BaseModel):
    orders: List[OrderResponse]
    total: int
    page: int
    limit: int
    pages: int


class PaymentRequest(BaseModel):
    idempotency_key: str = Field(..., description="Idempotency key to prevent duplicate payments")
    payment_method: Optional[str] = Field(None, description="Payment method (e.g., 'card', 'stripe')")
    amount: Optional[float] = Field(None, description="Payment amount (optional, defaults to order total)")


class PaymentResponse(BaseModel):
    payment_id: UUID
    order_id: UUID
    transaction_id: str
    amount: float
    status: str
    payment_method: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True

