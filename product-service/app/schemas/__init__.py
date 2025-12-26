from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
from app.models import ProductStatus, ProductImage, ProductVariant, Product


class ProductCreateRequest(BaseModel):
    """Request schema for creating a product"""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    sku: Optional[str] = Field(None, max_length=100)
    price: float = Field(..., gt=0)
    compare_at_price: Optional[float] = Field(None, gt=0)
    cost_price: Optional[float] = Field(None, gt=0)
    stock: int = Field(default=0, ge=0)
    status: ProductStatus = Field(default=ProductStatus.DRAFT)
    category: Optional[str] = None
    categories: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    images: List[ProductImage] = Field(default_factory=list)
    variants: List[ProductVariant] = Field(default_factory=list)
    weight: Optional[float] = Field(None, gt=0)
    dimensions: Optional[dict] = None
    brand: Optional[str] = Field(None, max_length=100)
    vendor: Optional[str] = Field(None, max_length=100)
    vendor_id: Optional[str] = Field(None, max_length=100)
    barcode: Optional[str] = Field(None, max_length=100)
    metadata: dict = Field(default_factory=dict)


class ProductUpdateRequest(BaseModel):
    """Request schema for updating a product"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    sku: Optional[str] = Field(None, max_length=100)
    price: Optional[float] = Field(None, gt=0)
    compare_at_price: Optional[float] = Field(None, gt=0)
    cost_price: Optional[float] = Field(None, gt=0)
    stock: Optional[int] = Field(None, ge=0)
    status: Optional[ProductStatus] = None
    category: Optional[str] = None
    categories: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    images: Optional[List[ProductImage]] = None
    variants: Optional[List[ProductVariant]] = None
    weight: Optional[float] = Field(None, gt=0)
    dimensions: Optional[dict] = None
    brand: Optional[str] = Field(None, max_length=100)
    vendor: Optional[str] = Field(None, max_length=100)
    vendor_id: Optional[str] = Field(None, max_length=100)
    barcode: Optional[str] = Field(None, max_length=100)
    metadata: Optional[dict] = None


class ProductResponse(BaseModel):
    """Response schema for product"""
    id: str
    name: str
    description: Optional[str]
    sku: Optional[str]
    price: float
    compare_at_price: Optional[float]
    cost_price: Optional[float]
    stock: int
    reserved_stock: int
    status: ProductStatus
    category: Optional[str]
    categories: List[str]
    tags: List[str]
    images: List[ProductImage]
    variants: List[ProductVariant]
    weight: Optional[float]
    dimensions: Optional[dict]
    brand: Optional[str]
    vendor: Optional[str]
    vendor_id: Optional[str]
    barcode: Optional[str]
    metadata: dict
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str]
    updated_by: Optional[str]
    
    @classmethod
    def from_model(cls, product: "Product"):
        """Create response from Product model"""
        return cls(
            id=str(product.id),
            name=product.name,
            description=product.description,
            sku=product.sku,
            price=product.price,
            compare_at_price=product.compare_at_price,
            cost_price=product.cost_price,
            stock=product.stock,
            reserved_stock=product.reserved_stock,
            status=product.status,
            category=product.category,
            categories=product.categories,
            tags=product.tags,
            images=product.images,
            variants=product.variants,
            weight=product.weight,
            dimensions=product.dimensions,
            brand=product.brand,
            vendor=product.vendor,
            vendor_id=product.vendor_id,
            barcode=product.barcode,
            metadata=product.metadata,
            created_at=product.created_at,
            updated_at=product.updated_at,
            created_by=product.created_by,
            updated_by=product.updated_by
        )


class InventoryReserveRequest(BaseModel):
    """Request schema for reserving inventory"""
    quantity: int = Field(..., description="Quantity to reserve", gt=0)
    order_id: Optional[str] = Field(None, description="Order ID for tracking", max_length=100)
    expires_at: Optional[datetime] = Field(None, description="Reservation expiration time")


class InventoryReleaseRequest(BaseModel):
    """Request schema for releasing reserved inventory"""
    quantity: int = Field(..., description="Quantity to release", gt=0)
    order_id: Optional[str] = Field(None, description="Order ID for tracking", max_length=100)


class ProductListResponse(BaseModel):
    """Response schema for product list"""
    products: List[ProductResponse]
    total: int
    page: int
    limit: int
    pages: int


class InventoryAdjustRequest(BaseModel):
    """Request schema for adjusting inventory"""
    quantity: int = Field(..., description="Quantity to adjust (positive to increase, negative to decrease)")
    reason: Optional[str] = Field(None, description="Reason for adjustment", max_length=500)


class InventoryResponse(BaseModel):
    """Response schema for inventory information"""
    product_id: str
    total_stock: int = Field(..., description="Total stock quantity")
    reserved_stock: int = Field(..., description="Reserved stock quantity")
    available_stock: int = Field(..., description="Available stock (total - reserved)")
    status: ProductStatus = Field(..., description="Product status")

