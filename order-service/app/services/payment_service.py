from uuid import UUID
from typing import Optional, Dict, Any
from decimal import Decimal
import os

from shared.logging_config import get_logger

logger = get_logger(__name__, "order-service")


class PaymentService:
    """
    Payment service that supports both mock payment gateway (for portfolio)
    and Stripe test mode.
    """
    
    def __init__(self):
        self.use_stripe = os.getenv("USE_STRIPE", "false").lower() == "true"
        self.stripe_secret_key = os.getenv("STRIPE_SECRET_KEY")
        
        if self.use_stripe and not self.stripe_secret_key:
            logger.warning("USE_STRIPE is true but STRIPE_SECRET_KEY is not set. Falling back to mock payment.")
            self.use_stripe = False
    
    async def process_payment(
        self,
        order_id: UUID,
        amount: Decimal,
        payment_method: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Process payment for an order.
        
        Args:
            order_id: Order ID
            amount: Payment amount
            payment_method: Payment method (e.g., "card", "stripe")
            **kwargs: Additional payment parameters
            
        Returns:
            Dict with payment result including transaction_id and status
        """
        if self.use_stripe:
            return await self._process_stripe_payment(order_id, amount, payment_method, **kwargs)
        else:
            return await self._process_mock_payment(order_id, amount, payment_method, **kwargs)
    
    async def _process_mock_payment(
        self,
        order_id: UUID,
        amount: Decimal,
        payment_method: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Mock payment gateway for portfolio/demo purposes.
        Always succeeds for demo purposes.
        """
        logger.info(f"Processing mock payment for order {order_id}, amount: {amount}")
        
        # Simulate payment processing delay
        import asyncio
        await asyncio.sleep(0.1)
        
        # Generate a mock transaction ID
        transaction_id = f"mock_txn_{order_id}_{int(asyncio.get_event_loop().time() * 1000)}"
        
        logger.info(f"Mock payment successful for order {order_id}, transaction_id: {transaction_id}")
        
        return {
            "transaction_id": transaction_id,
            "status": "succeeded",
            "payment_method": payment_method or "mock",
            "amount": float(amount),
            "gateway": "mock"
        }
    
    async def _process_stripe_payment(
        self,
        order_id: UUID,
        amount: Decimal,
        payment_method: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Process payment using Stripe test mode.
        """
        try:
            import stripe
            
            stripe.api_key = self.stripe_secret_key
            
            # Convert amount to cents for Stripe
            amount_cents = int(float(amount) * 100)
            
            # Create payment intent
            payment_intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency="usd",
                metadata={
                    "order_id": str(order_id),
                    "payment_method": payment_method or "card"
                }
            )
            
            # For test mode, we'll simulate confirmation
            # In production, you'd handle webhooks for actual payment confirmation
            if payment_intent.status == "succeeded":
                transaction_id = payment_intent.id
                status = "succeeded"
            else:
                # Confirm the payment intent for test mode
                payment_intent = stripe.PaymentIntent.confirm(payment_intent.id)
                transaction_id = payment_intent.id
                status = payment_intent.status
            
            logger.info(f"Stripe payment processed for order {order_id}, transaction_id: {transaction_id}")
            
            return {
                "transaction_id": transaction_id,
                "status": status,
                "payment_method": payment_method or "card",
                "amount": float(amount),
                "gateway": "stripe"
            }
            
        except ImportError:
            logger.error("Stripe library not installed. Install with: pip install stripe")
            raise ValueError("Stripe payment processing is not available")
        except Exception as e:
            logger.error(f"Stripe payment processing failed for order {order_id}: {e}")
            raise ValueError(f"Payment processing failed: {str(e)}")
    
    async def refund_payment(
        self,
        transaction_id: str,
        amount: Optional[Decimal] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Refund a payment.
        
        Args:
            transaction_id: Original transaction ID to refund
            amount: Refund amount (partial refund if provided, full refund if None)
            **kwargs: Additional refund parameters
            
        Returns:
            Dict with refund result including refund_id and status
        """
        if self.use_stripe:
            return await self._refund_stripe_payment(transaction_id, amount, **kwargs)
        else:
            return await self._refund_mock_payment(transaction_id, amount, **kwargs)
    
    async def _refund_mock_payment(
        self,
        transaction_id: str,
        amount: Optional[Decimal] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Mock refund for portfolio/demo purposes.
        Always succeeds for demo purposes.
        """
        logger.info(f"Processing mock refund for transaction {transaction_id}, amount: {amount}")
        
        # Simulate refund processing delay
        import asyncio
        await asyncio.sleep(0.1)
        
        # Generate a mock refund ID
        refund_id = f"mock_refund_{transaction_id}_{int(asyncio.get_event_loop().time() * 1000)}"
        
        logger.info(f"Mock refund successful for transaction {transaction_id}, refund_id: {refund_id}")
        
        return {
            "refund_id": refund_id,
            "transaction_id": transaction_id,
            "status": "succeeded",
            "amount": float(amount) if amount else None,
            "gateway": "mock"
        }
    
    async def _refund_stripe_payment(
        self,
        transaction_id: str,
        amount: Optional[Decimal] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Refund payment using Stripe.
        """
        try:
            import stripe
            
            stripe.api_key = self.stripe_secret_key
            
            # Convert amount to cents for Stripe if provided
            amount_cents = int(float(amount) * 100) if amount else None
            
            # Create refund
            refund_params = {"payment_intent": transaction_id}
            if amount_cents:
                refund_params["amount"] = amount_cents
            
            refund = stripe.Refund.create(**refund_params)
            
            logger.info(f"Stripe refund processed for transaction {transaction_id}, refund_id: {refund.id}")
            
            return {
                "refund_id": refund.id,
                "transaction_id": transaction_id,
                "status": refund.status,
                "amount": float(amount) if amount else None,
                "gateway": "stripe"
            }
            
        except ImportError:
            logger.error("Stripe library not installed. Install with: pip install stripe")
            raise ValueError("Stripe payment processing is not available")
        except Exception as e:
            logger.error(f"Stripe refund processing failed for transaction {transaction_id}: {e}")
            raise ValueError(f"Refund processing failed: {str(e)}")

