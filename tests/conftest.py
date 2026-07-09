import gzip
from collections import defaultdict
from pathlib import Path
from typing import Any, BinaryIO, cast

import numpy as np
import pytest
import yaml
from bson import decode_file_iter

from ampel.config.builder.DisplayOptions import DisplayOptions
from ampel.config.builder.DistConfigBuilder import DistConfigBuilder
from tests.data.make_test_data import (
    DATA_DIR,
    JOB_FILE_PATH,
    MONGO_PREFIX,
    patch_schema,
)


@pytest.fixture(scope="session")
def testing_config(tmp_path_factory, pytestconfig):
    """Path to an Ampel config file suitable for testing."""
    config_path = tmp_path_factory.mktemp("config") / "testing-config.yaml"
    if (config := pytestconfig.cache.get("testing_config", None)) is None:
        # build a config from all available ampel distributions
        cb = DistConfigBuilder(
            DisplayOptions(verbose=False, debug=False),
        )
        cb.load_distributions()
        config = cb.build_config(
            stop_on_errors=0,
            config_validator="ConfigValidator",
            get_unit_env=False,
        )
        assert config is not None
        # massage db settings for use with mongomock
        for db in config["mongo"]["databases"]:
            for collection in db["collections"]:
                # remove unsuported storageEngine options
                if "args" in collection and "storageEngine" in collection["args"]:
                    collection["args"].pop("storageEngine")
            # ensure that r and w modes share a client
            db["role"]["r"] = db["role"]["w"]
        pytestconfig.cache.set("testing_config", config)
    with open(config_path, "w") as f:
        yaml.safe_dump(config, f)
    return config_path


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
