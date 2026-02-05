"""
Pytest configuration: mock Home Assistant recorder so eon_remread can be imported without HA.
"""
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# Project root (eon-next-main)
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Mock HA recorder modules before any test imports custom_components.eon_remread.eon_remread
for mod in (
    "homeassistant",
    "homeassistant.components",
    "homeassistant.components.recorder",
    "homeassistant.components.recorder.models",
    "homeassistant.components.recorder.statistics",
):
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

# So "from ... import StatisticData, StatisticMetaData" and async_import_statistics get real mocks
sys.modules["homeassistant.components.recorder.models"].StatisticData = MagicMock()
sys.modules["homeassistant.components.recorder.models"].StatisticMetaData = MagicMock()
sys.modules["homeassistant.components.recorder.statistics"].async_import_statistics = AsyncMock()
