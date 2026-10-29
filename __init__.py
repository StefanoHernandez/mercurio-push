"""Hermes entry point: the plugin itself lives in the mercurio_push package."""

if __package__:  # loaded by Hermes as a plugin package (pytest imports this file bare)
    from .mercurio_push.plugin import register  # noqa: F401
