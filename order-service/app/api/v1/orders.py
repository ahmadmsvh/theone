from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from uuid import UUID
import os
from app.core.database import get_db
from app.core.dependencies import require_auth, require_role, require_any_role
from app.core.product_client import get_product_client, ProductServiceClient
from app.repositories.order_repository import OrderRepository
from app.repositories.payment_repository import PaymentRepository
from app.services.order_service import OrderService
from app.schemas import (
    OrderCreateRequest, 
    OrderResponse, 
    OrderItemResponse,
    OrderDetailResponse,
    OrderListResponse,
    OrderStatusUpdateRequest,
    OrderStatusHistoryResponse,
    PaymentRequest,
    PaymentResponse
)
from app.models import OrderStatus
from shared.logging_config import get_logger

logger = get_logger(__name__, os.getenv("SERVICE_NAME"))

router = APIRouter(prefix="/api/v1/orders", tags=["orders"])


def get_order_repository(db: Session = Depends(get_db)) -> OrderRepository:
    return OrderRepository(db)


def get_payment_repository(db: Session = Depends(get_db)) -> PaymentRepository:
    return PaymentRepository(db)


def get_order_service(
    repository: OrderRepository = Depends(get_order_repository),
    product_client: ProductServiceClient = Depends(get_product_client),
    payment_repository: PaymentRepository = Depends(get_payment_repository)
) -> OrderService: 
    return OrderService(repository, product_client, payment_repository)


@router.post(
    "",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new order",
    description="Create a new order for the authenticated customer. Validates cart items, checks inventory, reserves inventory, and creates the order."
)
async def create_order(
    order_data: OrderCreateRequest,
    request: Request,
    current_user: Dict[str, Any] = Depends(require_auth),
    _: None = Depends(require_role("Customer")),
    order_service: OrderService = Depends(get_order_service),
    db: Session = Depends(get_db)
):

    try:
        user_id = current_user["user_id"]
        # Extract token from Authorization header for service-to-service calls
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
        
        cart_items = [
            {"product_id": item.product_id, "quantity": item.quantity} for item in order_data.items if item.product_id and item.quantity
        ]
        
        order = await order_service.create_order(
            user_id=user_id,
            cart_items=cart_items,
            token=token
        )
        
        db.refresh(order)
        
        from app.core.events import publish_order_created_event
        await publish_order_created_event(order)
        
        return OrderResponse(
            id=order.id,
            user_id=order.user_id,
            status=order.status,
            total=float(order.total),
            created_at=order.created_at,
            updated_at=order.updated_at,
            items=[
                OrderItemResponse(
                    id=item.id,
                    product_id=item.product_id,
                    sku=item.sku,
                    quantity=item.quantity,
                    price=float(item.price)
                )
                for item in order.items
            ]
        )
        
    except ValueError as e:
        logger.warning(f"Validation error creating order: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating order: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating the order"
        )


@router.get(
    "",
    response_model=OrderListResponse,
    status_code=status.HTTP_200_OK,
    summary="List orders",
    description="List orders with pagination. Customers see only their own orders. Admins see all orders."
)
async def list_orders(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    current_user: Dict[str, Any] = Depends(require_auth),
    order_service: OrderService = Depends(get_order_service)
):
    try:
        user_roles = current_user.get("roles", [])
        user_id = current_user["user_id"]
        
        filter_user_id = None if "Admin" in user_roles else user_id
        
        result = order_service.list_orders(
            user_id=filter_user_id,
            page=page,
            limit=limit
        )
        
        orders_response = [
            OrderResponse(
                id=order.id,
                user_id=order.user_id,
                status=order.status,
                total=float(order.total),
                created_at=order.created_at,
                updated_at=order.updated_at,
                items=[
                    OrderItemResponse(
                        id=item.id,
                        product_id=item.product_id,
                        sku=item.sku,
                        quantity=item.quantity,
                        price=float(item.price)
                    )
                    for item in order.items
                ]
            )
            for order in result["orders"]
        ]
        
        return OrderListResponse(
            orders=orders_response,
            total=result["total"],
            page=result["page"],
            limit=result["limit"],
            pages=result["pages"]
        )
        
    except Exception as e:
        logger.error(f"Error listing orders: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while listing orders"
        )


@router.get(
    "/{order_id}",
    response_model=OrderDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get order details",
    description="Get detailed information about a specific order, including items and status history."
)
async def get_order(
    order_id: UUID,
    current_user: Dict[str, Any] = Depends(require_auth),
    order_service: OrderService = Depends(get_order_service),
    db: Session = Depends(get_db)
):
    try:
        order = order_service.get_order_by_id(order_id)
        
        # Check if user has access to this order
        user_roles = current_user.get("roles", [])
        user_id = current_user["user_id"]
        
        if "Admin" not in user_roles and order.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You can only view your own orders."
            )
        
        # Refresh to load relationships
        db.refresh(order)
        
        # Sort status history by timestamp
        status_history = sorted(order.status_history, key=lambda x: x.timestamp)
        
        return OrderDetailResponse(
            id=order.id,
            user_id=order.user_id,
            status=order.status,
            total=float(order.total),
            created_at=order.created_at,
            updated_at=order.updated_at,
            items=[
                OrderItemResponse(
                    id=item.id,
                    product_id=item.product_id,
                    sku=item.sku,
                    quantity=item.quantity,
                    price=float(item.price)
                )
                for item in order.items
            ],
            status_history=[
                OrderStatusHistoryResponse(
                    status=hist.status,
                    timestamp=hist.timestamp
                )
                for hist in status_history
            ]
        )
        
    except ValueError as e:
        logger.warning(f"Order not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting order {order_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while getting the order"
        )


