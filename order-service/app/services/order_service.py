from uuid import UUID
from typing import List, Dict, Any, Optional, Tuple
from decimal import Decimal

from app.repositories.order_repository import OrderRepository
from app.repositories.payment_repository import PaymentRepository
from app.models import Order, OrderStatus
from app.core.product_client import ProductServiceClient
from app.services.payment_service import PaymentService
from shared.logging_config import get_logger

logger = get_logger(__name__, "order-service")

# Valid status transitions
STATUS_TRANSITIONS = {
    OrderStatus.PENDING: [OrderStatus.CONFIRMED, OrderStatus.PAID, OrderStatus.CANCELLED],
    OrderStatus.CONFIRMED: [OrderStatus.PAID, OrderStatus.SHIPPED, OrderStatus.CANCELLED],
    OrderStatus.PAID: [OrderStatus.PROCESSING, OrderStatus.SHIPPED],
    OrderStatus.PROCESSING: [OrderStatus.SHIPPED],
    OrderStatus.SHIPPED: [OrderStatus.DELIVERED],
    OrderStatus.DELIVERED: [],
    OrderStatus.CANCELLED: [],
}


class OrderService:
    
    def __init__(
        self,
        repository: OrderRepository,
        product_client: ProductServiceClient,
        payment_repository: Optional[PaymentRepository] = None,
        payment_service: Optional[PaymentService] = None
    ):
        self.repository = repository
        self.product_client = product_client
        self.payment_repository = payment_repository
        self.payment_service = payment_service or PaymentService()
    
    async def create_order(
        self,
        user_id: UUID,
        cart_items: List[Dict[str, Any]],
        token: str
    ) -> Order:

        try:
            validated_items = await self.product_client.validate_cart_items(
                cart_items=[{"product_id": item["product_id"], "quantity": item["quantity"]} for item in cart_items],
                token=token
            )
            
            total = Decimal("0.00")
            for item in validated_items:
                item_total = Decimal(str(item["price"])) * Decimal(str(item["quantity"]))
                total += item_total
            
            order = self.repository.create_order(
                user_id=user_id,
                total=float(total),
                status=OrderStatus.PENDING
            )
            
            reserved_products = []
            try:
                for item in validated_items:
                    product_id = item["product_id"]
                    quantity = item["quantity"]
                    
                    await self.product_client.reserve_inventory(
                        product_id=product_id,
                        quantity=quantity,
                        order_id=str(order.id),
                        token=token
                    )
                    reserved_products.append(product_id)
                    
                    self.repository.create_order_item(
                        order_id=order.id,
                        product_id=product_id,
                        sku=item.get("sku", ""),
                        quantity=quantity,
                        price=float(item["price"])
                    )
                
                self.repository.commit()
                logger.info(f"Order {order.id} created successfully for user {user_id}")
                return order
                
            except Exception as e:
                logger.error(f"Error reserving inventory for order {order.id}: {e}")
                self.repository.rollback()
                raise
            
        except Exception as e:
            logger.error(f"Error creating order for user {user_id}: {e}")
            self.repository.rollback()
            raise
    
    def get_order_by_id(self, order_id: UUID) -> Order:
        order = self.repository.get_order_by_id(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")
        return order
    
    def get_orders_by_user_id(self, user_id: UUID) -> List[Order]:
        return self.repository.get_orders_by_user_id(user_id)
    
    def list_orders(
        self,
        user_id: Optional[UUID] = None,
        page: int = 1,
        limit: int = 10
    ) -> Dict[str, Any]:
        if page < 1:
            page = 1
        if limit < 1 or limit > 100:
            limit = 10
        
        skip = (page - 1) * limit
        orders, total = self.repository.list_orders(user_id=user_id, skip=skip, limit=limit)
        
        return {
            "orders": orders,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit if total > 0 else 0
        }
    
    def validate_status_transition(self, current_status: OrderStatus, new_status: OrderStatus) -> bool:
        """Validate if status transition is allowed"""
        allowed_transitions = STATUS_TRANSITIONS.get(current_status, [])
        return new_status in allowed_transitions
    
    def update_order_status(
        self,
        order_id: UUID,
        new_status: OrderStatus
    ) -> Order:
        order = self.get_order_by_id(order_id)
        
        # Don't validate transition if status hasn't changed
        if order.status == new_status:
            return order
        
        # Validate status transition
        if not self.validate_status_transition(order.status, new_status):
            raise ValueError(
                f"Invalid status transition from {order.status.value} to {new_status.value}. "
                f"Allowed transitions: {[s.value for s in STATUS_TRANSITIONS.get(order.status, [])]}"
            )
        
        updated_order = self.repository.update_order_status(order_id, new_status)
        if not updated_order:
            raise ValueError(f"Failed to update order {order_id}")
        
        self.repository.commit()
        logger.info(f"Order {order_id} status updated from {order.status.value} to {new_status.value}")
        return updated_order
    
    def cancel_order(self, order_id: UUID) -> Order:
        order = self.get_order_by_id(order_id)
        
        if order.status == OrderStatus.CANCELLED:
            return order
        
        cancelled_order = self.repository.cancel_order(order_id)
        if not cancelled_order:
            raise ValueError(f"Failed to cancel order {order_id}")
        
        self.repository.commit()
        logger.info(f"Order {order_id} cancelled")
        return cancelled_order
    
    async def process_payment(
        self,
        order_id: UUID,
        idempotency_key: str,
        payment_amount: Optional[float] = None,
        payment_method: Optional[str] = None,
        token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process payment for an order with idempotency support.
        
        Args:
            order_id: Order ID
            idempotency_key: Unique key to prevent duplicate payments
            payment_amount: Payment amount (defaults to order total)
            payment_method: Payment method (e.g., 'card', 'stripe')
            
        Returns:
            Dict with payment information including payment_id and transaction_id
        """
        if not self.payment_repository:
            raise ValueError("Payment repository is required for payment processing")
        
        # Check for existing payment with same idempotency key (idempotency check)
        existing_payment = self.payment_repository.get_payment_by_idempotency_key(idempotency_key)
        if existing_payment:
            logger.info(f"Payment with idempotency key {idempotency_key} already exists. Returning existing payment.")
            order = self.repository.get_order_by_id(existing_payment.order_id)
            return {
                "payment_id": existing_payment.id,
                "order_id": existing_payment.order_id,
                "transaction_id": existing_payment.transaction_id or "pending",
                "status": existing_payment.status,
                "amount": float(existing_payment.amount),
                "payment_method": existing_payment.payment_method,
                "order_status": order.status.value
            }
        
        # Get order
        order = self.get_order_by_id(order_id)
        
        # Validate order can be paid
        if order.status == OrderStatus.PAID:
            raise ValueError(f"Order {order_id} is already paid")
        
        if order.status == OrderStatus.CANCELLED:
            raise ValueError(f"Cannot pay for cancelled order {order_id}")
        
        # Use provided amount or order total
        amount = Decimal(str(payment_amount)) if payment_amount else Decimal(str(order.total))
        
        # Validate amount matches order total (allow small tolerance for rounding)
        if abs(float(amount) - float(order.total)) > 0.01:
            raise ValueError(
                f"Payment amount {float(amount)} does not match order total {float(order.total)}"
            )
        
        # Create payment record with pending status
        payment = self.payment_repository.create_payment(
            order_id=order_id,
            idempotency_key=idempotency_key,
            amount=float(amount),
            payment_method=payment_method,
            status="pending"
        )
        
        try:
            # Process payment through payment service
            payment_result = await self.payment_service.process_payment(
                order_id=order_id,
                amount=amount,
                payment_method=payment_method
            )
            
            # Update payment record with transaction details
            payment = self.payment_repository.update_payment_status(
                payment_id=payment.id,
                status=payment_result["status"],
                transaction_id=payment_result["transaction_id"]
            )
            
            # Update order status to PAID if payment succeeded
            if payment_result["status"] == "succeeded":
                updated_order = self.repository.update_order_status(order_id, OrderStatus.PAID)
                self.repository.commit()
                self.payment_repository.commit()
                logger.info(f"Payment successful for order {order_id}, transaction_id: {payment_result['transaction_id']}")
                
                return {
                    "payment_id": payment.id,
                    "order_id": order_id,
                    "transaction_id": payment_result["transaction_id"],
                    "status": "succeeded",
                    "amount": float(amount),
                    "payment_method": payment_result.get("payment_method"),
                    "order_status": updated_order.status.value
                }
            else:
                # Payment failed - implement saga pattern: release inventory
                self.payment_repository.commit()
                payment_error = ValueError(f"Payment processing failed with status: {payment_result['status']}")
                
                # Saga rollback: release inventory
                await self._rollback_order_inventory(order_id, token, payment_error)
                raise payment_error
                
        except Exception as e:
            # Rollback on error - implement saga pattern: release inventory
            self.payment_repository.rollback()
            self.repository.rollback()
            logger.error(f"Error processing payment for order {order_id}: {e}")
            
            # Saga rollback: release inventory if payment failed after inventory was reserved
            await self._rollback_order_inventory(order_id, token, e)
            raise
    
    async def _rollback_order_inventory(
        self,
        order_id: UUID,
        token: Optional[str],
        original_error: Exception
    ):
        """
        Saga pattern rollback: Release inventory when payment fails.
        If inventory release fails, log for manual review.
        """
        try:
            # Get order to find items
            order = self.repository.get_order_by_id(order_id)
            if not order:
                logger.warning(f"Order {order_id} not found for inventory rollback")
                return
            
            # Only release if order has items and is not already cancelled/delivered
            if not order.items or order.status in [OrderStatus.CANCELLED, OrderStatus.DELIVERED]:
                logger.info(f"Order {order_id} has no items or is already {order.status.value}, skipping inventory release")
                return
            
            if not token:
                logger.warning(
                    f"Payment failed for order {order_id}, but no token available for inventory release. "
                    f"Manual review required. Original error: {original_error}"
                )
                return
            
            # Release inventory for each item
            release_errors = []
            for item in order.items:
                try:
                    await self.product_client.release_inventory(
                        product_id=item.product_id,
                        quantity=item.quantity,
                        order_id=str(order_id),
                        token=token
                    )
                    logger.info(
                        f"Released inventory for order {order_id}, "
                        f"product {item.product_id}, quantity {item.quantity}"
                    )
                except Exception as release_error:
                    release_errors.append({
                        "product_id": item.product_id,
                        "quantity": item.quantity,
                        "error": str(release_error)
                    })
                    logger.error(
                        f"Failed to release inventory for order {order_id}, "
                        f"product {item.product_id}: {release_error}",
                        exc_info=True
                    )
            
            if release_errors:
                # Log for manual review
                logger.error(
                    f"PAYMENT FAILURE - INVENTORY RELEASE FAILED - Manual review required. "
                    f"Order ID: {order_id}, Payment error: {original_error}, "
                    f"Inventory release errors: {release_errors}"
                )
            
        except Exception as rollback_error:
            # Log for manual review if rollback itself fails
            logger.error(
                f"PAYMENT FAILURE - INVENTORY ROLLBACK FAILED - Manual review required. "
                f"Order ID: {order_id}, Payment error: {original_error}, "
                f"Rollback error: {rollback_error}",
                exc_info=True
            )

