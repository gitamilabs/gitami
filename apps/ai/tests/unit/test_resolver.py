from src.graph.resolver import resolve_relative_path, resolve_python_path


def test_resolve_relative_path_exact():
    known = {"tests/fixtures/mern_sample/api.js", "tests/fixtures/mern_sample/Header.jsx"}
    importer = "tests/fixtures/mern_sample/UserService.js"

    res = resolve_relative_path(importer, "./api.js", known)
    assert res == "tests/fixtures/mern_sample/api.js"


def test_resolve_relative_path_without_extension():
    known = {"tests/fixtures/mern_sample/api.js", "tests/fixtures/mern_sample/Header.jsx"}
    importer = "tests/fixtures/mern_sample/UserService.js"

    res = resolve_relative_path(importer, "./api", known)
    assert res == "tests/fixtures/mern_sample/api.js"


def test_resolve_python_path():
    known = {"tests/fixtures/python_sample/user_model.py", "tests/fixtures/python_sample/utils.py"}
    importer = "tests/fixtures/python_sample/app.py"

    res = resolve_python_path(importer, "user_model", known)
    assert res == "tests/fixtures/python_sample/user_model.py"
