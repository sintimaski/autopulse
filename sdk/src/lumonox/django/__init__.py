"""Django async middleware adapter for the Lumonox SDK.

Importing this subpackage does not import Django; ``monitor()`` (and the
middleware class) raise a clear ImportError pointing at the ``[django]``
extra if Django is not installed.

Single-line install:

    pip install "lumonox-sdk[django]"

Single-line ASGI wire-up (in your ``asgi.py``):

    from django.core.asgi import get_asgi_application
    from lumonox.django import monitor, wrap_asgi

    monitor(api_key="...", ingest_url="https://lumonox.example/ingest")
    application = wrap_asgi(get_asgi_application())

Then add ``"lumonox.django.middleware.LumonoxMiddleware"`` to ``MIDDLEWARE``
in ``settings.py``.

See ``sdk/docs/adapters.md`` for the full adapter contract.
"""

from lumonox.django.middleware import LumonoxMiddleware, monitor, wrap_asgi

__all__ = ["LumonoxMiddleware", "monitor", "wrap_asgi"]
