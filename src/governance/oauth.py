"""OAuth 2.0 + OIDC - Integrate Cognito/Keycloak

Self-Explanatory: Auth flows for secure login.
Why: Replace demo auth with standard OIDC.
How: Authlib for FastAPI; validate JWT in Depends.
Config: Set CLIENT_ID, SECRET, ISSUER in env.
"""
from authlib.integrations.starlette_client import OAuth
from fastapi import Depends, HTTPException
from jose import jwt, JWTError
import structlog
from starlette.config import Config
from starlette.requests import Request

config = Config('.env')  # Prod: Load env
OAUTH_CLIENT_ID = config('OAUTH_CLIENT_ID')
OAUTH_CLIENT_SECRET = config('OAUTH_CLIENT_SECRET')
OAUTH_ISSUER = config('OAUTH_ISSUER', default='https://cognito-idp.ap-south-1.amazonaws.com/ap-south-1_XXXX')  # Mumbai region

oauth = OAuth(config)
oauth.register(
    name='cognito',
    client_id=OAUTH_CLIENT_ID,
    client_secret=OAUTH_CLIENT_SECRET,
    authorize_url=f"{OAUTH_ISSUER}/authorize",
    access_token_url=f"{OAUTH_ISSUER}/token",
    jwks_uri=f"{OAUTH_ISSUER}/.well-known/jwks.json"
)

logger = structlog.get_logger()

async def get_current_user(request: Request) -> dict:
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if not token:
        raise HTTPException(401, "No token")
    
    try:
        jwks = await oauth.cognito.load_server_metadata()  # Or cache JWKS
        claims = jwt.decode(token, jwks, algorithms=['RS256'], audience=OAUTH_CLIENT_ID, issuer=OAUTH_ISSUER)
        logger.info("User validated", user_id=claims['sub'])
        return {"user_id": claims['sub'], "role": claims.get('role', 'viewer')}  # Custom claim for role
    except JWTError as e:
        logger.error("JWT error", error=str(e))
        raise HTTPException(401, "Invalid token")

# Login endpoint (add to router)
from fastapi import APIRouter
auth_router = APIRouter()

@auth_router.get("/login")
async def login(request: Request):
    redirect_uri = request.url_for('auth_callback')  # Define callback
    return await oauth.cognito.authorize_redirect(request, redirect_uri)

@auth_router.get("/auth/callback")
async def auth_callback(request: Request):
    token = await oauth.cognito.authorize_access_token(request)
    # Store token in session/cookie
    request.session['token'] = token['id_token']
    return {"message": "Logged in"}
