from __future__ import annotations

import unittest

from tools.exporters.tokens import PAPER_ACCOUNTING, normalize_usage


class TokenHelpersTest(unittest.TestCase):
    def test_paper_accounting_covers_all_website_runs(self) -> None:
        self.assertEqual(len(PAPER_ACCOUNTING), 16)
        self.assertEqual(PAPER_ACCOUNTING["l2-claude-code-sonnet"], (63.28, 61.12))
        self.assertEqual(PAPER_ACCOUNTING["l3-aligncoder-deepseek"], (71.94, 65.35))

    def test_token_aliases(self) -> None:
        self.assertEqual(
            normalize_usage({"input_tokens": 3, "output_tokens": 2, "embedding_tokens": 5}),
            {"inputTokens": 3, "outputTokens": 2, "embeddingTokens": 5},
        )


if __name__ == "__main__":
    unittest.main()
