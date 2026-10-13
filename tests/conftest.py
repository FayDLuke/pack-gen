import sys
import types

# Fuck
try:
    import endstone  # noqa: F401
except ImportError:
    stub = types.ModuleType("endstone")
    plugin = types.ModuleType("endstone.plugin")
    plugin.Plugin = type("Plugin", (), {})
    stub.plugin = plugin
    sys.modules["endstone"] = stub
    sys.modules["endstone.plugin"] = plugin
