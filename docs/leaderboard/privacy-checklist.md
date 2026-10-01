# Privacy and Publication Checklist

A leaderboard Pull Request is public. Git history preserves removed content after
the initial push. Complete this checklist before publishing a branch.

## Required review

- [ ] The submission contains native evaluation results, one `submission.json`,
  and optional text logs only.
- [ ] Generated projects, completed files, function bodies, and raw model output
  archives are absent.
- [ ] `.env` files, credentials, API keys, access tokens, cookies, SSH material,
  and cloud configuration are absent.
- [ ] `submission.json` contains no secret in the command, notes, URLs, or
  environment fields.
- [ ] Every per-task `stdout`, `stderr`, and `error` field has been inspected or
  searched for sensitive content.
- [ ] `dimension_details`, `judge_reviews`, `inferred_commands`, and `attempts`
  have been inspected for private paths and credentials.
- [ ] Optional logs contain no secrets, private source code, personal data, or
  confidential infrastructure details.
- [ ] Absolute local paths have been removed or replaced with non-sensitive
  placeholders in metadata and optional logs.
- [ ] Public URLs do not grant write access and contain no signed query token.
- [ ] The submitter has permission to publish all included content.

## Common sensitive patterns

Search for provider keys, bearer tokens, authorization headers, private key
blocks, password assignments, connection strings, home-directory paths, internal
hostnames, email addresses, and temporary signed URLs.

Automated scanning is a secondary safeguard. The submitter remains responsible
for the content of every committed file.

## Native stdout and stderr

Native evaluator task JSON files commonly preserve `stdout` and `stderr`. These
fields support result auditing and should remain in the native record. If they
contain a credential or private datum, sanitize the source environment and rerun
the affected evaluation. Editing task records after evaluation weakens their
audit value and can make the native summary inconsistent.

## Optional logs

The `logs/` directory may be omitted. Include a log only when it helps reviewers
interpret the run.

Allowed extensions:

```text
.log .txt .json .jsonl
```

Limits:

- maximum 5 MB per file;
- maximum 20 MB for the complete `logs/` directory;
- text content only;
- no nested archive, binary executable, database, dataset, generated code, or
  dependency bundle.

Optional logs do not affect ranking.

## If sensitive content was pushed

Do not rely on a follow-up commit that deletes the file. Close the Pull Request,
remove the content from branch history, rotate every exposed credential, and open
a clean Pull Request. Notify maintainers when exposure may also affect repository
logs or cached workflow artifacts.
