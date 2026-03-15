import json

from pushovernet.exceptions import PushoverConfigError


def get_secret(secret_name: str, region: str = "us-east-1") -> dict[str, str | int]:
    try:
        import boto3  # type: ignore[import-not-found]
    except ImportError:
        raise PushoverConfigError(
            "boto3 is required for AWS Secrets Manager support. "
            "Install it with: pip install pushovernet[aws]"
        )

    client = boto3.client("secretsmanager", region_name=region)
    response = client.get_secret_value(SecretId=secret_name)
    secret: dict[str, str | int] = json.loads(response["SecretString"])
    return secret
