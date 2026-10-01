from __future__ import annotations

import unittest

from tools.exporters.common import EXPECTED_PAIRED, EXPECTED_TASKS, RUNS


class CanonicalConfigurationTest(unittest.TestCase):
    def test_configuration_counts(self) -> None:
        counts = {level: sum(run.level == level for run in RUNS) for level in EXPECTED_TASKS}
        self.assertEqual(counts, {"L0": 4, "L1": 2, "L2": 4, "L3": 12})
        self.assertEqual(EXPECTED_PAIRED, 1891)


if __name__ == "__main__":
    unittest.main()
