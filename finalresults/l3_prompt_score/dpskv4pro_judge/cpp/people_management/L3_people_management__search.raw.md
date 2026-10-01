{
  "score": 4.0,
  "reason": "The description captures the core logic accurately, including the branching on target type, option validation, SQL construction, and error handling. However, it omits the important detail that option keys are passed with a leading dash (e.g., '-name') which the implementation strips via substr(1). This detail is essential for correctly parsing options and building valid SQL. The exact header output format is also not specified, though this is a secondary detail.",
  "missing_functionality": [
    "Options map keys are prefixed with '-' which must be stripped before use as column names.",
    "The specific format of the result headers (e.g., 'id\\t\\tname\\t\\tage\\t\\tschool\\t\\ttype') is not provided."
  ],
  "incorrect_or_misleading_points": [],
  "complete_enough": false
}
