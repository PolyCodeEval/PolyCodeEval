from __future__ import annotations

import unittest
import unittest.mock

from tools.exporters.common import Run
from tools.exporters.results import execution_record, summarize


class ResultAggregationTest(unittest.TestCase):
    def test_execution_full_pass_uses_paper_definition(self) -> None:
        run = Run("example", "L3", "Direct", "Example", "finalresults/example/summary.json")
        row = {"compile_score": 1.0, "test_pass_ratio": 1.0, "score": 1.0}

        with unittest.mock.patch("tools.exporters.results.Path.is_file", return_value=True):
            result = execution_record(run, "python/project/task", row)

        self.assertTrue(result["buildSuccess"])
        self.assertTrue(result["fullPass"])

    def test_conditional_metrics_only_use_build_successes(self) -> None:
        base = {
            "level": "L2",
            "configuration": "example",
            "method": "Direct",
            "model": "Example",
            "faithfulness": None,
            "architecture": None,
            "health": None,
            "overall": None,
        }
        rows = [
            {**base, "buildSuccess": True, "fullPass": True, "testPassRatio": 1.0, "executionScore": 1.0, "correctness": None},
            {**base, "buildSuccess": False, "fullPass": False, "testPassRatio": 0.0, "executionScore": 0.0, "correctness": None},
        ]

        result = summarize(rows, "all", "All")

        self.assertEqual(result["buildSuccessRate"], 0.5)
        self.assertEqual(result["fullPassRate"], 0.5)
        self.assertEqual(result["conditionalTestPassRatio"], 1.0)
        self.assertEqual(result["meanExecutionScore"], 0.5)


if __name__ == "__main__":
    unittest.main()
