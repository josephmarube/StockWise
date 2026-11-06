"""Deployment settings: hosted-MySQL URLs, TLS, production secret check, serving the built frontend."""
import datetime as dt
import importlib
import secrets
import ssl

import pytest
from fastapi.testclient import TestClient

from app import config
from app.config import Settings, normalise_database_url

# Built at runtime so no credential-looking string is stored in the repository.
FAKE_PW = secrets.token_hex(6)
FAKE_HOST = "db.example.test"  # reserved test domain, never resolves


def provider_uri(query: str = "ssl-mode=REQUIRED") -> str:
    return f"mysql://avnadmin:{FAKE_PW}@{FAKE_HOST}:12345/defaultdb?{query}"


class TestDatabaseUrl:
    def test_aiven_uri_accepted_as_is(self):
        url, tls = normalise_database_url(provider_uri())
        assert url == f"mysql+pymysql://avnadmin:{FAKE_PW}@{FAKE_HOST}:12345/defaultdb?charset=utf8mb4"
        assert tls is True

    def test_local_url_unchanged_apart_from_charset(self):
        url, tls = normalise_database_url(f"mysql+pymysql://u:{FAKE_PW}@127.0.0.1/stockwise")
        assert url.endswith("/stockwise?charset=utf8mb4") and tls is False

    def test_ssl_mode_disabled_means_no_tls(self):
        assert normalise_database_url(provider_uri("ssl-mode=DISABLED"))[1] is False

    def test_non_mysql_urls_untouched(self):
        assert normalise_database_url("sqlite://") == ("sqlite://", False)


class TestTls:
    def _settings(self, monkeypatch, **env):
        for k in ("DATABASE_CA_CERT", "DATABASE_SSL_CA", "DATABASE_SSL", "ENVIRONMENT"):
            monkeypatch.delenv(k, raising=False)
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        return Settings()

    def test_no_tls_for_plain_local_url(self, monkeypatch):
        s = self._settings(monkeypatch, DATABASE_URL=f"mysql+pymysql://u:{FAKE_PW}@127.0.0.1/db")
        assert s.db_connect_args() == {}

    def test_tls_without_ca_encrypts_but_warns(self, monkeypatch, caplog):
        s = self._settings(monkeypatch, DATABASE_URL=provider_uri())
        ctx = s.db_connect_args()["ssl"]
        assert isinstance(ctx, ssl.SSLContext) and ctx.verify_mode == ssl.CERT_NONE
        assert "not verified" in caplog.text

    def test_ca_cert_text_enables_verification(self, monkeypatch):
        # Pasted into an env var, newlines often arrive as literal "\\n".
        s = self._settings(monkeypatch, DATABASE_URL=provider_uri(),
                           DATABASE_CA_CERT=_SELF_SIGNED_CA.replace("\n", "\\n"))
        ctx = s.db_connect_args()["ssl"]
        assert ctx.verify_mode == ssl.CERT_REQUIRED and ctx.check_hostname is True

    def test_ca_path_enables_verification(self, monkeypatch, tmp_path):
        ca = tmp_path / "ca.pem"
        ca.write_text(_SELF_SIGNED_CA)
        s = self._settings(monkeypatch, DATABASE_URL=provider_uri(),
                           DATABASE_SSL_CA=str(ca))
        ctx = s.db_connect_args()["ssl"]
        assert ctx.verify_mode == ssl.CERT_REQUIRED and ctx.check_hostname is True

    def test_production_refuses_default_secret(self, monkeypatch):
        with pytest.raises(RuntimeError, match="JWT_SECRET"):
            self._settings(monkeypatch, ENVIRONMENT="production", JWT_SECRET="x" * 10)


@pytest.fixture()
def prod_app(tmp_path, monkeypatch):
    """The app as the Docker image runs it: STATIC_DIR set, migrations disabled at startup."""
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><title>StockWise</title><div id=root></div>")
    (tmp_path / "assets" / "app-1a2b.js").write_text("console.log('hi')")
    (tmp_path / "favicon.svg").write_text("<svg/>")
    monkeypatch.setenv("STATIC_DIR", str(tmp_path))
    monkeypatch.setenv("MIGRATE_ON_STARTUP", "false")
    config.get_settings.cache_clear()
    import app.main as main_mod

    fresh = importlib.reload(main_mod)
    with TestClient(fresh.app) as c:
        yield c
    monkeypatch.delenv("STATIC_DIR")
    config.get_settings.cache_clear()
    importlib.reload(main_mod)


class TestServesFrontend:
    def test_root_and_client_routes_return_app_shell(self, prod_app):
        for path in ("/", "/products/12", "/record?type=IN", "/reports"):
            r = prod_app.get(path)
            assert r.status_code == 200 and "<div id=root>" in r.text, path
            assert r.headers["cache-control"] == "no-cache"

    def test_assets_are_cached_long(self, prod_app):
        r = prod_app.get("/assets/app-1a2b.js")
        assert r.status_code == 200 and "immutable" in r.headers["cache-control"]
        assert r.headers["x-content-type-options"] == "nosniff"

    def test_root_files_served(self, prod_app):
        assert prod_app.get("/favicon.svg").text == "<svg/>"

    def test_unknown_api_path_is_json_404_not_html(self, prod_app):
        r = prod_app.get("/api/does-not-exist")
        assert r.status_code == 404 and r.headers["content-type"].startswith("application/json")

    def test_api_still_works(self, prod_app):
        assert prod_app.get("/api/auth/me").status_code == 401

    def test_cannot_escape_static_dir(self, prod_app):
        r = prod_app.get("/..%2f..%2fetc/passwd")
        assert "root:" not in r.text


def _make_test_ca() -> str:
    """A throwaway self-signed CA certificate (PEM), generated per test run."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "StockWise Test CA")])
    now = dt.datetime.now(dt.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=1))
        .not_valid_after(now + dt.timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    return cert.public_bytes(serialization.Encoding.PEM).decode()


_SELF_SIGNED_CA = _make_test_ca()
