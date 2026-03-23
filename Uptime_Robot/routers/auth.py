import html
import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

try:
    from .. import auth_module
    from ..database import get_db_connection
    from ..dependencies import get_current_user, require_admin
    from ..state import DB_PATH
except ImportError:
    import auth_module
    from database import get_db_connection
    from dependencies import get_current_user, require_admin
    from state import DB_PATH

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter()

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = None, user: dict = Depends(get_current_user)):
    if user:
        return RedirectResponse(url="/", status_code=302)

    error_html = f'<div class="error">{error}</div>' if error else ""
    warning_html = '<div class="warning">WARNING: Change password after first login!</div>'
    
    return templates.TemplateResponse(request, "login.html", {
        "request": request,
        "error_message": error_html,
        "warning_message": warning_html
    })

@router.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    async with get_db_connection() as conn:
        async with conn.execute(
            "SELECT id, password_hash, must_change_password FROM users WHERE username = ?",
            (username,),
        ) as c:
            user = await c.fetchone()

    if not user or not auth_module.verify_password(password, user["password_hash"]):
        return RedirectResponse(url="/login?error=Invalid username or password", status_code=302)

    session_id = await auth_module.create_session(user["id"], DB_PATH)
    response = RedirectResponse(
        url="/change-password" if user["must_change_password"] else "/", status_code=302
    )
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        max_age=604800,
        secure=request.url.scheme == "https",
        samesite="lax",
    )
    return response

@router.get("/logout")
async def logout(request: Request):
    session_id = request.cookies.get("session_id")
    if session_id:
        await auth_module.delete_session(session_id, DB_PATH)
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("session_id")
    return response

@router.get("/change-password", response_class=HTMLResponse)
async def change_password_page(
    request: Request, error: str = None, user: dict = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    error_html = f'<div class="error">{error}</div>' if error else ""
    return templates.TemplateResponse(request, "change_password.html", {
        "request": request, 
        "error_message": error_html
    })

@router.post("/change-password")
async def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    user: dict = Depends(get_current_user),
):
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    if new_password != confirm_password:
        return RedirectResponse(
            url="/change-password?error=Passwords do not match", status_code=302
        )

    if len(new_password) < 6:
        return RedirectResponse(url="/change-password?error=Minimum 6 characters", status_code=302)

    async with get_db_connection() as conn:
        async with conn.execute("SELECT password_hash FROM users WHERE id = ?", (user["user_id"],)) as c:
            user_data = await c.fetchone()

    if not user_data or not auth_module.verify_password(
        current_password, user_data["password_hash"]
    ):
        return RedirectResponse(
            url="/change-password?error=Invalid current password", status_code=302
        )

    if await auth_module.change_password(user["user_id"], new_password, DB_PATH):
        return RedirectResponse(url="/?message=Password updated", status_code=302)
    else:
        return RedirectResponse(url="/change-password?error=Update failed", status_code=302)

@router.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(
    request: Request,
    error: str = None,
    success: str = None,
    user: dict = Depends(get_current_user),
):
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    if not auth_module.is_admin(user):
        raise HTTPException(status_code=403, detail="Admin access required")

    error_html = f'<div class="error">{error}</div>' if error else ""
    success_html = f'<div class="success">{success}</div>' if success else ""
    
    return templates.TemplateResponse(request, "forgot_password.html", {
        "request": request,
        "error_message": error_html,
        "success_message": success_html
    })

@router.post("/forgot-password")
async def forgot_password_action(
    request: Request, username: str = Form(...), current_user: dict = Depends(require_admin)
):
    async with get_db_connection() as conn:
        async with conn.execute("SELECT id FROM users WHERE username = ?", (username,)) as c:
            user = await c.fetchone()
            
        if not user:
            error_html = '<div class="error">User not found</div>'
            return templates.TemplateResponse(request, "forgot_password.html", {
                "request": request,
                "error_message": error_html,
                "success_message": ""
            })
        temporary_password = secrets.token_urlsafe(12)
        await auth_module.change_password(user["id"], temporary_password, DB_PATH)
        await conn.execute("UPDATE users SET must_change_password = 1 WHERE id = ?", (user["id"],))
        await conn.commit()

    success_html = (
        '<div class="success">'
        f'Temporary password for {html.escape(username)}: '
        f'<code>{html.escape(temporary_password)}</code>'
        "</div>"
    )
    return templates.TemplateResponse(request, "forgot_password.html", {
        "request": request,
        "error_message": "",
        "success_message": success_html
    })
