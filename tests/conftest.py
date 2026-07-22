import gzip
from collections import defaultdict
from pathlib import Path
from typing import Any, BinaryIO, cast

import numpy as np
import pytest
import yaml
from bson import decode_file_iter

from tests.data.make_test_data import (
    DATA_DIR,
    JOB_FILE_PATH,
    MONGO_PREFIX,
    patch_schema,
)


def get_collection_filename(collection_name: str) -> Path:
    return DATA_DIR / MONGO_PREFIX / f"{collection_name}.bson.gz"


def load_collection(collection_name: str) -> list[dict[str, Any]]:
    fn = get_collection_filename(collection_name)
    with gzip.open(fn, "rb") as f:
        f = cast(BinaryIO, f)
        return list(decode_file_iter(f))


@pytest.fixture
def collections() -> dict[str, dict]:
    _collections = {"stock": load_collection("stock")}
    for i in range(3):
        n = f"t{i}"
        col = sorted(load_collection(n), key=lambda c: c["stock"], reverse=True)
        sorted_col = defaultdict(list)
        for c in col:
            for stock in np.atleast_1d(c["stock"]):
                sorted_col[stock].append(c)
        _collections[n] = sorted_col
    return _collections


@pytest.fixture
def test_schema_path(tmp_path: Path) -> Path:
    test_schema_path = tmp_path / "test_schema.yaml"
    with open(JOB_FILE_PATH) as f, test_schema_path.open("w") as g:
        patch_schema(f, g)
    return test_schema_path


@pytest.fixture
def test_schema(test_schema_path: Path) -> dict[str, Any]:
    with open(test_schema_path) as f:
        return yaml.safe_load(f)
