import unittest
from unittest.mock import AsyncMock, Mock, patch

from api.main import lifespan


class APILifespanTests(unittest.IsolatedAsyncioTestCase):

    async def test_normal_shutdown_always_stops_monitor_engine(self):
        engine = Mock()
        engine.start = AsyncMock()
        engine.stop = AsyncMock()

        with patch("api.main.monitor_engine", engine):
            async with lifespan(None):
                engine.start.assert_awaited_once_with()

        engine.stop.assert_awaited_once_with()

    async def test_exception_during_lifespan_still_stops_monitor_engine(self):
        engine = Mock()
        engine.start = AsyncMock()
        engine.stop = AsyncMock()

        with self.assertRaisesRegex(RuntimeError, "controlled shutdown"):
            with patch("api.main.monitor_engine", engine):
                async with lifespan(None):
                    raise RuntimeError("controlled shutdown")

        engine.start.assert_awaited_once_with()
        engine.stop.assert_awaited_once_with()


if __name__ == "__main__":
    unittest.main()
