{
  "score": 4.8,
  "reason": "The description accurately captures all key behaviors: the conditional decorator attachment, the error raised when decorators exist on both sides of an export, the prepend-vs-assign logic, the start location resets for both classNode and exportNode, the no-op when no decorators are provided, and the unconditional return of classNode. The only minor imprecision is that the error is raised with `classNode.decorators[0]` as the location argument (pointing to the first existing decorator), not the export declaration itself — but this is a secondary detail that doesn't affect implementability.",
  "missing_functionality": [],
  "incorrect_or_misleading_points": [
    "The description says the error is for 'decorators appearing on both sides of an export declaration', which is a reasonable paraphrase, but the raise call passes `classNode.decorators[0]` as the error location — a subtle detail the description omits."
  ],
  "complete_enough": true
}
