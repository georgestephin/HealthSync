import pytest
from healthsync import create_app


class Web:
    """Tiny test browser: logs in, keeps the CSRF token, posts forms."""

    def __init__(self, app, email=None, password=None):
        self.c = app.test_client()
        self.c.get("/")
        if email:
            assert self.post("/login", follow=False, email=email, password=password).status_code == 302, f"login failed for {email}"

    def token(self):
        with self.c.session_transaction() as s:
            return s["csrf"]

    def get(self, url, code=200):
        r = self.c.get(url)
        assert r.status_code == code, f"{url} -> {r.status_code}"
        return r.get_data(as_text=True)

    def post(self, url, follow=True, **data):
        return self.c.post(url, data=dict(_csrf=self.token(), **data), follow_redirects=follow)

    def text(self, url, **data):
        return self.post(url, **data).get_data(as_text=True)


@pytest.fixture(autouse=True)
def claims_service(monkeypatch):
    """Every test talks to an in-memory fake of the Claims service, never to a real one."""
    from tests.fake_claims import FakeClaims
    fake = FakeClaims()
    monkeypatch.setattr("healthsync.claims_client.call", fake)
    return fake


@pytest.fixture
def app(tmp_path):
    return create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.db"), "SECRET_KEY": "test"})


@pytest.fixture
def web(app):
    return lambda email=None, password=None: Web(app, email, password)


@pytest.fixture
def accounts(web):
    return dict(
        patient=web("patient@healthsync.local", "Patient@123"), doctor=web("doctor@healthsync.local", "Doctor@123"),
        admin=web("admin@healthsync.local", "Admin@123"), superadmin=web("superadmin@healthsync.local", "Super@123"),
        tpa_desk=web("tpadesk@healthsync.local", "Desk@123"), pmjay_desk=web("pmjaydesk@healthsync.local", "Desk@123"))
