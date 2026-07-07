import gzip
from pathlib import Path
from typing import Any, BinaryIO, cast

import pytest
from bson import decode_file_iter
from data import DATA_DIR, MONGO_PREFIX


def get_collection_filename(collection_name: str) -> Path:
    return DATA_DIR / MONGO_PREFIX / f"{collection_name}.bson.gz"


@pytest.fixture
def collections() -> dict[str, list[Any]]:
    _collections = {}
    for i in range(3):
        n = f"t{i}"
        fn = get_collection_filename(n)
        with gzip.open(fn, "rb") as f:
            f = cast(BinaryIO, f)
            _collections[n] = list(decode_file_iter(f))
    return _collections
