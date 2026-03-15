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

## Proxy Server

A local REST API proxy so LAN devices can send notifications without knowing your Pushover credentials.

```bash
pip install pushovernet[server]
```

### Running

```bash
pushovernet-server
python -m pushovernet
```

Listens on `0.0.0.0:9505` by default. Configure via TOML or environment variables:

```toml
[server]
api_key = "my-lan-secret"
host = "0.0.0.0"
port = 9505
```

Or: `PUSHOVERNET_API_KEY`, `PUSHOVERNET_HOST`, `PUSHOVERNET_PORT`.

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/send` | Send a notification |
| POST | `/glance` | Send glance data |
| GET | `/sounds` | List available sounds |
| GET | `/limits` | Get rate limit status |
| GET | `/health` | Health check |

### Examples

```bash
curl -X POST http://localhost:9505/send \
  -H "Content-Type: application/json" \
  -d '{"message": "hello from the LAN"}'

curl -X POST http://localhost:9505/send \
  -H "Content-Type: application/json" \
  -H "X-API-Key: my-lan-secret" \
  -d '{"message": "alert", "title": "Server", "priority": 1}'
```

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
