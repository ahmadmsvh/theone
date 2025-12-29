import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "shared"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import DatabaseManager                       
from app.repositories.role_repository import RoleRepository
from shared.logging_config import get_logger

logger = get_logger(__name__, "auth-service")


def seed_roles():
    db_manager = DatabaseManager()
    db_manager.create_engine()
    db_manager.create_session_factory()
    session_factory = db_manager.session_factory
    
    db = session_factory()
    
    try:
        role_repo = RoleRepository(db)
        
        initial_roles = [
            {"name": "Customer", "description": "Default customer role"},
            {"name": "Vendor", "description": "Vendor role for sellers"},
            {"name": "Admin", "description": "Administrator role with full access"},
        ]
        
        created_count = 0
        skipped_count = 0
        
        for role_data in initial_roles:
            existing_role = role_repo.get_by_name(role_data["name"])
            if existing_role:
                logger.info(f"Role '{role_data['name']}' already exists, skipping...")
                skipped_count += 1
                continue
            
            try:
                role_repo.create(
                    name=role_data["name"],
                    description=role_data["description"]
                )
                logger.info(f"Created role: {role_data['name']}")
                created_count += 1
            except Exception as e:
                logger.error(f"Failed to create role '{role_data['name']}': {e}")
        
        logger.info(
            f"Role seeding completed. Created: {created_count}, Skipped: {skipped_count}"
        )
        
    except Exception as e:
        logger.error(f"Error during role seeding: {e}", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    logger.info("Starting role seeding...")
    seed_roles()
    logger.info("Role seeding completed successfully!")
