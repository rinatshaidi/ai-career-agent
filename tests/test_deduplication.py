from __future__ import annotations

import unittest
from dataclasses import replace

from tests.test_repository import make_opportunity
from utils.deduplication import canonicalize_url, opportunity_fingerprint


class DeduplicationTests(unittest.TestCase):
    def test_removes_tracking_and_normalizes_url_shape(self) -> None:
        first = canonicalize_url(
            "HTTPS://WWW.Example.com:443/jobs/42/?utm_source=mail&b=2&a=1#apply"
        )
        second = canonicalize_url("https://example.com/jobs/42?a=1&b=2")
        self.assertEqual(first, second)

    def test_keeps_identity_query_parameters(self) -> None:
        first = canonicalize_url("https://example.com/job?id=42&utm_campaign=test")
        second = canonicalize_url("https://example.com/job?id=43")
        self.assertNotEqual(first, second)

    def test_fingerprint_normalizes_case_punctuation_and_whitespace(self) -> None:
        first = make_opportunity("first")
        second = replace(
            first,
            source="another_source",
            external_id="second",
            url="https://another.example/jobs/second",
            title="  AUTOMATION---TASK first ",
            company_name="EXAMPLE",
            location="Moscow!!!",
            description="Build   a workflow.",
        )
        self.assertEqual(opportunity_fingerprint(first), opportunity_fingerprint(second))

    def test_fingerprint_changes_when_description_changes(self) -> None:
        first = make_opportunity("first")
        second = replace(first, description="Build an unrelated backend service.")
        self.assertNotEqual(opportunity_fingerprint(first), opportunity_fingerprint(second))


if __name__ == "__main__":
    unittest.main()

