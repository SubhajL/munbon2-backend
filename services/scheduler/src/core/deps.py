from typing import AsyncGenerator, Dict, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
import jwt

from .database import SessionLocal
from .redis import RedisClient, get_redis_client
from .config import settings
from .logger import get_logger

logger = get_logger(__name__)

# Security scheme
security = HTTPBearer()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Database dependency"""
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_redis() -> RedisClient:
    """Redis dependency"""
    return await get_redis_client()


async def verify_token(token: str) -> Optional[Dict]:
    """Verify JWT token"""
    try:
        # In production, verify against auth service
        # For now, decode with secret
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=["HS256"]
        )
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    redis: RedisClient = Depends(get_redis)
) -> Dict:
    """Get current authenticated user"""
    
    token = credentials.credentials
    
    # Check token blacklist
    if await redis.exists(f"token:blacklist:{token}"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked"
        )
    
    # Verify token
    user_data = await verify_token(token)
    
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    # In production, might fetch full user details from auth service
    return user_data


async def get_current_active_user(
    current_user: Dict = Depends(get_current_user)
) -> Dict:
    """Get current active user"""
    
    if not current_user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    
    return current_user


async def verify_websocket_token(
    token: str,
    redis: RedisClient
) -> Optional[Dict]:
    """Verify token for WebSocket connections"""
    
    # Check if token is blacklisted
    if await redis.exists(f"token:blacklist:{token}"):
        return None
    
    # Verify token
    return await verify_token(token)


class RoleChecker:
    """Dependency for role-based access control"""
    
    def __init__(self, allowed_roles: list[str]):
        self.allowed_roles = allowed_roles
    
    def __call__(self, user: Dict = Depends(get_current_user)) -> Dict:
        user_roles = user.get("roles", [])
        
        if not any(role in self.allowed_roles for role in user_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        
        return user


# Convenience role checkers
require_admin = RoleChecker(["admin"])
require_operator = RoleChecker(["admin", "operator"])
require_supervisor = RoleChecker(["admin", "supervisor"])
require_field_team = RoleChecker(["admin", "supervisor", "field_team"])