from dataclasses import dataclass


@dataclass(frozen=True)
class MessageResponse:
    status: int
    request: str
    receipt: str | None = None


@dataclass(frozen=True)
class RateLimits:
    limit: int
    remaining: int
    reset: int


@dataclass(frozen=True)
class ReceiptStatus:
    status: int
    request: str
    acknowledged: int
    acknowledged_at: int
    acknowledged_by: str
    acknowledged_by_device: str
    last_delivered_at: int
    expired: int
    expires_at: int
    called_back: int
    called_back_at: int


@dataclass(frozen=True)
class ValidateResponse:
    status: int
    request: str
    devices: list[str]


@dataclass(frozen=True)
class GroupUser:
    user: str
    device: str
    memo: str
    disabled: bool


@dataclass(frozen=True)
class GroupInfo:
    name: str
    users: list[GroupUser]


@dataclass(frozen=True)
class GroupCreated:
    status: int
    request: str
    group: str


@dataclass(frozen=True)
class GroupListEntry:
    group: str
    name: str


@dataclass(frozen=True)
class LicenseInfo:
    status: int
    request: str
    credits: int


@dataclass(frozen=True)
class SubscriptionResponse:
    status: int
    request: str
    subscribed_user_key: str
