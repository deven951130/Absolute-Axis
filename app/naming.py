"""帳號名稱規則（註冊與管理員新增帳號共用；登入不檢查，已存在的帳號照常可用）。

帳號名稱會顯示在管理頁、問題反饋、分享對象等地方，也是 NAS 目錄名稱（NAS_ROOT/<名稱>）；
允許中英文字、數字與 _ . -，第一個字必須是文字／數字／底線——
不允許空白、引號、角括號（可被當成 HTML／程式碼），也不允許 "/"、"\\"、".."、"."開頭（可跳出 NAS 目錄）。
"""
import re

_USERNAME = re.compile(r"^\w[\w.\-]{1,31}$")  # \w 含中文等 Unicode 文字、數字與底線


def valid_username(name: str | None) -> bool:
    return isinstance(name, str) and _USERNAME.fullmatch(name) is not None


USERNAME_RULE = "帳號名稱需 2–32 字，只能使用中英文字、數字與 _ . -，且第一個字要是文字或數字"
