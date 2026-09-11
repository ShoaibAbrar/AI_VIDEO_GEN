"""
Authentication and authorization services.
"""

from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.user import User, Role
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, get_token_expiry_seconds
from app.core.exceptions import UnauthorizedException, ValidationException, NotFoundError
from app.schemas.auth import UserCreate, UserLogin, TokenResponse
from datetime import datetime


def ensure_default_roles(db: Session) -> dict[str, Role]:
    """Ensure required RBAC roles exist in the current database."""
    role_names = ["user", "admin", "manager"]
    existing_roles = {
        role.name: role for role in db.query(Role).filter(Role.name.in_(role_names)).all()
    }

    for role_name in role_names:
        if role_name not in existing_roles:
            new_role = Role(name=role_name, description=f"{role_name.title()} role")
            db.add(new_role)
            db.flush()
            existing_roles[role_name] = new_role

    db.commit()
    return existing_roles


class AuthService:
    """Authentication service."""
    
    @staticmethod
    def register_user(db: Session, user_data: UserCreate) -> User:
        """Register a new user."""
        ensure_default_roles(db)

        # Check if user already exists
        existing_user = db.query(User).filter(
            (User.username == user_data.username) | (User.email == user_data.email)
        ).first()
        
        if existing_user:
            raise ValidationException(
                f"User with username or email already exists",
                status_code=400
            )
        
        # Create new user
        user = User(
            username=user_data.username,
            email=user_data.email,
            hashed_password=hash_password(user_data.password),
            first_name=user_data.first_name,
            last_name=user_data.last_name,
        )
        
        # Assign default "user" role
        default_role = db.query(Role).filter(Role.name == "user").first()
        if default_role is None:
            default_role = ensure_default_roles(db)["user"]
        user.roles.append(default_role)
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        return user
    
    @staticmethod
    def authenticate_user(db: Session, login_data: UserLogin) -> User:
        """Authenticate a user by username and password."""
        user = db.query(User).filter(User.username == login_data.username).first()
        
        if not user or not verify_password(login_data.password, user.hashed_password):
            raise UnauthorizedException("Invalid username or password")
        
        if not user.is_active:
            raise UnauthorizedException("User account is inactive")
        
        # Update last login
        user.last_login = datetime.utcnow()
        db.commit()
        
        return user
    
    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> User:
        """Get user by ID."""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise NotFoundError("User", user_id)
        return user
    
    @staticmethod
    def get_user_by_username(db: Session, username: str) -> User:
        """Get user by username."""
        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise NotFoundError("User", username)
        return user


class TokenService:
    """Token service for JWT management."""
    
    @staticmethod
    def create_tokens(user: User) -> TokenResponse:
        """Create access and refresh tokens for a user."""
        token_data = {"sub": str(user.id), "username": user.username}
        
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=get_token_expiry_seconds("access")
        )
    
    @staticmethod
    def refresh_access_token(refresh_token: str) -> str:
        """Create a new access token from a refresh token."""
        from app.core.security import verify_token
        
        try:
            payload = verify_token(refresh_token)
            
            if payload.get("type") != "refresh":
                raise UnauthorizedException("Invalid token type")
            
            user_id = payload.get("sub")
            username = payload.get("username")
            
            if not user_id or not username:
                raise UnauthorizedException("Invalid token payload")
            
            token_data = {"sub": user_id, "username": username}
            access_token = create_access_token(token_data)
            
            return access_token
        except Exception as e:
            raise UnauthorizedException(f"Token refresh failed: {str(e)}")
