from uuid import UUID
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from app.models import Payment
from shared.logging_config import get_logger

logger = get_logger(__name__, "order-service")


class PaymentRepository:
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_payment_by_idempotency_key(self, idempotency_key: str) -> Optional[Payment]:
        """Get payment by idempotency key to check for duplicate requests."""
        try:
            return (
                self.db.query(Payment)
                .filter(Payment.idempotency_key == idempotency_key)
                .first()
            )
        except SQLAlchemyError as e:
            logger.error(f"Error getting payment by idempotency key {idempotency_key}: {e}")
            raise
    
    def create_payment(
        self,
        order_id: UUID,
        idempotency_key: str,
        amount: float,
        payment_method: Optional[str] = None,
        transaction_id: Optional[str] = None,
        status: str = "pending"
    ) -> Payment:
        """Create a new payment record."""
        try:
            payment = Payment(
                order_id=order_id,
                idempotency_key=idempotency_key,
                amount=amount,
                payment_method=payment_method,
                transaction_id=transaction_id,
                status=status
            )
            self.db.add(payment)
            self.db.flush()
            return payment
        except IntegrityError as e:
            logger.error(f"Integrity error creating payment (duplicate idempotency key?): {e}")
            self.db.rollback()
            raise ValueError(f"Payment with idempotency key {idempotency_key} already exists")
        except SQLAlchemyError as e:
            logger.error(f"Error creating payment: {e}")
            self.db.rollback()
            raise
    
    def update_payment_status(
        self,
        payment_id: UUID,
        status: str,
        transaction_id: Optional[str] = None
    ) -> Optional[Payment]:
        """Update payment status."""
        try:
            payment = self.db.query(Payment).filter(Payment.id == payment_id).first()
            if not payment:
                return None
            
            payment.status = status
            if transaction_id:
                payment.transaction_id = transaction_id
            
            self.db.flush()
            return payment
        except SQLAlchemyError as e:
            logger.error(f"Error updating payment status for payment {payment_id}: {e}")
            self.db.rollback()
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

