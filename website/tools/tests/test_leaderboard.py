from __future__ import annotations

import unittest

from tools.exporters.leaderboard import LEVEL_COUNTS, RELEASE_VERSION


class LeaderboardContractTest(unittest.TestCase):
    def test_release_contract(self) -> None:
        self.assertEqual(RELEASE_VERSION, "pce-1.0")
        self.assertEqual(LEVEL_COUNTS, {"L0": 58, "L1": 58, "L2": 150, "L3": 2324})


if __name__ == "__main__":
    unittest.main()
