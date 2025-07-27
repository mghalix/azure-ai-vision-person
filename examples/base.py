import getpass
import os
from collections.abc import Sequence


def _set_env(var: str) -> None:
    if os.environ.get(var):
        return

    os.environ[var] = getpass.getpass(f"{var}: ")


def _init_env(keys: Sequence[str] = ("AZURE_AI_ENDPOINT", "AZURE_AI_KEY")) -> None:
    from dotenv import load_dotenv

    load_dotenv()

    for key in keys:
        _set_env(key)


def get_config() -> tuple[str, str]:
    azure_ai_endpoint: str = os.environ["AZURE_AI_ENDPOINT"]
    azure_ai_key = os.environ["AZURE_AI_KEY"]

    return azure_ai_endpoint, azure_ai_key
