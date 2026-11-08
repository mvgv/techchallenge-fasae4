import pytest

from medwatch.storage import LocalStorage, key_from_uri


def test_local_roundtrip(tmp_path):
    st = LocalStorage(tmp_path / "root")
    src = tmp_path / "a.txt"
    src.write_bytes(b"ola")
    uri = st.put_file(src, "media/p/m/a.txt")
    assert uri == "local://media/p/m/a.txt"
    out = st.get_to_path(uri, tmp_path / "out" / "b.txt")
    assert out.read_bytes() == b"ola"
    uri2 = st.put_bytes(b"xyz", "artifacts/m/x.bin")
    assert b"".join(st.open_stream(key_from_uri(uri2))) == b"xyz"


def test_key_from_uri():
    assert key_from_uri("local://a/b") == "a/b"
    assert key_from_uri("azure://media/a/b") == "a/b"
    with pytest.raises(ValueError):
        key_from_uri("http://x")


def test_path_traversal_blocked(tmp_path):
    with pytest.raises(ValueError):
        LocalStorage(tmp_path).put_bytes(b"x", "../evil")
