"""Deployment settings: hosted-MySQL URLs, TLS, production secret check, serving the built frontend."""
import importlib
import ssl

import pytest
from fastapi.testclient import TestClient

from app import config
from app.config import Settings, normalise_database_url


class TestDatabaseUrl:
    def test_aiven_uri_accepted_as_is(self):
        url, tls = normalise_database_url(
            "mysql://avnadmin:p%40ss@mysql-x.aivencloud.com:12345/defaultdb?ssl-mode=REQUIRED"
        )
        assert url == "mysql+pymysql://avnadmin:p%40ss@mysql-x.aivencloud.com:12345/defaultdb?charset=utf8mb4"
        assert tls is True

    def test_local_url_unchanged_apart_from_charset(self):
        url, tls = normalise_database_url("mysql+pymysql://u:p@127.0.0.1/stockwise")
        assert url.endswith("/stockwise?charset=utf8mb4") and tls is False

    def test_ssl_mode_disabled_means_no_tls(self):
        assert normalise_database_url("mysql://u:p@h/db?ssl-mode=DISABLED")[1] is False

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
        s = self._settings(monkeypatch, DATABASE_URL="mysql+pymysql://u:p@127.0.0.1/db")
        assert s.db_connect_args() == {}

    def test_tls_without_ca_encrypts_but_warns(self, monkeypatch, caplog):
        s = self._settings(monkeypatch, DATABASE_URL="mysql://u:p@h:1/db?ssl-mode=REQUIRED")
        ctx = s.db_connect_args()["ssl"]
        assert isinstance(ctx, ssl.SSLContext) and ctx.verify_mode == ssl.CERT_NONE
        assert "not verified" in caplog.text

    def test_ca_cert_text_enables_verification(self, monkeypatch):
        # Pasted into an env var, newlines often arrive as literal "\\n".
        s = self._settings(monkeypatch, DATABASE_URL="mysql://u:p@h:1/db?ssl-mode=REQUIRED",
                           DATABASE_CA_CERT=_SELF_SIGNED_CA.replace("\n", "\\n"))
        ctx = s.db_connect_args()["ssl"]
        assert ctx.verify_mode == ssl.CERT_REQUIRED and ctx.check_hostname is True

    def test_ca_path_enables_verification(self, monkeypatch, tmp_path):
        ca = tmp_path / "ca.pem"
        ca.write_text(_SELF_SIGNED_CA)
        s = self._settings(monkeypatch, DATABASE_URL="mysql://u:p@h:1/db?ssl-mode=REQUIRED",
                           DATABASE_SSL_CA=str(ca))
        ctx = s.db_connect_args()["ssl"]
        assert ctx.verify_mode == ssl.CERT_REQUIRED and ctx.check_hostname is True

    def test_production_refuses_default_secret(self, monkeypatch):
        with pytest.raises(RuntimeError, match="JWT_SECRET"):
            self._settings(monkeypatch, ENVIRONMENT="production", JWT_SECRET="short")


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


# A throwaway self-signed CA, only used to build an SSL context in tests.
_SELF_SIGNED_CA = """\
-----BEGIN CERTIFICATE-----
MIIDGTCCAgGgAwIBAgIUbI+7RsYnE5pC1IhQqbWVn13FLrAwDQYJKoZIhvcNAQEL
BQAwHDEaMBgGA1UEAwwRU3RvY2tXaXNlIFRlc3QgQ0EwHhcNMjYxMTA2MDkwMzAy
WhcNMzYxMTAzMDkwMzAyWjAcMRowGAYDVQQDDBFTdG9ja1dpc2UgVGVzdCBDQTCC
ASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBAMLtKO6vcfv03Tx2LcYYl4b/
uqYfOALptPMXQRQPFFR3+ZpdxGPMPY/3tsAkarAqmMM6wEKTTlwC3k8b9eJ9DnZT
YFWbwJKyu4IWZm62PL2vMwBXD8U4FuQXyoBQXV9KGkrGZE8HXKzABYQg7GMoNmSe
YsveUH+BpWZuDwCdcrLwpJZpuofs4oZ25ssc4DfT/nChEl5Xg8U34O4ouDKBnBNT
1lM6YfU0nSOJaf5uRzv6n6mCz0hQtVTua5eZO+P2Gmkhe8CnKUl0nccPoge4vViV
JcbS1VeShu8XIj8WH4rw9iIF3T49QH/qDMhgN3MLPrvHIK93vpHwvWlZM2BeK9kC
AwEAAaNTMFEwHQYDVR0OBBYEFHPP4sbb6Iq7hLW09qOG7I8aFHIWMB8GA1UdIwQY
MBaAFHPP4sbb6Iq7hLW09qOG7I8aFHIWMA8GA1UdEwEB/wQFMAMBAf8wDQYJKoZI
hvcNAQELBQADggEBAGxvk3aDhYh9GPHg/fy3S4xagZ4PcN28WehyInm47LY6LIlc
5wT2CJCMBUkrdaMYJ27z3j9nano85NFw89tcqX/22GAOJsRO7s330zhaUE7ctgDC
W6kF47YlbGCK+sSFSo7I+eYXfMDMdvUYwbXVu0vgyLhXFdGsspJ5ePd0wHsqS983
YbqKIjwxYKOAfTAHoa4BDgUKyAMJTTJkHEvCK7l3exXePfuU6Adkbd0dLqJv3S0h
thI2sl+V9TgSA5gaBUjvKrr9bADEjjF4mceRWUC6TKa37B7/kOfg4yidF3PrTDE7
6n0hVE2yEX7d+o6ita3iGOcNnvq+lJ5aDGA0mTU=
-----END CERTIFICATE-----
"""
