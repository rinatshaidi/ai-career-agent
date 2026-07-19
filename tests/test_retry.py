from __future__ import annotations

import unittest

from utils import RetryPolicy, retry_call


class RetryTests(unittest.TestCase):
    def test_retries_until_operation_succeeds(self) -> None:
        calls = 0
        sleeps: list[float] = []

        def operation() -> str:
            nonlocal calls
            calls += 1
            if calls < 3:
                raise RuntimeError("temporary")
            return "ok"

        result = retry_call(
            operation,
            exceptions=(RuntimeError,),
            policy=RetryPolicy(attempts=3, delay_seconds=2),
            sleep=sleeps.append,
        )

        self.assertEqual(result, "ok")
        self.assertEqual(calls, 3)
        self.assertEqual(sleeps, [2, 2])

    def test_raises_after_attempt_limit(self) -> None:
        calls = 0

        def operation() -> None:
            nonlocal calls
            calls += 1
            raise RuntimeError("still unavailable")

        with self.assertRaisesRegex(RuntimeError, "still unavailable"):
            retry_call(
                operation,
                exceptions=(RuntimeError,),
                policy=RetryPolicy(attempts=2, delay_seconds=0),
                sleep=lambda _seconds: None,
            )
        self.assertEqual(calls, 2)


if __name__ == "__main__":
    unittest.main()
