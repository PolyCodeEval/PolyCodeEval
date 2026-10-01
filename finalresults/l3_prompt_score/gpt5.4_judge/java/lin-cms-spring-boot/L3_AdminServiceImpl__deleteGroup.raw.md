{
  "score": 5.0,
  "reason": "The description matches the implementation very closely and covers all meaningful behavior: fetching root and guest group IDs, forbidding deletion of those special groups with the correct error codes, validating existence via the helper, checking whether the group still has users, throwing the correct forbidden error when non-empty, and returning the result of `groupService.removeById(id)`. It is also sufficiently complete to implement the function accurately.",
  "missing_functionality": [],
  "incorrect_or_misleading_points": [],
  "complete_enough": true
}
