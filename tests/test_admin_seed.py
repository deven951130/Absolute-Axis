"""第一次啟動建立管理員（app/utils.py init_db_user）的規則。

- 資料庫裡一個管理員都沒有時，才用 AXIS_ADMIN_USER（預設 admin）＋ AXIS_ADMIN_PASS 建立。
- 已有管理員（例如舊版建立的 sparkle）就不動，升級既有站台不會多出第二個管理員。
執行：在 repo 根目錄 `python -m pytest tests`
"""
import os
import tempfile

# app.config 在匯入時決定資料路徑：指到暫存目錄，測試不碰 repo 裡的 axis.db / nas/
os.environ.setdefault("AXIS_BASE_PATH", tempfile.mkdtemp(prefix="axis-test-"))
os.environ.setdefault("AXIS_JWT_SECRET", "t" * 64)

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

import app.utils as utils  # noqa: E402
from app.database import Base, User  # noqa: E402


@pytest.fixture
def Session(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'axis.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(utils, "SessionLocal", factory)
    monkeypatch.delenv("AXIS_ADMIN_USER", raising=False)
    monkeypatch.setenv("AXIS_ADMIN_PASS", "initial-pass-123")
    yield factory
    engine.dispose()


def _users(factory):
    s = factory()
    try:
        return sorted((u.username, u.role) for u in s.query(User).all())
    finally:
        s.close()


def _add(factory, name, role):
    s = factory()
    s.add(User(username=name, password_hash="x", role=role))
    s.commit()
    s.close()


def test_creates_default_admin(Session):
    utils.init_db_user()
    assert _users(Session) == [("admin", "Administrator")]


def test_password_is_hashed_and_works(Session):
    utils.init_db_user()
    s = Session()
    u = s.query(User).filter(User.username == "admin").one()
    s.close()
    assert u.password_hash != "initial-pass-123"
    assert utils.verify_password("initial-pass-123", u.password_hash)


def test_custom_admin_name(Session, monkeypatch):
    monkeypatch.setenv("AXIS_ADMIN_USER", "小明")
    utils.init_db_user()
    assert _users(Session) == [("小明", "Administrator")]


@pytest.mark.parametrize("role", ["Administrator", "admin"])
def test_existing_admin_is_left_alone(Session, role):
    # 既有站台（舊版建立的 sparkle）升級後不能多出第二個管理員
    _add(Session, "sparkle", role)
    utils.init_db_user()
    assert _users(Session) == [("sparkle", role)]


def test_renamed_admin_is_not_recreated(Session, monkeypatch):
    monkeypatch.setenv("AXIS_ADMIN_USER", "sparkle")
    _add(Session, "新名字", "Administrator")
    utils.init_db_user()
    assert _users(Session) == [("新名字", "Administrator")]


def test_no_password_creates_nothing(Session, monkeypatch):
    monkeypatch.delenv("AXIS_ADMIN_PASS")
    utils.init_db_user()
    assert _users(Session) == []


@pytest.mark.parametrize("value", ["", "   ", "<請填入管理員初始密碼>"])
def test_blank_or_template_password_creates_nothing(Session, monkeypatch, value):
    monkeypatch.setenv("AXIS_ADMIN_PASS", value)
    utils.init_db_user()
    assert _users(Session) == []


@pytest.mark.parametrize("name", ["a b", "<img>", "../x", "x"])
def test_invalid_name_creates_nothing(Session, monkeypatch, name):
    monkeypatch.setenv("AXIS_ADMIN_USER", name)
    utils.init_db_user()
    assert _users(Session) == []


def test_member_with_same_name_is_not_promoted(Session):
    _add(Session, "admin", "Member")
    utils.init_db_user()
    assert _users(Session) == [("admin", "Member")]
