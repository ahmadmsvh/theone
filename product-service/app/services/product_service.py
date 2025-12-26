import uuid
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
import os
from shared.logging_config import get_logger
from app.models import Product, ProductStatus
from app.schemas import ProductCreateRequest, ProductUpdateRequest
from app.repositories.product_repository import ProductRepository

logger = get_logger(__name__, os.getenv("SERVICE_NAME"))


class ProductService:
    """Service for product business logic"""
    
    def __init__(self, database: AsyncIOMotorDatabase):
        self.repository = ProductRepository(database)
    
    def generate_sku(self) -> str:
        """Generate a unique SKU"""
        # Generate a unique SKU using UUID (first 8 characters)
        return f"PRD-{uuid.uuid4().hex[:8].upper()}"
    
    async def create_product(
        self,
        product_data: ProductCreateRequest,
        user_id: str,
        vendor_id: Optional[str] = None
    ) -> Product:
        """Create a new product with business logic"""
        # Generate SKU if not provided
        if not product_data.sku:
            sku = self.generate_sku()
            # Ensure SKU is unique
            while await self.repository.sku_exists(sku):
                sku = self.generate_sku()
            product_data.sku = sku
        else:
            # Check if SKU already exists
            if await self.repository.sku_exists(product_data.sku):
                raise ValueError(f"Product with SKU '{product_data.sku}' already exists")
        
        # Set vendor_id if provided
        if vendor_id:
            product_data.vendor_id = vendor_id
        
        # Create product
        product = await self.repository.create(product_data, user_id)
        logger.info(f"Product created: {product.id} (SKU: {product.sku})")
        return product
    
    async def get_product(self, product_id: str) -> Optional[Product]:
        """Get a product by ID"""
        return await self.repository.get_by_id(product_id)
    
    async def list_products(
        self,
        page: int = 1,
        limit: int = 10,
        category: Optional[str] = None,
        search: Optional[str] = None,
        status: Optional[str] = None
    ) -> dict:
        """List products with pagination"""
        skip = (page - 1) * limit
        
        products, total = await self.repository.list(
            skip=skip,
            limit=limit,
            category=category,
            search=search,
            status=status
        )
        
        return {
            "products": products,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit if total > 0 else 0
        }
    
    async def update_product(
        self,
        product_id: str,
        product_data: ProductUpdateRequest,
        user_id: str,
        user_roles: list[str]
    ) -> Optional[Product]:
        """Update a product with authorization checks"""
        # Check if product exists
        product = await self.repository.get_by_id(product_id)
        if not product:
            return None
        
        # If user is vendor, ensure they own the product
        if "Vendor" in user_roles and "Admin" not in user_roles:
            if product.vendor_id and product.vendor_id != user_id:
                raise PermissionError("You can only update your own products")
        
        # If SKU is being updated, check uniqueness
        if product_data.sku and product_data.sku != product.sku:
            if await self.repository.sku_exists(product_data.sku, exclude_id=product_id):
                raise ValueError(f"Product with SKU '{product_data.sku}' already exists")
        
        return await self.repository.update(product_id, product_data, user_id)
    
    async def delete_product(self, product_id: str) -> bool:
        """Delete a product"""
        return await self.repository.delete(product_id)
    
    async def adjust_inventory(
        self,
        product_id: str,
        quantity: int,
        user_id: str,
        user_roles: list[str]
    ) -> Optional[Product]:
        """Adjust product inventory (increase or decrease)"""
        # Check if product exists
        product = await self.repository.get_by_id(product_id)
        if not product:
            return None
        
        # Authorization: Vendor can only modify their own products, Admin can modify any
        if "Vendor" in user_roles and "Admin" not in user_roles:
            if product.vendor_id and product.vendor_id != user_id:
                raise PermissionError("You can only adjust inventory for your own products")
        
        # Adjust stock
        return await self.repository.adjust_stock(product_id, quantity)
    
    async def get_inventory(self, product_id: str) -> Optional[dict]:
        """Get inventory information for a product"""
        product = await self.repository.get_by_id(product_id)
        if not product:
            return None
        
        available_stock = product.stock - product.reserved_stock
        
        return {
            "product_id": str(product.id),
            "total_stock": product.stock,
            "reserved_stock": product.reserved_stock,
            "available_stock": available_stock,
            "status": product.status
        }
    
    async def reserve_inventory(
        self,
        product_id: str,
        quantity: int,
        order_id: Optional[str] = None
    ) -> Optional[Product]:
        """Reserve inventory for an order"""
        # Check if product exists
        product = await self.repository.get_by_id(product_id)
        if not product:
            return None
        
        # Check if product is active
        if product.status != ProductStatus.ACTIVE:
            raise ValueError(f"Cannot reserve inventory for product with status: {product.status}")
        
        # Reserve stock
        return await self.repository.reserve_stock(product_id, quantity)
    
    async def release_inventory(
        self,
        product_id: str,
        quantity: int,
        order_id: Optional[str] = None
    ) -> Optional[Product]:
        """Release reserved inventory (e.g., on order cancel)"""
        # Check if product exists
        product = await self.repository.get_by_id(product_id)
        if not product:
            return None
        
        # Release stock
        return await self.repository.release_stock(product_id, quantity)

