import html
import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from .. import auth_module, models
from ..csrf import generate_csrf_token, validate_csrf_token
from ..database import get_db_connection
from ..dependencies import get_client_ip, get_current_user, require_admin
from ..state import DB_PATH

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter()


def _rate_limit_dependency(endpoint: str, max_attempts: int, window_seconds: int):
    """Creates a FastAPI Dependency that rate-limits by client IP using DB."""

    async def limiter(request: Request):
        client_ip = get_client_ip(request)
        ok = await models.check_db_rate_limit(
            endpoint, client_ip, max_attempts, window_seconds, DB_PATH
        )
        if not ok:
            raise HTTPException(
                status_code=429,
                detail="Too many attempts. Try again later.",
            )
        return True

    return limiter


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = None, user: dict = Depends(get_current_user)):
    if user:
        return RedirectResponse(url="/", status_code=302)

    error_html = f'<div class="error">{error}</div>' if error else ""

    return templates.TemplateResponse(
        request,
        "login.html",
        {"request": request, "error_message": error_html},
    )


@router.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    client_ip = get_client_ip(request)
    if not await models.check_db_rate_limit("login", client_ip, 5, 900, DB_PATH):
        return RedirectResponse(
            url="/login?error=Too many login attempts. Try again later.", status_code=429
        )

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
    session_id = request.cookies.get("session_id", "")
    csrf_token = await generate_csrf_token(session_id) if session_id else ""
    return templates.TemplateResponse(
        request,
        "change_password.html",
        {"request": request, "error_message": error_html, "csrf_token": csrf_token},
    )


@router.post("/change-password")
async def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    csrf_token: str = Form(default=""),
    user: dict = Depends(get_current_user),
    _rate_ok: bool = Depends(_rate_limit_dependency("change_password", 3, 900)),
):
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    session_id = request.cookies.get("session_id", "")
    if not await validate_csrf_token(session_id, csrf_token):
        return RedirectResponse(
            url="/change-password?error=Session expired, try again", status_code=302
        )

    if new_password != confirm_password:
        return RedirectResponse(
            url="/change-password?error=Passwords do not match", status_code=302
        )

    is_valid, error_msg = auth_module.validate_password_strength(new_password)
    if not is_valid:
        return RedirectResponse(url=f"/change-password?error={error_msg}", status_code=302)

    async with get_db_connection() as conn:
        async with conn.execute(
            "SELECT password_hash FROM users WHERE id = ?", (user["user_id"],)
        ) as c:
            user_data = await c.fetchone()

    if not user_data or not auth_module.verify_password(
        current_password, user_data["password_hash"]
    ):
        return RedirectResponse(
            url="/change-password?error=Invalid current password", status_code=302
        )

    if await auth_module.change_password(user["user_id"], new_password, DB_PATH):
        # change_password invalidated ALL of this user's sessions (including the
        # current one). Mint a fresh session so the acting user stays logged in.
        new_session_id = await auth_module.create_session(user["user_id"], DB_PATH)
        response = RedirectResponse(url="/?message=Password updated", status_code=302)
        response.set_cookie(
            key="session_id",
            value=new_session_id,
            httponly=True,
            max_age=604800,
            secure=request.url.scheme == "https",
            samesite="lax",
        )
        return response
    else:
        return RedirectResponse(url="/change-password?error=Update failed", status_code=302)


@router.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(
    request: Request,
    error: str = None,
    success: str = None,
    user: dict = Depends(get_current_user),
):
    # Allow access without login — a user who forgot their password
    # cannot log in to reset it. Only admins can reset other users.
    # If not logged in, show the form without user-specific data.
    error_html = f'<div class="error">{error}</div>' if error else ""
    success_html = f'<div class="success">{success}</div>' if success else ""

    session_id = request.cookies.get("session_id", "")
    csrf_token = await generate_csrf_token(session_id) if session_id else ""

    return templates.TemplateResponse(
        request,
        "forgot_password.html",
        {
            "request": request,
            "error_message": error_html,
            "success_message": success_html,
            "csrf_token": csrf_token,
            "is_admin": auth_module.is_admin(user) if user else False,
        },
    )


@router.post("/forgot-password")
async def forgot_password_action(
    request: Request,
    username: str = Form(...),
    csrf_token: str = Form(default=""),
    current_user: dict = Depends(get_current_user),
    _rate_ok: bool = Depends(_rate_limit_dependency("forgot_password", 3, 1800)),
):
    if not current_user or not auth_module.is_admin(current_user):
        return RedirectResponse(url="/login?error=Admin access required", status_code=302)

    session_id = request.cookies.get("session_id", "")
    if not await validate_csrf_token(session_id, csrf_token):
        return RedirectResponse(
            url="/forgot-password?error=Session expired, try again", status_code=302
        )
    fresh_token = await generate_csrf_token(session_id) if session_id else ""

    async with get_db_connection() as conn:
        async with conn.execute("SELECT id FROM users WHERE username = ?", (username,)) as c:
            user = await c.fetchone()

        if not user:
            error_html = '<div class="error">User not found</div>'
            return templates.TemplateResponse(
                request,
                "forgot_password.html",
                {
                    "request": request,
                    "error_message": error_html,
                    "success_message": "",
                    "csrf_token": fresh_token,
                },
            )
        temporary_password = secrets.token_urlsafe(12)
        await auth_module.change_password(user["id"], temporary_password, DB_PATH)
        await conn.execute("UPDATE users SET must_change_password = 1 WHERE id = ?", (user["id"],))
        await conn.commit()

    success_html = (
        '<div class="success">'
        f"Password reset for {html.escape(username)} — user must change on next login. "
        f"Temporary password: <code>{html.escape(temporary_password)}</code> "
        f"<button onclick=\"setTimeout(function(){{ document.getElementById('temp-pw').style.display='none'; }},60000)\" class=\"text-xs text-slate-400\">(hide in 60s)</button>"
        "</div>"
    )
    response = templates.TemplateResponse(
        request,
        "forgot_password.html",
        {
            "request": request,
            "error_message": "",
            "success_message": success_html,
            "csrf_token": fresh_token,
        },
    )
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return response
