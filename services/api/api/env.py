"""The only module that reads os.environ — and only secrets come through it."""

from api.secrets import Secrets


def secrets_from_env() -> Secrets:
    return Secrets()
