from typing import Optional, List, Dict, Any
from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime
import os
from shared.logging_config import get_logger
from app.models import Product
from app.schemas import ProductCreateRequest, ProductUpdateRequest

logger = get_logger(__name__, os.getenv("SERVICE_NAME"))


class ProductRepository:
    """Repository for product database operations"""
    
    def __init__(self, database: AsyncIOMotorDatabase):
        self.db = database
        self.collection = database.products
    
    async def create(self, product_data: ProductCreateRequest, user_id: str) -> Product:
        """Create a new product"""
        try:
            product_dict = product_data.model_dump(exclude_none=True)
            product_dict["created_at"] = datetime.utcnow()
            product_dict["updated_at"] = datetime.utcnow()
            product_dict["created_by"] = user_id
            # Ensure reserved_stock is set (defaults to 0 for new products)
            if "reserved_stock" not in product_dict:
                product_dict["reserved_stock"] = 0
            
            result = await self.collection.insert_one(product_dict)
            created = await self.collection.find_one({"_id": result.inserted_id})
            
            return Product(**created)
        except Exception as e:
            logger.error(f"Error creating product: {e}")
            raise
    
    async def get_by_id(self, product_id: str) -> Optional[Product]:
        """Get product by ID"""
        try:
            if not ObjectId.is_valid(product_id):
                return None
            
            product = await self.collection.find_one({"_id": ObjectId(product_id)})
            if not product:
                return None
            
            return Product(**product)
        except (InvalidId, Exception) as e:
            logger.error(f"Error getting product by ID {product_id}: {e}")
            return None
    
    async def get_by_sku(self, sku: str) -> Optional[Product]:
        """Get product by SKU"""
        try:
            product = await self.collection.find_one({"sku": sku})
            if not product:
                return None
            
            return Product(**product)
        except Exception as e:
            logger.error(f"Error getting product by SKU {sku}: {e}")
            return None
    
    async def list(
        self,
        skip: int = 0,
        limit: int = 10,
        category: Optional[str] = None,
        search: Optional[str] = None,
        status: Optional[str] = None
    ) -> tuple[List[Product], int]:
        """List products with pagination and filters"""
        try:
            query: Dict[str, Any] = {}
            
            # Apply filters
            if category:
                query["category"] = category
            if status:
                query["status"] = status
            if search:
                query["$text"] = {"$search": search}
            
            # Get total count
            total = await self.collection.count_documents(query)
            
            # Get products
            cursor = self.collection.find(query).skip(skip).limit(limit).sort("created_at", -1)
            products = await cursor.to_list(length=limit)
            
            product_list = [Product(**p) for p in products]
            return product_list, total
        except (RuntimeError, ValueError) as e:
            # Check if this is the "attached to a different loop" error
            error_msg = str(e)
            if "different loop" in error_msg.lower() or "attached to a different" in error_msg.lower():
                logger.warning("Database connection attached to different event loop, reconnecting...")
                # Reconnect and update collection reference
                from app.core.database import get_database
                self.db = await get_database()
                self.collection = self.db.products
                # Retry the operation
                total = await self.collection.count_documents(query)
                cursor = self.collection.find(query).skip(skip).limit(limit).sort("created_at", -1)
                products = await cursor.to_list(length=limit)
                product_list = [Product(**p) for p in products]
                return product_list, total
            else:
                logger.error(f"Error listing products: {e}")
                raise
        except Exception as e:
            logger.error(f"Error listing products: {e}")
            raise
    
    async def update(self, product_id: str, product_data: ProductUpdateRequest, user_id: str) -> Optional[Product]:
        """Update a product"""
        try:
            if not ObjectId.is_valid(product_id):
                return None
            
            update_dict = product_data.model_dump(exclude_none=True)
            update_dict["updated_at"] = datetime.utcnow()
            update_dict["updated_by"] = user_id
            
            result = await self.collection.update_one(
                {"_id": ObjectId(product_id)},
                {"$set": update_dict}
            )
            
            if result.matched_count == 0:
                return None
            
            updated = await self.collection.find_one({"_id": ObjectId(product_id)})
            return Product(**updated)
        except (InvalidId, Exception) as e:
            logger.error(f"Error updating product {product_id}: {e}")
            return None
    
    async def delete(self, product_id: str) -> bool:
        """Delete a product"""
        try:
            if not ObjectId.is_valid(product_id):
                return False
            
            result = await self.collection.delete_one({"_id": ObjectId(product_id)})
            return result.deleted_count > 0
        except (InvalidId, Exception) as e:
            logger.error(f"Error deleting product {product_id}: {e}")
            return False
    
    async def sku_exists(self, sku: str, exclude_id: Optional[str] = None) -> bool:
        """Check if SKU already exists"""
        try:
            query: Dict[str, Any] = {"sku": sku}
            if exclude_id and ObjectId.is_valid(exclude_id):
                query["_id"] = {"$ne": ObjectId(exclude_id)}
            
            count = await self.collection.count_documents(query)
            return count > 0
        except Exception as e:
            logger.error(f"Error checking SKU existence: {e}")
            return False
    
    async def adjust_stock(self, product_id: str, quantity_change: int) -> Optional[Product]:
        """Adjust product stock (increase or decrease)"""
        try:
            if not ObjectId.is_valid(product_id):
                return None
            
            # Get current product
            product = await self.collection.find_one({"_id": ObjectId(product_id)})
            if not product:
                return None
            
            current_stock = product.get("stock", 0)
            new_stock = current_stock + quantity_change
            
            # Ensure stock doesn't go negative
            if new_stock < 0:
                raise ValueError(f"Insufficient stock. Current: {current_stock}, Requested change: {quantity_change}")
            
            # Update stock and timestamp
            result = await self.collection.update_one(
                {"_id": ObjectId(product_id)},
                {
                    "$set": {
                        "stock": new_stock,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            if result.matched_count == 0:
                return None
            
            # If reserved_stock exceeds new stock, adjust it
            updated_product = await self.collection.find_one({"_id": ObjectId(product_id)})
            if updated_product:
                reserved = updated_product.get("reserved_stock", 0)
                if reserved > new_stock:
                    await self.collection.update_one(
                        {"_id": ObjectId(product_id)},
                        {
                            "$set": {
                                "reserved_stock": new_stock,
                                "updated_at": datetime.utcnow()
                            }
                        }
                    )
                    updated_product["reserved_stock"] = new_stock
                    updated_product["stock"] = new_stock
            
            return Product(**updated_product) if updated_product else None
        except (InvalidId, Exception) as e:
            logger.error(f"Error adjusting stock for product {product_id}: {e}")
            raise
    
    async def reserve_stock(self, product_id: str, quantity: int) -> Optional[Product]:
        """Reserve stock for an order"""
        try:
            if not ObjectId.is_valid(product_id):
                return None
            
            if quantity <= 0:
                raise ValueError("Reservation quantity must be positive")
            
            # Get current product
            product = await self.collection.find_one({"_id": ObjectId(product_id)})
            if not product:
                return None
            
            current_stock = product.get("stock", 0)
            current_reserved = product.get("reserved_stock", 0)
            available_stock = current_stock - current_reserved
            
            # Check if enough stock is available
            if available_stock < quantity:
                raise ValueError(
                    f"Insufficient available stock. Available: {available_stock}, Requested: {quantity}"
                )
            
            # Update reserved stock
            new_reserved = current_reserved + quantity
            result = await self.collection.update_one(
                {"_id": ObjectId(product_id)},
                {
                    "$set": {
                        "reserved_stock": new_reserved,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            if result.matched_count == 0:
                return None
            
            updated = await self.collection.find_one({"_id": ObjectId(product_id)})
            return Product(**updated) if updated else None
        except (InvalidId, Exception) as e:
            logger.error(f"Error reserving stock for product {product_id}: {e}")
            raise
    
    async def release_stock(self, product_id: str, quantity: int) -> Optional[Product]:
        """Release reserved stock"""
        try:
            if not ObjectId.is_valid(product_id):
                return None
            
            if quantity <= 0:
                raise ValueError("Release quantity must be positive")
            
            # Get current product
            product = await self.collection.find_one({"_id": ObjectId(product_id)})
            if not product:
                return None
            
            current_reserved = product.get("reserved_stock", 0)
            
            # Check if enough stock is reserved
            if current_reserved < quantity:
                raise ValueError(
                    f"Insufficient reserved stock. Reserved: {current_reserved}, Requested release: {quantity}"
                )
            
            # Update reserved stock
            new_reserved = current_reserved - quantity
            result = await self.collection.update_one(
                {"_id": ObjectId(product_id)},
                {
                    "$set": {
                        "reserved_stock": max(0, new_reserved),  # Ensure non-negative
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            if result.matched_count == 0:
                return None
            
            updated = await self.collection.find_one({"_id": ObjectId(product_id)})
            return Product(**updated) if updated else None
        except (InvalidId, Exception) as e:
            logger.error(f"Error releasing stock for product {product_id}: {e}")
            raise

