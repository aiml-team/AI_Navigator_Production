"""
services/saml_service.py
━━━━━━━━━━━━━━━━━━━━━━━━
Wraps python3-saml to provide SP settings for Okta SSO.
"""

# ──────────────────────────────────────────────────────────────────────────
#  OKTA SSO ENABLED — module active. See routes/saml_routes.py for endpoints.
# ──────────────────────────────────────────────────────────────────────────

import os
from pathlib import Path


def _strip_cert(text: str) -> str:
    return (
        text.replace("-----BEGIN CERTIFICATE-----", "")
            .replace("-----END CERTIFICATE-----", "")
            .replace("\r", "")
            .replace("\n", "")
            .strip()
    )


def _strip_key(text: str) -> str:
    return (
        text.replace("-----BEGIN PRIVATE KEY-----", "")
            .replace("-----END PRIVATE KEY-----", "")
            .replace("-----BEGIN RSA PRIVATE KEY-----", "")
            .replace("-----END RSA PRIVATE KEY-----", "")
            .replace("\r", "")
            .replace("\n", "")
            .strip()
    )


def _read_cert(path: str) -> str:
    return _strip_cert(Path(path).read_text())


def _read_key(path: str) -> str:
    return _strip_key(Path(path).read_text())


def _load_pem(env_var: str, file_path: str, is_key: bool) -> str:
    """
    Load a PEM-formatted cert or key.

    Priority:
      1) Environment variable `env_var` — used in Azure App Service, where
         the private key is stored in App Settings so it never has to be
         committed to git. The value can either include the -----BEGIN/END-----
         armor or be the base64 body only; both are normalized to the
         armor-stripped form python3-saml expects.
      2) File at `file_path` on disk — used for local development so the
         existing saml/ folder keeps working with no changes.

    Raises FileNotFoundError with a clearer message when neither source
    is available (previously we got a bare Path().read_text() error).
    """
    raw = os.getenv(env_var)
    if raw:
        return _strip_key(raw) if is_key else _strip_cert(raw)

    p = Path(file_path)
    if p.exists():
        return _read_key(file_path) if is_key else _read_cert(file_path)

    raise FileNotFoundError(
        f"SAML material missing: set env var {env_var} or provide {file_path}"
    )


def get_saml_settings() -> dict:
    base_url = os.getenv(
        "APP_BASE_URL",
        "https://ai-navigator-ashpbzhbcmgeerbt.northeurope-01.azurewebsites.net"
    ).rstrip("/")

    # SP cert / key and IdP cert can come from env vars (Azure App Settings)
    # or from local files in saml/. See _load_pem() docstring above.
    sp_cert  = _load_pem("SAML_SP_CERT", "saml/sp.crt", is_key=False)
    sp_key   = _load_pem("SAML_SP_KEY",  "saml/sp.key", is_key=True)
    idp_cert = _load_pem("SAML_IDP_CERT", "saml/idp.crt", is_key=False)

    return {
        "strict": True,
        "debug": False,
        # ── Security settings ──────────────────────────────────────────
        # wantAttributeStatement=False: allow SAML responses that carry only
        # the NameID (email) and no <AttributeStatement> block. Okta's prod
        # app currently does not send attribute statements — the user email
        # arrives as NameID, which is all we need. Without this flag
        # python3-saml rejects the response with:
        #     "There is no AttributeStatement on the Response"
        # Other checks (signature, audience, destination, timing) remain on.
        "security": {
            "wantAttributeStatement": False,
        },
        "sp": {
            "entityId": f"{base_url}/saml/metadata",
            "assertionConsumerService": {
                "url": f"{base_url}/saml/acs",
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
            },
            "singleLogoutService": {
                "url": f"{base_url}/saml/logout",
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
            },
            "NameIDFormat": "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
            "x509cert": sp_cert,
            "privateKey": sp_key,
        },
        "idp": {
            # ── Okta PRODUCTION app (onentt_ainavigatorprod_1) ──
            # Registered in Okta with ACS = https://ai-navigator-ashpbzhbcmgeerbt.northeurope-01.azurewebsites.net/saml/acs
            # Confirmed by Global IT team.
            "entityId": "http://www.okta.com/exky6wzhy4PfkwSKt417",
            "singleSignOnService": {
                "url": "https://onentt.okta.com/app/onentt_ainavigatorprod_1/exky6wzhy4PfkwSKt417/sso/saml",
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
            },
            "singleLogoutService": {
                "url": "https://onentt.okta.com/app/onentt_ainavigatorprod_1/exky6wzhy4PfkwSKt417/sso/saml",
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
            },
            "x509cert": idp_cert,
        },
    }
