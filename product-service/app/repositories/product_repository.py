from typing import Optional, List, Dict, Any
from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timezone
import os
from shared.logging_config import get_logger
from app.models import Product
from app.schemas import ProductCreateRequest, ProductUpdateRequest

logger = get_logger(__name__, os.getenv("SERVICE_NAME"))


class ProductRepository:
    
    def __init__(self, database: AsyncIOMotorDatabase):
        self.db = database
        self.collection = database.products
    
    def _validate_object_id(self, product_id: str) -> Optional[ObjectId]:
        if not ObjectId.is_valid(product_id):
            return None
        try:
            return ObjectId(product_id)
        except (InvalidId, ValueError):
            return None
    
    def _to_product(self, doc: Optional[Dict[str, Any]]) -> Optional[Product]:
        if not doc:
            return None
        try:
            return Product(**doc)
        except Exception as e:
            logger.error(f"Error converting document to Product: {e}")
            return None
    
    def _to_product_list(self, docs: List[Dict[str, Any]]) -> List[Product]:
        products = []
        for doc in docs:
            product = self._to_product(doc)
            if product:
                products.append(product)
        return products
    
    async def _get_product_doc_by_id(self, product_id: str) -> Optional[Dict[str, Any]]:
        object_id = self._validate_object_id(product_id)
        if not object_id:
            return None
        
        try:
            return await self.collection.find_one({"_id": object_id})
        except Exception as e:
            logger.error(f"Error fetching product document {product_id}: {e}")
            return None
    
    def _get_current_timestamp(self) -> datetime:
        return datetime.now(timezone.utc)
    
    async def create(self, product_data: ProductCreateRequest, user_id: str) -> Product:
        try:
            product_dict = product_data.model_dump(exclude_none=True)
            now = self._get_current_timestamp()
            product_dict["created_at"] = now
            product_dict["updated_at"] = now
            product_dict["created_by"] = user_id
            if "reserved_stock" not in product_dict:
                product_dict["reserved_stock"] = 0
            
            result = await self.collection.insert_one(product_dict)
            created = await self.collection.find_one({"_id": result.inserted_id})
            
            return self._to_product(created)
        except Exception as e:
            logger.error(f"Error creating product: {e}")
            raise
    
    async def get_by_id(self, product_id: str) -> Optional[Product]:
        try:
            product_doc = await self._get_product_doc_by_id(product_id)
            return self._to_product(product_doc)
        except Exception as e:
            logger.error(f"Error getting product by ID {product_id}: {e}")
            return None
    
    async def get_by_sku(self, sku: str) -> Optional[Product]:
        try:
            product_doc = await self.collection.find_one({"sku": sku})
            return self._to_product(product_doc)
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
        try:
            query: Dict[str, Any] = {}
            
            if category:
                query["category"] = category
            if status:
                query["status"] = status
            if search:
                query["$text"] = {"$search": search}
            
            total = await self.collection.count_documents(query)
            
            cursor = self.collection.find(query).skip(skip).limit(limit).sort("created_at", -1)
            products = await cursor.to_list(length=limit)
            
            product_list = self._to_product_list(products)
            return product_list, total
        except (RuntimeError, ValueError) as e:
            error_msg = str(e)
            if "different loop" in error_msg.lower() or "attached to a different" in error_msg.lower():
                logger.warning("Database connection attached to different event loop, reconnecting...")
                from app.core.database import get_database
                self.db = await get_database()
                self.collection = self.db.products
                total = await self.collection.count_documents(query)
                cursor = self.collection.find(query).skip(skip).limit(limit).sort("created_at", -1)
                products = await cursor.to_list(length=limit)
                product_list = self._to_product_list(products)
                return product_list, total
            else:
                logger.error(f"Error listing products: {e}")
                raise
        except Exception as e:
            logger.error(f"Error listing products: {e}")
            raise
    
    async def update(self, product_id: str, product_data: ProductUpdateRequest, user_id: str) -> Optional[Product]:
        try:
            object_id = self._validate_object_id(product_id)
            if not object_id:
                return None
            
            update_dict = product_data.model_dump(exclude_none=True)
            update_dict["updated_at"] = self._get_current_timestamp()
            update_dict["updated_by"] = user_id
            
            result = await self.collection.update_one(
                {"_id": object_id},
                {"$set": update_dict}
            )
            
            if result.matched_count == 0:
                return None
            
            updated = await self.collection.find_one({"_id": object_id})
            return self._to_product(updated)
        except Exception as e:
            logger.error(f"Error updating product {product_id}: {e}")
            return None
    
    async def delete(self, product_id: str) -> bool:
        try:
            object_id = self._validate_object_id(product_id)
            if not object_id:
                return False
            
            result = await self.collection.delete_one({"_id": object_id})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting product {product_id}: {e}")
            return False
    
    async def sku_exists(self, sku: str, exclude_id: Optional[str] = None) -> bool:
        try:
            query: Dict[str, Any] = {"sku": sku}
            if exclude_id:
                object_id = self._validate_object_id(exclude_id)
                if object_id:
                    query["_id"] = {"$ne": object_id}
            
            count = await self.collection.count_documents(query)
            return count > 0
        except Exception as e:
            logger.error(f"Error checking SKU existence: {e}")
            return False
    
    async def adjust_stock(self, product_id: str, quantity_change: int) -> Optional[Product]:
        try:
            object_id = self._validate_object_id(product_id)
            if not object_id:
                return None
            
            timestamp = self._get_current_timestamp()
            
            if quantity_change < 0:
                result = await self.collection.find_one_and_update(
                    {
                        "_id": object_id,
                        "stock": {"$gte": abs(quantity_change)}
                    },
                    {
                        "$inc": {"stock": quantity_change},
                        "$set": {"updated_at": timestamp}
                    },
                    return_document=True
                )
                
                if not result:
                    product = await self.collection.find_one({"_id": object_id})
                    if not product:
                        return None
                    current_stock = product.get("stock", 0)
                    raise ValueError(
                        f"Insufficient stock. Current: {current_stock}, Requested change: {quantity_change}"
                    )
            else:
                result = await self.collection.find_one_and_update(
                    {"_id": object_id},
                    {
                        "$inc": {"stock": quantity_change},
                        "$set": {"updated_at": timestamp}
                    },
                    return_document=True
                )
                
                if not result:
                    return None
            
            if result:
                stock = result.get("stock", 0)
                reserved = result.get("reserved_stock", 0)
                if reserved > stock:
                    await self.collection.update_one(
                        {"_id": object_id, "reserved_stock": {"$gt": stock}},
                        {
                            "$set": {
                                "reserved_stock": stock,
                                "updated_at": timestamp
                            }
                        }
                    )
                    result["reserved_stock"] = stock
            
            return self._to_product(result)
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error adjusting stock for product {product_id}: {e}")
            raise
    
    async def reserve_stock(self, product_id: str, quantity: int) -> Optional[Product]:

        try:
            object_id = self._validate_object_id(product_id)
            if not object_id:
                return None
            
            if quantity <= 0:
                raise ValueError("Reservation quantity must be positive")
            
            timestamp = self._get_current_timestamp()
            
            result = await self.collection.find_one_and_update(
                {
                    "_id": object_id,
                    "$expr": {
                        "$gte": [
                            {"$subtract": ["$stock", "$reserved_stock"]},
                            quantity
                        ]
                    }
                },
                {
                    "$inc": {"reserved_stock": quantity},
                    "$set": {"updated_at": timestamp}
                },
                return_document=True
            )
            
            if not result:
                product = await self.collection.find_one({"_id": object_id})
                if not product:
                    return None
                current_stock = product.get("stock", 0)
                current_reserved = product.get("reserved_stock", 0)
                available_stock = current_stock - current_reserved
                raise ValueError(
                    f"Insufficient available stock. Available: {available_stock}, Requested: {quantity}"
                )
            
            return self._to_product(result)
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error reserving stock for product {product_id}: {e}")
            raise
    
    async def release_stock(self, product_id: str, quantity: int) -> Optional[Product]:

        try:
            object_id = self._validate_object_id(product_id)
            if not object_id:
                return None
            
            if quantity <= 0:
                raise ValueError("Release quantity must be positive")
            
            timestamp = self._get_current_timestamp()
            
            result = await self.collection.find_one_and_update(
                {
                    "_id": object_id,
                    "reserved_stock": {"$gte": quantity}
                },
                {
                    "$inc": {"reserved_stock": -quantity},
                    "$set": {"updated_at": timestamp}
                },
                return_document=True
            )
            
            if not result:
                product = await self.collection.find_one({"_id": object_id})
                if not product:
                    return None
                current_reserved = product.get("reserved_stock", 0)
                raise ValueError(
                    f"Insufficient reserved stock. Reserved: {current_reserved}, Requested release: {quantity}"
                )
            
            return self._to_product(result)
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error releasing stock for product {product_id}: {e}")
            raise
    
    async def complete_order_deduction(self, product_id: str, quantity: int) -> Optional[Product]:
        try:
            object_id = self._validate_object_id(product_id)
            if not object_id:
                return None
            
            if quantity <= 0:
                raise ValueError("Deduction quantity must be positive")
            
            timestamp = self._get_current_timestamp()
            
            result = await self.collection.find_one_and_update(
                {
                    "_id": object_id,
                    "stock": {"$gte": quantity},
                    "reserved_stock": {"$gte": quantity}
                },
                {
                    "$inc": {
                        "stock": -quantity,
                        "reserved_stock": -quantity
                    },
                    "$set": {"updated_at": timestamp}
                },
                return_document=True
            )
            
            if not result:
                product = await self.collection.find_one({"_id": object_id})
                if not product:
                    return None
                current_stock = product.get("stock", 0)
                current_reserved = product.get("reserved_stock", 0)
                
                if current_reserved < quantity:
                    raise ValueError(
                        f"Insufficient reserved stock. Reserved: {current_reserved}, Requested deduction: {quantity}"
                    )
                if current_stock < quantity:
                    raise ValueError(
                        f"Insufficient total stock. Total: {current_stock}, Requested deduction: {quantity}"
                    )
                raise ValueError(f"Unable to complete deduction for product {product_id}")
            
            return self._to_product(result)
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error completing order deduction for product {product_id}: {e}")
            raise

