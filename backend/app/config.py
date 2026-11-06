"""Application settings, loaded from environment variables (see .env.example)."""
import logging
import os
import secrets
import ssl
import tempfile
from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger("stockwise")

_TLS_MODES = {"required", "verify_ca", "verify_identity", "verify-ca", "verify-full"}


def normalise_database_url(raw: str) -> tuple[str, bool]:
    """Accept a hosting provider's URI as-is, e.g. Aiven's
    'mysql://<user>:<password>@<host>:<port>/defaultdb?ssl-mode=REQUIRED'.

    Returns (SQLAlchemy URL for PyMySQL, whether TLS is required).
    """
    raw = raw.strip()
    parts = urlsplit(raw)
    if not parts.scheme.startswith(("mysql", "mariadb")):
        return raw, False  # e.g. sqlite:// in tests: leave untouched
    scheme = parts.scheme
    if scheme in ("mysql", "mariadb"):
        scheme = "mysql+pymysql"
    query = []
    tls = False
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if key.lower().replace("_", "-") in ("ssl-mode", "sslmode"):
            tls = value.lower() in _TLS_MODES
            continue  # PyMySQL does not understand ssl-mode; TLS is set via connect_args
        query.append((key, value))
    if scheme.startswith("mysql") and not any(k == "charset" for k, _ in query):
        query.append(("charset", "utf8mb4"))
    return urlunsplit((scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)), tls


class Settings:
    def __init__(self) -> None:
        self.environment: str = os.getenv("ENVIRONMENT", "development").lower()
        raw_url = os.getenv("DATABASE_URL", "").strip()
        if not raw_url:
            raise RuntimeError(
                "Set DATABASE_URL (see backend/.env.example), e.g. "
                "mysql+pymysql://<user>:<password>@127.0.0.1:3306/stockwise"
            )
        self.database_url, tls_in_url = normalise_database_url(raw_url)
        # TLS to the database: required by Aiven and most hosted MySQL.
        # DATABASE_CA_CERT holds the CA certificate text (PEM); DATABASE_SSL_CA is a path to it.
        self.db_ca_cert: str | None = os.getenv("DATABASE_CA_CERT") or None
        self.db_ssl_ca: str | None = os.getenv("DATABASE_SSL_CA") or None
        self.db_tls: bool = tls_in_url or bool(self.db_ca_cert or self.db_ssl_ca) or _truthy(
            os.getenv("DATABASE_SSL")
        )
        self.db_verify_hostname: bool = _truthy(os.getenv("DATABASE_SSL_VERIFY_HOSTNAME", "true"))

        self.jwt_secret: str = os.getenv("JWT_SECRET", "").strip()
        self.jwt_algorithm: str = "HS256"
        self.jwt_expire_minutes: int = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))
        self.cors_origins: list[str] = [
            o.strip()
            for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
            if o.strip()
        ]
        # Business-local timezone used for report date ranges and CSV timestamps.
        self.business_timezone: str = os.getenv("BUSINESS_TIMEZONE", "Africa/Nairobi")
        self.bootstrap_admin_email: str | None = os.getenv("BOOTSTRAP_ADMIN_EMAIL")
        self.bootstrap_admin_password: str | None = os.getenv("BOOTSTRAP_ADMIN_PASSWORD")
        self.bootstrap_business_name: str = os.getenv("BOOTSTRAP_BUSINESS_NAME") or "My Business"
        # Built React app to serve from the API (production image). Unset in development.
        self.static_dir: str | None = os.getenv("STATIC_DIR") or None
        # Production image runs migrations once before starting workers.
        self.migrate_on_startup: bool = _truthy(os.getenv("MIGRATE_ON_STARTUP", "true"))

        if len(self.jwt_secret) < 32:
            if self.environment == "production":
                raise RuntimeError("Set JWT_SECRET to a random string of at least 32 characters.")
            # Development only: a throwaway secret, so nothing secret is ever written in code.
            # Logins end when the server restarts; set JWT_SECRET in .env to keep them.
            self.jwt_secret = secrets.token_urlsafe(48)
            log.warning("JWT_SECRET not set; using a random one for this run (development only).")

    def db_connect_args(self) -> dict:
        if not self.database_url.startswith("mysql") or not self.db_tls:
            return {}
        ca_path = self.db_ssl_ca
        if self.db_ca_cert and not ca_path:
            ca_path = _write_temp_pem(self.db_ca_cert)
        if ca_path:
            ctx = ssl.create_default_context(cafile=ca_path)
            ctx.check_hostname = self.db_verify_hostname
            # Python 3.13+ adds strict X.509 checks that reject some database CAs
            # (missing optional extensions). The chain is still fully verified.
            ctx.verify_flags &= ~getattr(ssl, "VERIFY_X509_STRICT", 0)
        else:
            log.warning(
                "Database connection is encrypted but the server certificate is not verified. "
                "Set DATABASE_CA_CERT to your provider's CA certificate."
            )
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        return {"ssl": ctx}


def _truthy(v: str | None) -> bool:
    return (v or "").strip().lower() in ("1", "true", "yes", "on")


def _write_temp_pem(pem: str) -> str:
    # Env vars often lose real newlines; accept "\n" escapes too.
    text = pem.replace("\\n", "\n").strip() + "\n"
    f = tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False)
    f.write(text)
    f.close()
    return f.name


@lru_cache
def get_settings() -> Settings:
    return Settings()
