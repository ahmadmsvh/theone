from uuid import UUID
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import desc

from app.models import Order, OrderItem, OrderStatus, OrderStatusHistory
from shared.logging_config import get_logger

logger = get_logger(__name__, "order-service")


class OrderRepository:
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_order(
        self,
        user_id: UUID,
        total: float,
        status: OrderStatus = OrderStatus.PENDING
    ) -> Order:
        try:
            order = Order(
                user_id=user_id,
                total=total,
                status=status
            )
            self.db.add(order)
            self.db.flush()
            
            # Create initial status history entry
            status_history = OrderStatusHistory(
                order_id=order.id,
                status=status
            )
            self.db.add(status_history)
            self.db.flush()
            
            return order
        except SQLAlchemyError as e:
            logger.error(f"Error creating order: {e}")
            self.db.rollback()
            raise
    
    def create_order_item(
        self,
        order_id: UUID,
        product_id: str,
        sku: str,
        quantity: int,
        price: float
    ) -> OrderItem:
        try:
            order_item = OrderItem(
                order_id=order_id,
                product_id=product_id,
                sku=sku,
                quantity=quantity,
                price=price
            )
            self.db.add(order_item)
            return order_item
        except SQLAlchemyError as e:
            logger.error(f"Error creating order item: {e}")
            self.db.rollback()
            raise
    
    def get_order_by_id(self, order_id: UUID) -> Optional[Order]:
        try:
            return (
                self.db.query(Order)
                .options(
                    joinedload(Order.items),
                    joinedload(Order.status_history)
                )
                .filter(Order.id == order_id)
                .first()
            )
        except SQLAlchemyError as e:
            logger.error(f"Error getting order {order_id}: {e}")
            raise
    
    def get_orders_by_user_id(self, user_id: UUID) -> List[Order]:
        try:
            return self.db.query(Order).filter(Order.user_id == user_id).all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting orders for user {user_id}: {e}")
            raise
    
    def list_orders(
        self,
        user_id: Optional[UUID] = None,
        skip: int = 0,
        limit: int = 10
    ) -> Tuple[List[Order], int]:
        try:
            query = self.db.query(Order).options(joinedload(Order.items))
            
            if user_id:
                query = query.filter(Order.user_id == user_id)
            
            total = query.count()
            
            orders = query.order_by(desc(Order.created_at)).offset(skip).limit(limit).all()
            
            return orders, total
        except SQLAlchemyError as e:
            logger.error(f"Error listing orders: {e}")
            raise
    
    def update_order_status(
        self,
        order_id: UUID,
        new_status: OrderStatus
    ) -> Optional[Order]:
        try:
            order = self.get_order_by_id(order_id)
            if not order:
                return None
            
            old_status = order.status
            order.status = new_status
            
            # Create status history entry
            status_history = OrderStatusHistory(
                order_id=order_id,
                status=new_status
            )
            self.db.add(status_history)
            
            self.db.flush()
            return order
        except SQLAlchemyError as e:
            logger.error(f"Error updating order status for order {order_id}: {e}")
            self.db.rollback()
            raise
    
    def cancel_order(self, order_id: UUID) -> Optional[Order]:
        try:
            order = self.get_order_by_id(order_id)
            if not order:
                return None
            
            if order.status not in [OrderStatus.PENDING, OrderStatus.CONFIRMED]:
                raise ValueError(f"Cannot cancel order with status {order.status.value}")
            
            order.status = OrderStatus.CANCELLED
            
            # Create status history entry
            status_history = OrderStatusHistory(
                order_id=order_id,
                status=OrderStatus.CANCELLED
            )
            self.db.add(status_history)
            
            self.db.flush()
            return order
        except SQLAlchemyError as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            self.db.rollback()
            raise
        except ValueError:
            raise
    
    def commit(self):
        try:
            self.db.commit()
        except SQLAlchemyError as e:
            logger.error(f"Error committing transaction: {e}")
            self.db.rollback()
            raise
    
    def rollback(self):
        self.db.rollback()

