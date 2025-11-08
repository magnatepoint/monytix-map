from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional
import httpx

router = APIRouter()
security = HTTPBearer(auto_error=False)


class UserAuth(BaseModel):
    user_id: str
    email: str
    access_token: str


class UserDep(BaseModel):
    user_id: str
    email: str


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> UserDep:
    """Validate user with Supabase"""
    from config import settings
    
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = credentials.credentials
    
    if not settings.supabase_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase API key not configured"
        )
    
    # Validate with Supabase - use apikey header (anon key) required by Supabase
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "apikey": settings.supabase_key,
                "Content-Type": "application/json"
            }
            response = await client.get(
                f"{settings.supabase_url}/auth/v1/user",
                headers=headers
            )
            
            if response.status_code != 200:
                error_detail = f"Invalid authentication credentials: {response.status_code}"
                try:
                    error_body = response.json()
                    error_detail = error_body.get("message") or error_body.get("error_description") or error_detail
                    print(f"Supabase auth error: {error_detail}")
                except:
                    error_detail = f"Supabase returned {response.status_code}: {response.text[:100]}"
                    print(f"Supabase auth error (raw): {error_detail}")
                    
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=error_detail,
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            user_data = response.json()
            user_id = user_data.get("id") or user_data.get("sub")
            email = user_data.get("email")
            
            if not user_id or not email:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid user data from Supabase"
                )
            
            return UserDep(user_id=str(user_id), email=str(email))
    except HTTPException:
        raise
    except httpx.RequestError as e:
        print(f"Supabase connection error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to connect to Supabase: {str(e)}"
        )


@router.get("/verify")
async def verify_token(current_user: UserDep = Depends(get_current_user)):
    """Verify Supabase JWT token"""
    return {"valid": True, "user": current_user}


@router.get("/google")
async def google_auth():
    """Initiate Google OAuth"""
    from config import settings
    
    # This should redirect to Google OAuth URL
    redirect_uri = settings.gmail_redirect_uri
    client_id = settings.gmail_client_id
    
    # In production, this should redirect the browser
    return {
        "message": "Redirect to Google OAuth",
        "url": f"https://accounts.google.com/o/oauth2/auth?client_id={client_id}&redirect_uri={redirect_uri}&scope=https://www.googleapis.com/auth/gmail.readonly&response_type=code"
    }
