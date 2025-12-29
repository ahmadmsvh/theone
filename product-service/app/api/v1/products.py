from flask import Blueprint, request, jsonify

from app.core.auth import require_auth, require_role, require_any_role
from app.core.error_handlers import handle_api_errors, not_found_response
from app.utils import async_route
from app.services.product_service import get_product_service
from app.schemas import (
    ProductCreateRequest,
    ProductUpdateRequest,
    ProductResponse,
    ProductListResponse,
    InventoryAdjustRequest,
    InventoryResponse,
    InventoryReserveRequest,
    InventoryReleaseRequest
)

bp = Blueprint("products", __name__, url_prefix="/api/v1/products")


@bp.route("", methods=["POST"])
@require_role("Vendor")
@async_route
@handle_api_errors
async def create_product(current_user):
    product_data = ProductCreateRequest(**request.json)
    service = await get_product_service()
    
    user_id = current_user.get("sub")
    vendor_id = current_user.get("sub")
    
    product = await service.create_product(
        product_data=product_data,
        user_id=user_id,
        vendor_id=vendor_id
    )
    
    response = ProductResponse.from_model(product)
    return jsonify(response.model_dump()), 201


@bp.route("", methods=["GET"])
@async_route
@handle_api_errors
async def list_products():
    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 10))
    category = request.args.get("category")
    search = request.args.get("search")
    status = request.args.get("status")
    
    if page < 1:
        page = 1
    if limit < 1 or limit > 20:
        limit = 10
    
    service = await get_product_service()
    
    result = await service.list_products(
        page=page,
        limit=limit,
        category=category,
        search=search,
        status=status
    )
    
    products_response = [ProductResponse.from_model(p).model_dump() for p in result["products"]]
    response = ProductListResponse(
        products=products_response,
        total=result["total"],
        page=result["page"],
        limit=result["limit"],
        pages=result["pages"]
    )
    
    return jsonify(response.model_dump()), 200


@bp.route("/<product_id>", methods=["GET"])
@async_route
@handle_api_errors
async def get_product(product_id):
    service = await get_product_service()
    product = await service.get_product(product_id)
    
    if not product:
        return not_found_response("Product not found")
    
    response = ProductResponse.from_model(product)
    return jsonify(response.model_dump()), 200


@bp.route("/<product_id>", methods=["PUT"])
@require_any_role("Vendor", "Admin")
@async_route
@handle_api_errors
async def update_product(product_id, current_user):
    product_data = ProductUpdateRequest(**request.json)
    service = await get_product_service()
    
    user_id = current_user.get("sub")
    user_roles = current_user.get("roles", [])
    
    product = await service.update_product(
        product_id=product_id,
        product_data=product_data,
        user_id=user_id,
        user_roles=user_roles
    )
    
    if not product:
        return not_found_response("Product not found")
    
    response = ProductResponse.from_model(product)
    return jsonify(response.model_dump()), 200


@bp.route("/<product_id>", methods=["DELETE"])
@require_role("Admin")
@async_route
@handle_api_errors
async def delete_product(product_id, current_user):
    service = await get_product_service()
    deleted = await service.delete_product(product_id)
    
    if not deleted:
        return not_found_response("Product not found")
    
    return jsonify({"message": "Product deleted successfully"}), 200


@bp.route("/<product_id>/inventory", methods=["POST"])
@require_role("Vendor")
@async_route
@handle_api_errors
async def adjust_inventory(product_id, current_user):
    inventory_data = InventoryAdjustRequest(**request.json)
    service = await get_product_service()
    
    user_id = current_user.get("sub")
    user_roles = current_user.get("roles", [])
    
    product = await service.adjust_inventory(
        product_id=product_id,
        quantity=inventory_data.quantity,
        user_id=user_id,
        user_roles=user_roles
    )
    
    if not product:
        return not_found_response("Product not found")
    
    response = ProductResponse.from_model(product)
    return jsonify(response.model_dump()), 200


@bp.route("/<product_id>/inventory", methods=["GET"])
@async_route
@handle_api_errors
async def get_inventory(product_id):
    service = await get_product_service()
    inventory = await service.get_inventory(product_id)
    
    if not inventory:
        return not_found_response("Product not found")
    
    response = InventoryResponse(**inventory)
    return jsonify(response.model_dump()), 200


@bp.route("/<product_id>/inventory/reserve", methods=["POST"])
@require_auth
@async_route
@handle_api_errors
async def reserve_inventory(product_id, current_user):
    reserve_data = InventoryReserveRequest(**request.json)
    service = await get_product_service()
    
    product = await service.reserve_inventory(
        product_id=product_id,
        quantity=reserve_data.quantity,
        order_id=reserve_data.order_id
    )
    
    if not product:
        return not_found_response("Product not found")
    
    response = ProductResponse.from_model(product)
    return jsonify(response.model_dump()), 200


@bp.route("/<product_id>/inventory/release", methods=["POST"])
@require_auth
@async_route
@handle_api_errors
async def release_inventory(product_id, current_user):
    release_data = InventoryReleaseRequest(**request.json)
    service = await get_product_service()
    
    product = await service.release_inventory(
        product_id=product_id,
        quantity=release_data.quantity,
        order_id=release_data.order_id
    )
    
    if not product:
        return not_found_response("Product not found")
    
    response = ProductResponse.from_model(product)
    return jsonify(response.model_dump()), 200

