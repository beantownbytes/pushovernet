import pytest

from pushovernet.config import PushoverConfig


@pytest.fixture
def sample_config():
    return PushoverConfig(
        token="test_token_abc123",
        user_key="test_user_xyz789",
        default_device="iphone",
        default_priority=0,
        default_sound="pushover",
    )


@pytest.fixture
def client(sample_config):
    from pushovernet.client import PushoverClient

    c = PushoverClient(config=sample_config)
    yield c
    c.close()


STANDARD_RESPONSE = {"status": 1, "request": "req-abc-123"}
