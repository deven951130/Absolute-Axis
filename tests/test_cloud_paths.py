"""私有雲路徑：使用者只能碰自己的 NAS_ROOT/<帳號> 與自己的垃圾桶。

檔名以 cl 開頭：要比 test_devicehub_module.py（會用假的 app.utils 取代真的）先被收集。
執行：在 repo 根目錄 `python -m pytest tests`
"""
import os
import tempfile

os.environ.setdefault("AXIS_BASE_PATH", tempfile.mkdtemp(prefix="axis-test-"))
os.environ.setdefault("AXIS_JWT_SECRET", "t" * 64)

import pytest  # noqa: E402
from fastapi import HTTPException  # noqa: E402

from app import utils  # noqa: E402
from app.models import ToggleRequest  # noqa: E402
from app.routers import nas  # noqa: E402


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(utils, "NAS_ROOT", str(tmp_path))
    monkeypatch.setattr(nas, "NAS_ROOT", str(tmp_path))
    monkeypatch.setattr(nas, "log_event", lambda *a: None)
    return tmp_path


def _write(path, text="x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _user(name):
    return {"username": name}


# ---------- safe_path ----------
@pytest.mark.parametrize("rel,expected", [
    ("", ""), ("a.txt", "a.txt"), ("/a.txt", "a.txt"), ("sub/b.txt", "sub/b.txt"), ("sub/../c.txt", "c.txt"),
])
def test_safe_path_inside(root, rel, expected):
    assert utils.safe_path(rel, "ad") == os.path.abspath(os.path.join(root, "ad", expected))


@pytest.mark.parametrize("rel", [
    "../admin/secret.txt",  # 帳號 ad 是 admin 的前綴：舊版 startswith 會放行
    "../adx", "..", "../..", "sub/../../admin", "../.trash/bob",
])
def test_safe_path_rejects_escape(root, rel):
    _write(root / "admin" / "secret.txt", "admin only")
    with pytest.raises(HTTPException) as e:
        utils.safe_path(rel, "ad")
    assert e.value.status_code == 403


@pytest.mark.parametrize("username", ["..", "../admin", "a/b"])
def test_safe_path_rejects_bad_username(root, username):
    with pytest.raises(HTTPException) as e:
        utils.safe_path("", username)
    assert e.value.status_code == 403


# ---------- 垃圾桶 ----------
@pytest.mark.parametrize("path", ["..", ".", "", "sub/.."])
def test_delete_rejects_trash_itself_or_parent(root, path):
    _write(root / ".trash" / "ad" / "mine.txt")
    _write(root / ".trash" / "bob" / "bobs.txt")
    _write(root / "ad" / "keep.txt")
    with pytest.raises(HTTPException) as e:
        nas.delete_nas(ToggleRequest(path=path), user=_user("ad"))
    assert e.value.status_code == 400
    assert (root / ".trash" / "bob" / "bobs.txt").exists()
    assert (root / ".trash" / "ad" / "mine.txt").exists()
    assert (root / "ad" / "keep.txt").exists()


@pytest.mark.parametrize("path", ["..", ".", ""])
def test_restore_rejects_trash_itself_or_parent(root, path):
    _write(root / ".trash" / "ad" / "mine.txt")
    _write(root / ".trash" / "bob" / "bobs.txt")
    with pytest.raises(HTTPException) as e:
        nas.restore_from_trash(ToggleRequest(path=path), user=_user("ad"))
    assert e.value.status_code == 400
    assert (root / ".trash" / "bob" / "bobs.txt").exists()
    assert not (root / "ad" / "bobs.txt").exists()


def test_trash_rejects_whole_drive(root):
    _write(root / "ad" / "keep.txt")
    with pytest.raises(HTTPException) as e:
        nas.move_to_trash(ToggleRequest(path=""), user=_user("ad"))
    assert e.value.status_code == 400
    assert (root / "ad" / "keep.txt").exists()


def test_trash_restore_delete_still_work(root):
    _write(root / "ad" / "sub" / "a.txt", "hello")
    nas.move_to_trash(ToggleRequest(path="sub/a.txt"), user=_user("ad"))
    assert (root / ".trash" / "ad" / "a.txt").exists()
    assert not (root / "ad" / "sub" / "a.txt").exists()

    nas.restore_from_trash(ToggleRequest(path="a.txt"), user=_user("ad"))
    assert (root / "ad" / "a.txt").read_text() == "hello"

    nas.move_to_trash(ToggleRequest(path="a.txt"), user=_user("ad"))
    nas.delete_nas(ToggleRequest(path="a.txt"), user=_user("ad"))
    assert not (root / ".trash" / "ad" / "a.txt").exists()
    assert not (root / "ad" / "a.txt").exists()


def test_delete_from_drive_still_works(root):
    _write(root / "ad" / "sub" / "b.txt")
    nas.delete_nas(ToggleRequest(path="sub/b.txt"), user=_user("ad"))
    assert not (root / "ad" / "sub" / "b.txt").exists()
    assert (root / "ad" / "sub").exists()
