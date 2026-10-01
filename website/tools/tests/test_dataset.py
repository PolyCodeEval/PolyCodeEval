from __future__ import annotations

import unittest

from tools.exporters.dataset import difficulty


class DatasetHelpersTest(unittest.TestCase):
    def test_difficulty_boundaries(self) -> None:
        self.assertEqual(difficulty("", 499), "Small")
        self.assertEqual(difficulty("", 500), "Medium")
        self.assertEqual(difficulty("", 2000), "Large")
        self.assertEqual(difficulty("", 6000), "Very Large")


if __name__ == "__main__":
    unittest.main()
