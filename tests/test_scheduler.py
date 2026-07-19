from __future__ import annotations

import unittest

from services import IntervalScheduler


class SchedulerTests(unittest.TestCase):
    def test_stops_cleanly_after_requested_cycle(self) -> None:
        calls = 0
        scheduler: IntervalScheduler

        def task() -> None:
            nonlocal calls
            calls += 1
            scheduler.stop()

        scheduler = IntervalScheduler(task, interval_seconds=60)
        scheduler.run_forever()
        self.assertEqual(calls, 1)

    def test_continues_after_cycle_error(self) -> None:
        calls = 0
        scheduler: IntervalScheduler

        def task() -> None:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError("cycle failed")
            scheduler.stop()

        scheduler = IntervalScheduler(task, interval_seconds=1)
        scheduler.run_forever()
        self.assertEqual(calls, 2)


if __name__ == "__main__":
    unittest.main()
