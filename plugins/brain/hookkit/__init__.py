"""hookkit: zero-dependency plumbing for Claude Code hooks.

Vendored inside the brain plugin so that installing the plugin installs the
library. Extract to a shared package only when a second plugin needs it.
"""

__all__ = ["failopen"]