@router.put(
    "/{order_id}/status",
    response_model=OrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Update order status",
    description="Update the status of an order. Only Admin and Vendor roles can update order status."
)
async def update_order_status(
    order_id: UUID,
    status_data: OrderStatusUpdateRequest,
    current_user: Dict[str, Any] = Depends(require_auth),
    _: None = Depends(require_any_role("Admin", "Vendor")),
    order_service: OrderService = Depends(get_order_service),
    db: Session = Depends(get_db)
):
    try:
        # Get the order to capture old status
        order = order_service.get_order_by_id(order_id)
        old_status = order.status
        
        # Update the status
        updated_order = order_service.update_order_status(
            order_id=order_id,
            new_status=status_data.status
        )
        
        db.refresh(updated_order)
        
        # Publish status change event
        from app.core.events import publish_order_status_updated_event
        await publish_order_status_updated_event(updated_order, old_status)
        
        return OrderResponse(
            id=updated_order.id,
            user_id=updated_order.user_id,
            status=updated_order.status,
            total=float(updated_order.total),
            created_at=updated_order.created_at,
            updated_at=updated_order.updated_at,
            items=[
                OrderItemResponse(
                    id=item.id,
                    product_id=item.product_id,
                    sku=item.sku,
                    quantity=item.quantity,
                    price=float(item.price)
                )
                for item in updated_order.items
            ]
        )
        
    except ValueError as e:
        logger.warning(f"Validation error updating order status: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating order status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating the order status"
        )


@router.post(
    "/{order_id}/cancel",
    response_model=OrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel order",
    description="Cancel an order. Only orders with 'pending' or 'confirmed' status can be cancelled."
)
async def cancel_order(
    order_id: UUID,
    current_user: Dict[str, Any] = Depends(require_auth),
    order_service: OrderService = Depends(get_order_service),
    db: Session = Depends(get_db)
):
    try:
        # Check if user has access to this order
        order = order_service.get_order_by_id(order_id)
        user_roles = current_user.get("roles", [])
        user_id = current_user["user_id"]
        
        if "Admin" not in user_roles and order.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You can only cancel your own orders."
            )
        
        # Cancel the order
        cancelled_order = order_service.cancel_order(order_id)
        
        db.refresh(cancelled_order)
        
        # Publish cancellation event
        from app.core.events import publish_order_cancelled_event
        await publish_order_cancelled_event(cancelled_order)
        
        return OrderResponse(
            id=cancelled_order.id,
            user_id=cancelled_order.user_id,
            status=cancelled_order.status,
            total=float(cancelled_order.total),
            created_at=cancelled_order.created_at,
            updated_at=cancelled_order.updated_at,
            items=[
                OrderItemResponse(
                    id=item.id,
                    product_id=item.product_id,
                    sku=item.sku,
                    quantity=item.quantity,
                    price=float(item.price)
                )
                for item in cancelled_order.items
            ]
        )
        
    except ValueError as e:
        logger.warning(f"Validation error cancelling order: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling order: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while cancelling the order"
        )


@router.post(
    "/{order_id}/payment",
    response_model=PaymentResponse,
    status_code=status.HTTP_200_OK,
    summary="Process payment for an order",
    description="Process payment for an order. Supports idempotency keys to prevent duplicate charges. Uses mock payment gateway by default, or Stripe test mode if configured."
)
async def process_payment(
    order_id: UUID,
    payment_data: PaymentRequest,
    request: Request,
    current_user: Dict[str, Any] = Depends(require_auth),
    _: None = Depends(require_role("Customer")),
    order_service: OrderService = Depends(get_order_service),
    payment_repository: PaymentRepository = Depends(get_payment_repository),
    db: Session = Depends(get_db)
):
    try:
        # Check if user has access to this order
        order = order_service.get_order_by_id(order_id)
        user_roles = current_user.get("roles", [])
        user_id = current_user["user_id"]
        
        if "Admin" not in user_roles and order.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You can only pay for your own orders."
            )
        
        # Extract token from Authorization header for service-to-service calls
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
        
        # Process payment
        payment_result = await order_service.process_payment(
            order_id=order_id,
            idempotency_key=payment_data.idempotency_key,
            payment_amount=payment_data.amount,
            payment_method=payment_data.payment_method,
            token=token
        )
        
        # Refresh order to get updated status
        db.refresh(order)
        order = order_service.get_order_by_id(order_id)
        
        # Publish order.paid event if payment succeeded
        if payment_result["status"] == "succeeded":
            from app.core.events import publish_order_paid_event
            await publish_order_paid_event(
                order=order,
                transaction_id=payment_result["transaction_id"],
                payment_method=payment_result.get("payment_method")
            )
        
        # Get payment record for response
        payment = payment_repository.get_payment_by_idempotency_key(payment_data.idempotency_key)
        
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Payment record not found after processing"
            )
        
        return PaymentResponse(
            payment_id=payment.id,
            order_id=payment.order_id,
            transaction_id=payment.transaction_id or "pending",
            amount=float(payment.amount),
            status=payment.status,
            payment_method=payment.payment_method,
            created_at=payment.created_at
        )
        
    except ValueError as e:
        logger.warning(f"Validation error processing payment for order {order_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing payment for order {order_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing the payment"
        )

