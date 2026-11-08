"""Armazenamento de arquivos: local ou Azure Blob."""
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from medwatch.config import get_settings


def key_from_uri(uri: str) -> str:
    """Extrai a chave de um URI local://<key> ou azure://<container>/<key>."""
    if uri.startswith("local://"):
        return uri[len("local://"):]
    if uri.startswith("azure://"):
        return uri[len("azure://"):].split("/", 1)[1]
    raise ValueError(f"URI desconhecido: {uri}")


class Storage(Protocol):
    def put_file(self, local_path: Path, key: str) -> str: ...
    def put_bytes(self, data: bytes, key: str) -> str: ...
    def get_to_path(self, uri: str, dest: Path) -> Path: ...
    def open_stream(self, key: str) -> Iterator[bytes]: ...


class LocalStorage:
    def __init__(self, root: Path):
        self.root = Path(root)

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if not p.is_relative_to(self.root.resolve()):
            raise ValueError(f"Chave fora da raiz: {key}")
        return p

    def put_bytes(self, data: bytes, key: str) -> str:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return f"local://{key}"

    def put_file(self, local_path: Path, key: str) -> str:
        return self.put_bytes(Path(local_path).read_bytes(), key)

    def get_to_path(self, uri: str, dest: Path) -> Path:
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(self._path(key_from_uri(uri)).read_bytes())
        return dest

    def open_stream(self, key: str) -> Iterator[bytes]:
        with self._path(key).open("rb") as f:
            while chunk := f.read(1024 * 1024):
                yield chunk


class AzureBlobStorage:
    def __init__(self, connection_string: str, container: str):
        from azure.core.exceptions import ResourceExistsError
        from azure.storage.blob import BlobServiceClient

        self.container = container
        self.service = BlobServiceClient.from_connection_string(connection_string)
        self.client = self.service.get_container_client(container)
        try:
            self.client.create_container()
        except ResourceExistsError:
            pass

    def put_bytes(self, data: bytes, key: str) -> str:
        self.client.upload_blob(key, data, overwrite=True)
        return f"azure://{self.container}/{key}"

    def put_file(self, local_path: Path, key: str) -> str:
        with open(local_path, "rb") as f:
            self.client.upload_blob(key, f, overwrite=True)
        return f"azure://{self.container}/{key}"

    def get_to_path(self, uri: str, dest: Path) -> Path:
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(self.client.download_blob(key_from_uri(uri)).readall())
        return dest

    def open_stream(self, key: str) -> Iterator[bytes]:
        yield from self.client.download_blob(key).chunks()


@lru_cache
def get_storage() -> Storage:
    s = get_settings()
    if s.storage_backend == "azure":
        return AzureBlobStorage(s.azure_storage_connection_string, s.azure_storage_container)
    return LocalStorage(s.local_storage_dir)
