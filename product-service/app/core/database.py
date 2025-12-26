import sys
from pathlib import Path
from typing import Optional, TYPE_CHECKING


from shared.database import get_async_mongo
from shared.logging_config import get_logger
from shared.config import get_settings

settings = get_settings()

if TYPE_CHECKING:
    from motor.motor_asyncio import AsyncIOMotorDatabase

logger = get_logger(__name__, settings.app.service_name)


class ProductDatabaseManager:
    """Product-specific database operations and index management"""
    
    def __init__(self):
        self.mongo = get_async_mongo()
    
    async def connect(self):
        """Connect to MongoDB"""
        await self.mongo.connect()
    
    @property
    def database(self) -> "AsyncIOMotorDatabase":
        """Get database instance"""
        return self.mongo.database
    
    @property
    def client(self):
        """Get MongoDB client"""
        return self.mongo.client
    
    async def close(self):
        """Close MongoDB connection"""
        await self.mongo.close()
    
    async def health_check(self) -> bool:
        """Check MongoDB health"""
        return await self.mongo.health_check()
    
    async def create_indexes(self):
        """Create product-specific indexes"""
        if self.mongo._database is None:
            await self.mongo.connect()
        
        try:
            # Products collection indexes
            products_collection = self.mongo.database.products
            
            # Create indexes
            # SKU unique index (sparse to allow nulls)
            await products_collection.create_index("sku", unique=True, sparse=True)
            await products_collection.create_index("vendor_id", sparse=True)
            await products_collection.create_index("name")
            await products_collection.create_index("category")
            await products_collection.create_index("status")
            await products_collection.create_index("price")
            await products_collection.create_index([("name", "text"), ("description", "text")])  # Text search index
            await products_collection.create_index("created_at")
            await products_collection.create_index("updated_at")
            
            logger.info("Product indexes created successfully")
        except Exception as e:
            logger.error(f"Failed to create product indexes: {e}")
            raise


# Global database manager instance (singleton pattern)
_db_manager: Optional[ProductDatabaseManager] = None


def get_db_manager() -> ProductDatabaseManager:
    """Get global product database manager instance"""
    global _db_manager
    if _db_manager is None:
        _db_manager = ProductDatabaseManager()
    return _db_manager


async def get_database() -> "AsyncIOMotorDatabase":
    """Get database instance (dependency injection)"""
    db_manager = get_db_manager()
    # Check if database is connected and valid for current event loop
    if db_manager.mongo._database is None or not db_manager.mongo._is_client_valid_for_current_loop():
        await db_manager.connect()
    return db_manager.database
