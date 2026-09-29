"""帳號名稱規則（app/naming.py）：註冊、管理員新增帳號、改名共用。"""
import pytest

from app.naming import valid_username


@pytest.mark.parametrize("name", ["sparkle", "deven951130", "管理員", "小明_01", "a.b-c", "ab", "_x", "x" * 32])
def test_accepts(name):
    assert valid_username(name)


@pytest.mark.parametrize("name", [
    # 可被當成 HTML／程式碼（管理頁、問題反饋會顯示帳號名稱）
    "<img src=x onerror=alert(1)>", "o'neil", 'say"hi', "semi;colon", "amp&",
    # 可跳出 NAS 目錄（名稱就是 NAS_ROOT 底下的資料夾名）
    "..", "...", ".hidden", "../../etc", "..\\app", "a/b", "a\\b", "a/..", "-x",
    # 長度、空白、控制字元、型別
    "", "a", "x" * 33, "a b", "tab\tname", "line\nbreak", "x y", None, 123,
])
def test_rejects(name):
    assert not valid_username(name)
