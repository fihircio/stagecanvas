import os
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from .models import User, UserInDB, TokenData, UserRole

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------
SECRET_KEY = os.environ.get("STAGE_CANVAS_SECRET_KEY", "b3984e7a8e8f8c8d8b8a898887868584838281807f7e7d7c")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

# ---------------------------------------------------------------------------
# IN-MEMORY USER STORE (For initial implementation)
# ---------------------------------------------------------------------------
FAKE_USERS_DB = {
    "admin": {
        "user_id": "u-admin",
        "username": "admin",
        "full_name": "System Administrator",
        "hashed_password": pwd_context.hash("admin123"),
        "role": "admin",
        "disabled": False,
    },
    "designer": {
        "user_id": "u-designer",
        "username": "designer",
        "full_name": "Show Designer",
        "hashed_password": pwd_context.hash("design123"),
        "role": "designer",
        "disabled": False,
    },
    "operator": {
        "user_id": "u-operator",
        "username": "operator",
        "full_name": "Board Operator",
        "hashed_password": pwd_context.hash("op123"),
        "role": "operator",
        "disabled": False,
    },
    "view": {
        "user_id": "u-viewer",
        "username": "view",
        "full_name": "Client Viewer",
        "hashed_password": pwd_context.hash("view123"),
        "role": "viewer",
        "disabled": False,
    }
}

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# ---------------------------------------------------------------------------
# DEPENDENCIES
# ---------------------------------------------------------------------------

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username, role=role)
    except JWTError:
        raise credentials_exception
    
    user_dict = FAKE_USERS_DB.get(token_data.username)
    if user_dict is None:
        raise credentials_exception
    
    return User(**user_dict)

async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

def require_role(roles: List[UserRole]):
    """
    Dependency that ensures the current user has one of the required roles.
    """
    async def role_dependency(current_user: User = Depends(get_current_active_user)):
        # Role hierarchy: admin (0) > designer (1) > operator (2) > viewer (3)
        role_values = {"admin": 0, "designer": 1, "operator": 2, "viewer": 3}
        
        user_role_val = role_values.get(current_user.role, 99)
        
        # Check if user has ANY of the required roles OR higher status
        # Designer also has operator and viewer permissions.
        # Admin has all permissions.
        
        # Determine the "min" requirement (highest value in role_values)
        min_required_val = min(role_values[r] for r in roles)
        
        if user_role_val > min_required_val:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Resource requires {roles} permissions."
            )
        return current_user
    
    return role_dependency
