"""Shared public client distribution details."""

from . import __version__

SDK_WHEEL = f"ccask_client-{__version__}-py3-none-any.whl"


def install_command():
    return (
        'NO_PROXY=127.0.0.1,localhost python -m pip install --upgrade '
        f'"http://127.0.0.1:8765/api/sdk/{SDK_WHEEL}"'
    )
