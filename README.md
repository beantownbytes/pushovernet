# pushovernet

Python client for the [Pushover.net](https://pushover.net) notification API.

## Installation

```bash
pip install pushovernet
```

For AWS Secrets Manager support:

```bash
pip install pushovernet[aws]
```

## Configuration

Create `~/.config/pushovernet/config.toml`:

```toml
[pushover]
token = "your_app_token"
user_key = "your_user_key"
default_device = ""
default_priority = 0
default_sound = ""
```

## Usage

```python
from pushovernet import PushoverClient

with PushoverClient() as client:
    client.send_message("Hello from pushovernet")

    client.send_message(
        "Server alert",
        title="Alert",
        priority=1,
        sound="siren",
    )

    # Emergency priority (requires retry/expire)
    client.send_message(
        "Critical failure",
        priority=2,
        retry=60,
        expire=3600,
    )
```

### Explicit credentials

```python
client = PushoverClient(token="...", user_key="...")
```

### Environment variables

```python
from pushovernet import PushoverClient, PushoverConfig

config = PushoverConfig.from_env()  # reads PUSHOVER_TOKEN, PUSHOVER_USER_KEY
client = PushoverClient(config=config)
```

### AWS Secrets Manager

```python
from pushovernet import PushoverClient, PushoverConfig

config = PushoverConfig.from_aws_secret("my/pushover/secret", region="us-east-1")
client = PushoverClient(config=config)
```

The secret JSON should contain `token` and `user_key` keys.

## API Coverage

- Messages: send, with attachments, emergency priority
- User validation
- Receipts: query, cancel, cancel by tag
- Sounds: list available sounds
- Rate limits: query app limits
- Groups: create, list, get, add/remove/enable/disable users, rename
- Glances: send glance data
- Subscriptions: migrate
- Licenses: assign, get credits
