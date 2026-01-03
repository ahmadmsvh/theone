import asyncio
from typing import Dict, Any, List, Optional
import httpx
from fastapi import HTTPException
from shared.logging_config import get_logger
from shared.config import get_settings

logger = get_logger(__name__, "order-service")
settings = get_settings()

PRODUCT_SERVICE_URL = "http://product-service:5001"
import os
PRODUCT_SERVICE_URL = os.getenv("PRODUCT_SERVICE_URL", PRODUCT_SERVICE_URL)


class ProductServiceClient:
    
    def __init__(self, base_url: str = PRODUCT_SERVICE_URL, timeout: float = 10.0, max_retries: int = 3):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                follow_redirects=True
            )
        return self._client
    
    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
    
    async def _request_with_retry(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> httpx.Response:
        client = await self._get_client()
        
        last_exception = None
        for attempt in range(self.max_retries):
            try:
                response = await client.request(method, url, **kwargs)
                if response.status_code < 500:
                    return response
                
                logger.warning(
                    f"Product service returned {response.status_code} on attempt {attempt + 1}/{self.max_retries}"
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    last_exception = None
                else:
                    response.raise_for_status()
            except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as e:
                last_exception = e
                logger.warning(
                    f"Product service connection error on attempt {attempt + 1}/{self.max_retries}: {e}"
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                else:
                    logger.error(f"Product service unavailable after {self.max_retries} attempts")
                    raise HTTPException(
                        status_code=503,
                        detail="Product service is currently unavailable"
                    ) from e
        
        if last_exception:
            raise last_exception
        
        return response
    
    async def get_product(self, product_id: str, token: str) -> Dict[str, Any]:
        try:
            response = await self._request_with_retry(
                "GET",
                f"/api/v1/products/{product_id}",
                headers={"Authorization": f"Bearer {token}"}
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ValueError(f"Product {product_id} not found")
            logger.error(f"Error getting product {product_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting product {product_id}: {e}")
            raise
    
    async def get_inventory(self, product_id: str, token: str) -> Dict[str, Any]:
        try:
            response = await self._request_with_retry(
                "GET",
                f"/api/v1/products/{product_id}/inventory",
                headers={"Authorization": f"Bearer {token}"}
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ValueError(f"Product {product_id} not found")
            logger.error(f"Error getting inventory for product {product_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting inventory for product {product_id}: {e}")
            raise
    
    async def reserve_inventory(
        self,
        product_id: str,
        quantity: int,
        order_id: str,
        token: str
    ) -> Dict[str, Any]:
        try:
            response = await self._request_with_retry(
                "POST",
                f"/api/v1/products/{product_id}/inventory/reserve",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                json={
                    "quantity": quantity,
                    "order_id": order_id
                }
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ValueError(f"Product {product_id} not found")
            elif e.response.status_code == 400:
                error_detail = e.response.json().get("error", "Invalid request")
                raise ValueError(error_detail)
            logger.error(f"Error reserving inventory for product {product_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error reserving inventory for product {product_id}: {e}")
            raise
    
    async def release_inventory(
        self,
        product_id: str,
        quantity: int,
        order_id: str,
        token: str
    ) -> Dict[str, Any]:
        try:
            response = await self._request_with_retry(
                "POST",
                f"/api/v1/products/{product_id}/inventory/release",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                json={
                    "quantity": quantity,
                    "order_id": order_id
                }
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ValueError(f"Product {product_id} not found")
            elif e.response.status_code == 400:
                error_detail = e.response.json().get("error", "Invalid request")
                raise ValueError(error_detail)
            logger.error(f"Error releasing inventory for product {product_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error releasing inventory for product {product_id}: {e}")
            raise
    
    async def validate_cart_items(
        self,
        cart_items: List[Dict[str, Any]],
        token: str
    ) -> List[Dict[str, Any]]:
        validated_items = []
        
        for item in cart_items:
            product_id = item.get("product_id")
            quantity = item.get("quantity", 1)
            
            if not product_id:
                raise ValueError("Cart item missing product_id")
            if quantity <= 0:
                raise ValueError(f"Invalid quantity for product {product_id}: {quantity}")
            
            try:
                product = await self.get_product(product_id, token)
                
                inventory = await self.get_inventory(product_id, token)
                
                available_stock = inventory.get("available_stock", 0)
                if available_stock < quantity:
                    raise ValueError(
                        f"Insufficient stock for product {product_id}. "
                        f"Available: {available_stock}, Requested: {quantity}"
                    )
                
                validated_items.append({
                    "product_id": product_id,
                    "sku": product.get("sku"),
                    "name": product.get("name"),
                    "price": product.get("price"),
                    "quantity": quantity
                })
            except ValueError as e: 
                raise
            except Exception as e:
                logger.error(f"Error validating cart item {product_id}: {e}")
                raise ValueError(f"Failed to validate product {product_id}: {str(e)}")
        
        return validated_items


_product_client: Optional[ProductServiceClient] = None


async def get_product_client() -> ProductServiceClient:
    global _product_client
    if _product_client is None:
        _product_client = ProductServiceClient()
    return _product_client


async def close_product_client():  
    global _product_client
    if _product_client:
        await _product_client.close()
        _product_client = None

