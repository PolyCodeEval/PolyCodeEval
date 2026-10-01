{
  "score": 4.8,
  "reason": "The description matches the implementation very closely and covers nearly all important control flow, validation, SQL construction, and error handling. It correctly distinguishes person vs. school behavior, the required -id check, person option validation against known columns, the need for at least one non-id person field, school existence validation for person updates, SQL execution failure handling, and success return. It is also sufficiently detailed to support reimplementation. The only notable gap is that the implementation treats any non-\"person\" target as a school update path rather than explicitly validating that the target is either person or school.",
  "missing_functionality": [
    "The implementation does not validate the target string strictly; any target other than \"person\" follows the school-update branch."
  ],
  "incorrect_or_misleading_points": [
    "The description says the target type may be either a person or a school, which is slightly stronger than the implementation because the code does not reject other target strings and instead handles them as school updates."
  ],
  "complete_enough": true
}
