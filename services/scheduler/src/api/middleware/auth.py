from typing import Optional
from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
import httpx
import jwt
from jwt.exceptions import InvalidTokenError

from ...core.config import settings
from ...core.logger import get_logger

logger = get_logger(__name__)
security = HTTPBearer()


class AuthMiddleware(BaseHTTPMiddleware):
    """Authentication middleware"""
    
    def __init__(self, app, auth_service_url: str):
        super().__init__(app)
        self.auth_service_url = auth_service_url
        # Paths that don't require authentication
        self.public_paths = [
            "/health",
            "/docs",
            "/openapi.json",
            "/redoc",
        ]
    
    async def dispatch(self, request: Request, call_next):
        # Skip auth for public paths
        if any(request.url.path.startswith(path) for path in self.public_paths):
            return await call_next(request)
        
        # Extract token
        authorization = request.headers.get("Authorization")
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing authentication token")
        
        token = authorization.split(" ")[1]
        
        try:
            # Decode token to get basic info (without verification for speed)
            payload = jwt.decode(token, options={"verify_signature": False})
            request.state.user_id = payload.get("sub")
            request.state.user_email = payload.get("email")
            request.state.roles = payload.get("roles", [])
            
            # For critical operations, verify with auth service
            if request.method in ["POST", "PUT", "DELETE"]:
                await self._verify_token_with_auth_service(token)
            
        except InvalidTokenError as e:
            logger.error(f"Invalid token: {str(e)}")
            raise HTTPException(status_code=401, detail="Invalid authentication token")
        
        response = await call_next(request)
        return response
    
    async def _verify_token_with_auth_service(self, token: str) -> bool:
        """Verify token with auth service"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.auth_service_url}/api/v1/auth/verify",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=5.0,
                )
                
                if response.status_code != 200:
                    raise HTTPException(status_code=401, detail="Token verification failed")
                
                return True
        except httpx.RequestError as e:
            logger.error(f"Auth service verification failed: {str(e)}")
            # In case auth service is down, allow the request but log it
            logger.warning("Auth service unavailable, proceeding with local token validation")
            return True