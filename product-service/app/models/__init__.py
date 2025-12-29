from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from bson import ObjectId
from enum import Enum


class PyObjectId(ObjectId):     
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        from pydantic_core import core_schema
        
        def validate_from_str(value: str) -> ObjectId:
            if ObjectId.is_valid(value):
                return ObjectId(value)
            raise ValueError("Invalid ObjectId")
        
        def serialize_to_str(value: ObjectId) -> str:
            return str(value)
        
        return core_schema.json_or_python_schema(
            json_schema=core_schema.no_info_plain_validator_function(validate_from_str),
            python_schema=core_schema.union_schema([
                core_schema.is_instance_schema(ObjectId),
                core_schema.no_info_plain_validator_function(validate_from_str),
            ]),
            serialization=core_schema.plain_serializer_function_ser_schema(
                serialize_to_str,
                when_used='json'
            )
        )
    
    @classmethod
    def __get_pydantic_json_schema__(cls, field_schema, handler):
        field_schema.update(type="string", format="objectid")


class ProductStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    OUT_OF_STOCK = "out_of_stock"
    DISCONTINUED = "discontinued"
    DRAFT = "draft"


class ProductCategory(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    id: Optional[str] = Field(None, description="Category ID")
    name: str = Field(..., description="Category name", min_length=1, max_length=100)
    slug: Optional[str] = Field(None, description="Category URL slug")
    parent_id: Optional[str] = Field(None, description="Parent category ID for nested categories")


class ProductImage(BaseModel):
    url: str = Field(..., description="Image URL")
    alt_text: Optional[str] = Field(None, description="Image alt text")
    is_primary: bool = Field(default=False, description="Is this the primary image")
    order: int = Field(default=0, description="Display order")


class ProductVariant(BaseModel):
    name: str = Field(..., description="Variant name (e.g., 'Size', 'Color')")
    value: str = Field(..., description="Variant value (e.g., 'Large', 'Red')")
    sku: Optional[str] = Field(None, description="Variant-specific SKU")
    price_modifier: float = Field(default=0.0, description="Price adjustment for this variant")
    stock: int = Field(default=0, description="Stock quantity for this variant")


class Product(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        populate_by_name=True
    )
    
    id: Optional[PyObjectId] = Field(default_factory=ObjectId, alias="_id", description="Product ID")
    name: str = Field(..., description="Product name", min_length=1, max_length=200)
    description: Optional[str] = Field(None, description="Product description")
    sku: Optional[str] = Field(None, description="Stock Keeping Unit (unique identifier)", max_length=100)
    price: float = Field(..., description="Product price", gt=0)
    compare_at_price: Optional[float] = Field(None, description="Original price (for discounts)", gt=0)
    cost_price: Optional[float] = Field(None, description="Cost price (internal)", gt=0)
    stock: int = Field(default=0, description="Stock quantity", ge=0)
    reserved_stock: int = Field(default=0, description="Reserved stock quantity (for orders)", ge=0)
    status: ProductStatus = Field(default=ProductStatus.DRAFT, description="Product status")
    category: Optional[str] = Field(None, description="Category ID or name")
    categories: List[str] = Field(default_factory=list, description="List of category IDs")
    tags: List[str] = Field(default_factory=list, description="Product tags")
    images: List[ProductImage] = Field(default_factory=list, description="Product images")
    variants: List[ProductVariant] = Field(default_factory=list, description="Product variants")
    weight: Optional[float] = Field(None, description="Product weight (kg)", gt=0)
    dimensions: Optional[Dict[str, float]] = Field(None, description="Product dimensions (length, width, height)")
    brand: Optional[str] = Field(None, description="Product brand", max_length=100)
    vendor: Optional[str] = Field(None, description="Product vendor/supplier", max_length=100)
    vendor_id: Optional[str] = Field(None, description="Vendor ID (for vendor lookup)", max_length=100)
    barcode: Optional[str] = Field(None, description="Product barcode", max_length=100)
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Creation timestamp")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Last update timestamp")
    created_by: Optional[str] = Field(None, description="User ID who created the product")
    updated_by: Optional[str] = Field(None, description="User ID who last updated the product")
    
    @field_validator("price", "compare_at_price", "cost_price", mode="before")
    @classmethod
    def validate_price(cls, v):
        if v is not None and v < 0:
            raise ValueError("Price must be greater than or equal to 0")
        return v
    
    @model_validator(mode="after")
    def validate_compare_price(self):
        if self.compare_at_price is not None and self.price is not None:
            if self.compare_at_price <= self.price:
                raise ValueError("compare_at_price must be greater than price")
        return self
    
    @model_validator(mode="after")
    def validate_reserved_stock(self):
        if self.reserved_stock > self.stock:
            raise ValueError("reserved_stock cannot exceed stock")
        return self


