"""
Database Initialization and Seeding Script.
Creates tables and ensures default development users exist.
"""

import sys
from pathlib import Path

# Add backend directory to Python path if run standalone
backend_dir = Path(__file__).resolve().parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.logging_config import logger
from app.core.security import hash_password
from app.db.database import Base, SessionLocal, engine
from app.models.user import User
from app.services.auth import ensure_default_roles


def init_and_seed() -> None:
    """Create database tables and seed baseline users."""
    logger.info("Initializing database schema...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database schema created successfully.")

    db = SessionLocal()
    try:
        roles_map = ensure_default_roles(db)
        admin_role = roles_map["admin"]
        user_role = roles_map["user"]

        # Check / Seed Admin User
        admin_email = "admin@wan2gp.local"
        admin = db.query(User).filter(User.email == admin_email).first()
        if not admin:
            admin = User(
                email=admin_email,
                username="admin",
                first_name="Platform",
                last_name="Admin",
                hashed_password=hash_password("Admin12345!"),
                is_active=True,
            )
            admin.roles.append(admin_role)
            admin.roles.append(user_role)
            db.add(admin)
            logger.info("Created default admin user: %s (password: Admin12345!)", admin_email)

        # Check / Seed Demo User
        demo_email = "user@wan2gp.local"
        demo = db.query(User).filter(User.email == demo_email).first()
        if not demo:
            demo = User(
                email=demo_email,
                username="demouser",
                first_name="Demo",
                last_name="User",
                hashed_password=hash_password("User12345!"),
                is_active=True,
            )
            demo.roles.append(user_role)
            db.add(demo)
            logger.info("Created default demo user: %s (password: User12345!)", demo_email)

        db.commit()
        logger.info("Database setup and seeding completed successfully.")
    except Exception as exc:
        db.rollback()
        logger.error("Failed to seed database: %s", exc)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    init_and_seed()
