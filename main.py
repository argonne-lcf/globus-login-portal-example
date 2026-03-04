import os
import secrets
from urllib.parse import urlencode
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

# Load .env file variables
from dotenv import load_dotenv
load_dotenv()

# Helper function to combine the base scopes with the requested scopes
def _scopes_to_request() -> str:
    extra = os.getenv("REQUESTED_SCOPES") or os.getenv("GLOBUS_SCOPES") or ""
    return f"openid profile email {extra}".strip()

# Globus configuration from the .env file
GLOBUS_CONFIG = {
    "client_id": (os.getenv("GLOBUS_CLIENT_ID") or "").strip() or None,
    "client_secret": (os.getenv("GLOBUS_CLIENT_SECRET") or "").strip() or None,
    "redirect_uri": (os.getenv("GLOBUS_REDIRECT_URI") or "").strip() or None,
    "scopes": _scopes_to_request(),
    "policy": (os.getenv("GLOBUS_POLICY") or "").strip() or None,
}

# Define Globus Auth URLs
AUTH_BASE = "https://auth.globus.org/v2/oauth2"
AUTHORIZE_URL = f"{AUTH_BASE}/authorize"
TOKEN_URL = f"{AUTH_BASE}/token"
USERINFO_URL = f"{AUTH_BASE}/userinfo"

# Start FastAPI application
app = FastAPI()
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET", "change-me"),
    https_only=False,
    same_site="lax",
)

# Load Jinja2 templates to render the web page
templates = Jinja2Templates(directory="templates")

# Storage for the main Globus token
TOKEN_STORE: dict[str, dict] = {}


# Main web page with login/logout buttons
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):

    # Get the main Globus token from the session
    token_id = request.session.get("token_id")
    token = TOKEN_STORE.get(token_id) if token_id else None
    
    # Generate the Globus logout URL
    client_id = GLOBUS_CONFIG.get("client_id")
    if client_id:
        globus_logout_url = f"https://auth.globus.org/v2/web/logout?{urlencode({'client_id': client_id})}"
    else:
        globus_logout_url = ""

    # Render the web page with the login/logout buttons
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "logged_in": bool(token and token.get("access_token")),
            "globus_logout_url": globus_logout_url,
        },
    )


# Login flow
@app.get("/login")
async def login(request: Request):

    # OAuth2 state to protect the login flow
    state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state

    # Prepare the login flow parameters
    redirect_uri = GLOBUS_CONFIG.get("redirect_uri") or str(request.url_for("auth_callback"))
    params = {
        "client_id": GLOBUS_CONFIG["client_id"],
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": GLOBUS_CONFIG["scopes"],
        "state": state,
    }

    # Add Globus policy in the auth flow
    if GLOBUS_CONFIG["policy"]:
        params["session_required_policies"] = GLOBUS_CONFIG["policy"]

    # Redirect to Globus Auth authorize endpoint
    return RedirectResponse(f"{AUTHORIZE_URL}?{urlencode(params)}", status_code=302)


# Callback when the auth flow returns to this API application
@app.get("/auth/callback", name="auth_callback")
async def auth_callback(request: Request, code: str | None = None, state: str | None = None):
    
    # Validate the code and state
    if not code or not state:
        return HTMLResponse("Missing code/state", status_code=400)
    expected_state = request.session.get("oauth_state")
    if not expected_state or state != expected_state:
        return HTMLResponse("Invalid state", status_code=400)

    # Exchange the code for an access token
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": GLOBUS_CONFIG.get("redirect_uri") or str(request.url_for("auth_callback")),
            },
            auth=(GLOBUS_CONFIG["client_id"], GLOBUS_CONFIG["client_secret"]),
        )
        if resp.status_code >= 400:
            return HTMLResponse(resp.text, status_code=resp.status_code)

    # Store the main Globus token in the session
    token_data = resp.json()
    token_data.pop("id_token", None)
    token_id = secrets.token_urlsafe(24)
    TOKEN_STORE[token_id] = token_data
    request.session["token_id"] = token_id

    # Clear the OAuth state
    request.session.pop("oauth_state", None)
    
    # Redirect to the main page
    return RedirectResponse("/", status_code=302)


# Logout from Globus (the HTML code includes an important redirect to the Globus logout page)
@app.get("/logout")
async def logout(request: Request):

    # Clear the session
    token_id = request.session.pop("token_id", None)
    if token_id:
        TOKEN_STORE.pop(token_id, None)
    request.session.pop("oauth_state", None)

    # Redirect to the main page
    return RedirectResponse("/", status_code=302)


# View the main Globus token JSON stored in the session
@app.get("/token")
async def token(request: Request):

    token_id = request.session.get("token_id")
    token_data = TOKEN_STORE.get(token_id) if token_id else None
    if not token_data or not token_data.get("access_token"):
        return JSONResponse({"error": "not_logged_in"}, status_code=401)
    
    # Return the main token JSON data
    return JSONResponse(token_data, status_code=200)


# User details using the access token
@app.get("/whoami")
async def whoami(request: Request):

    token_id = request.session.get("token_id")
    token_data = TOKEN_STORE.get(token_id) if token_id else None
    if not token_data:
        return JSONResponse({"error": "not_logged_in"}, status_code=401)

    # Get access token from main token
    access_token = token_data.get("access_token")
    if not access_token:
        return JSONResponse({"error": "missing_access_token", "token_keys": sorted(token_data.keys())}, status_code=500)

    # Call Globus /userinfo endpoint with the access token
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
        return JSONResponse(resp.json(), status_code=resp.status_code)


