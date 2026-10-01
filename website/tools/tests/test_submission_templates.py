from __future__ import annotations

import json
import unittest

from tools.exporters.common import ROOT
from tools.exporters.submission_templates import _template


class SubmissionSchemaTest(unittest.TestCase):
    def test_required_submission_fields(self) -> None:
        schema = json.loads(
            (ROOT / "scripts/submission/submission.schema.json").read_text(encoding="utf-8")
        )
        self.assertEqual(schema["properties"]["benchmarkVersion"]["const"], "pce-1.0")
        self.assertEqual(schema["properties"]["schemaVersion"]["const"], "2")
        self.assertIn("submitter", schema["required"])
        self.assertIn("evaluation", schema["required"])
        self.assertNotIn("submissionType", schema["properties"])

    def test_single_template_uses_execution_by_default(self) -> None:
        template = _template()
        self.assertEqual(template["level"], "L3")
        self.assertEqual(template["evaluation"]["scoringMode"], "execution")


if __name__ == "__main__":
    unittest.main()
