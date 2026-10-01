{
  "score": 4.8,
  "reason": "The description matches the implementation very closely at both file and function level, including most exact control flow, SQL construction, error handling, printed messages, and even unusual behaviors like `check_select` returning true on prepare failure and only finalizing on the row-found path. It is also detailed enough to reconstruct nearly the entire file faithfully. Only a few minor implementation details are omitted or slightly overgeneralized, but none substantially undermine reconstructability.",
  "missing_functionality": [
    "The description does not mention that `PeopleManagement::~PeopleManagement()` closes the SQLite database with `sqlite3_close(db)`, though this function is present in the file skeleton and implementation.",
    "The description for school insertion says only `-name` is accepted, but does not explicitly mention that extra options are effectively ignored rather than rejected in the implementation.",
    "The search description does not explicitly call out that school searches with an empty accepted-predicate set can still produce `select ID, name from school where;`, though top-level nonempty options usually prevent this."
  ],
  "incorrect_or_misleading_points": [
    "In `validate_options`, the description says targets must be required for any subcommand found in the global commands collection, which is correct, but it does not preserve the exact formatting typo in the CRUD unsupported-target message: `Only 'person', 'school'are supported.`",
    "The file-level description says the file 'defines PeopleManagement database behavior for initializing the SQLite database and schema files, checking whether records exist, and performing add, search, delete, update, and mentorship operations' but does not mention the callback-based row printing helper, which is part of the implementation flow.",
    "The add description for school could be read as strict validation of only `-name`, while the implementation merely checks presence of `-name` and does not reject additional options."
  ],
  "complete_enough": true
}
