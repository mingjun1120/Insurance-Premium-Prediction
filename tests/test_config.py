"""Tests that `config.yml` still has everything the code reaches for.

Small, and worth having. `config.yml` is not imported by anything - it is read
at runtime by key - so a typo or a deleted section produces a KeyError deep in
a training run rather than an error at startup. These tests turn that into an
instant, obvious failure.
"""

import pytest
import yaml

from steps import CONFIG_PATH, PROJECT_ROOT, load_config, resolve
from steps.train import MODEL_REGISTRY


@pytest.fixture
def config():
    return load_config()


def test_config_file_exists():
    assert CONFIG_PATH.exists(), f"config.yml is missing from {PROJECT_ROOT}"


def test_config_is_valid_yaml():
    yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize("section", ["data", "train", "model", "models", "mlflow"])
def test_top_level_sections_are_present(config, section):
    assert section in config


@pytest.mark.parametrize("key", ["source_path", "data_path", "target"])
def test_data_keys(config, key):
    assert key in config["data"]


@pytest.mark.parametrize("key", ["test_size", "random_state", "use_log_target"])
def test_train_keys(config, key):
    assert key in config["train"]


@pytest.mark.parametrize("key", ["name", "tune", "store_path"])
def test_model_keys(config, key):
    assert key in config["model"]


@pytest.mark.parametrize(
    "key",
    ["experiment_name", "registered_model_name", "developer",
     "tracking_db", "artifact_location"],
)
def test_mlflow_keys(config, key):
    assert key in config["mlflow"]


def test_active_model_is_one_the_code_can_build(config):
    """The name in `model.name` has to exist in the registry, or nothing runs."""
    assert config["model"]["name"] in MODEL_REGISTRY


def test_every_registry_model_has_a_config_block(config):
    """Switching models by editing one line only works if the block is there."""
    for name in MODEL_REGISTRY:
        assert name in config["models"], f"config.yml has no block for {name}"
        assert "params" in config["models"][name]
        assert "tuning_params" in config["models"][name]


def test_tuning_grids_use_the_pipeline_prefix(config):
    """Grid keys must address a pipeline step, or GridSearchCV rejects them.

    `create_pipeline` always names the final step `model`, and the linear
    pipeline adds `prepare`, `expand` and `rescale`.
    """
    valid_prefixes = ("model__", "prepare__", "expand__", "rescale__")

    for name, block in config["models"].items():
        for key in block["tuning_params"]:
            assert key.startswith(valid_prefixes), (
                f"{name}: tuning key '{key}' addresses no pipeline step"
            )


def test_use_log_target_is_a_boolean(config):
    """A string "false" is truthy, which would silently enable the transform."""
    assert isinstance(config["train"]["use_log_target"], bool)


def test_tune_is_a_boolean(config):
    assert isinstance(config["model"]["tune"], bool)


def test_resolve_returns_absolute_paths():
    """Paths in config.yml are relative; `resolve` anchors them to the project."""
    resolved = resolve("models/")

    assert resolved.is_absolute()
    assert resolved.is_relative_to(PROJECT_ROOT)
