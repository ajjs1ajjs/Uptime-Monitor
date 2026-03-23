from fastapi import Depends, HTTPException, Request
try:
    from . import auth_module
    from .state import DB_PATH
except ImportError:
    import auth_module
    from state import DB_PATH

async def get_current_user(request: Request):
    session_id = request.cookies.get("session_id")
    user = await auth_module.validate_session(session_id, DB_PATH)
    if not user:
        return None
    return user

def require_admin(user: dict = Depends(get_current_user)):
    """Dependency to require admin role"""
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    if not auth_module.is_admin(user):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

def require_viewer_or_higher(user: dict = Depends(get_current_user)):
    """Dependency to require viewer or admin role (read-only access)"""
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    if not auth_module.is_viewer_or_higher(user):
        raise HTTPException(status_code=403, detail="Viewer or admin access required")
    return user
