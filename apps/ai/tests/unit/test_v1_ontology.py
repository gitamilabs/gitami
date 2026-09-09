from src.parsing.parser import CodeParser


def test_python_ontology_extraction():
    parser = CodeParser()
    py_code = b"""
class BaseService:
    def base_method(self):
        pass

class UserService(BaseService):
    def get_user(self, user_id: str):
        return True

def standalone_func():
    return 1

def test_user_service():
    assert True
"""
    res = parser.parse_code_bytes(py_code, "services/user.py")
    assert res is not None
    assert len(res.symbols) >= 5

    symbols_by_name = {s.name: s for s in res.symbols}
    assert symbols_by_name["BaseService"].kind == "class"
    assert symbols_by_name["UserService"].kind == "class"
    assert symbols_by_name["UserService"].superclasses == ["BaseService"]

    assert symbols_by_name["base_method"].kind == "method"
    assert symbols_by_name["base_method"].class_name == "BaseService"

    assert symbols_by_name["get_user"].kind == "method"
    assert symbols_by_name["get_user"].class_name == "UserService"

    assert symbols_by_name["standalone_func"].kind == "function"
    assert symbols_by_name["test_user_service"].kind == "test"

    # Heritage edges
    assert len(res.heritage) == 1
    assert res.heritage[0].subclass_name == "UserService"
    assert res.heritage[0].target_name == "BaseService"
    assert res.heritage[0].kind == "extends"


def test_typescript_ontology_extraction():
    parser = CodeParser()
    ts_code = b"""
interface UserDTO {
    id: string;
    name: string;
}

type UserRole = 'admin' | 'viewer';

class AdminUser extends BaseAccount implements UserDTO {
    getRole(): UserRole {
        return 'admin';
    }
}

function fetchUser() {
    return null;
}
"""
    res = parser.parse_code_bytes(ts_code, "models/user.ts")
    assert res is not None

    symbols_by_name = {s.name: s for s in res.symbols}
    assert "UserDTO" in symbols_by_name
    assert symbols_by_name["UserDTO"].kind == "interface"

    assert "UserRole" in symbols_by_name
    assert symbols_by_name["UserRole"].kind == "type"

    assert "AdminUser" in symbols_by_name
    assert symbols_by_name["AdminUser"].kind == "class"
    assert symbols_by_name["AdminUser"].superclasses == ["BaseAccount"]
    assert symbols_by_name["AdminUser"].interfaces == ["UserDTO"]

    assert "getRole" in symbols_by_name
    assert symbols_by_name["getRole"].kind == "method"
    assert symbols_by_name["getRole"].class_name == "AdminUser"

    assert "fetchUser" in symbols_by_name
    assert symbols_by_name["fetchUser"].kind == "function"

    # Heritage
    h_map = {(h.subclass_name, h.target_name): h.kind for h in res.heritage}
    assert h_map.get(("AdminUser", "BaseAccount")) == "extends"
    assert h_map.get(("AdminUser", "UserDTO")) == "implements"
