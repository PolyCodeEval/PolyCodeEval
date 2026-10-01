{
  "score": 4.8,
  "reason": "The description accurately captures all core behaviors: slug-based article lookup with `ResourceNotFoundException`, authentication check with `AuthenticationException`, authorization check with `NoAuthorizationException`, delegating the update to `articleCommandService` with title/body/description params, and returning a `DataFetcherResult` wrapping an empty `ArticlePayload` with the updated article in local context. The order of checks (article existence → authentication → authorization) is correctly described. No incorrect claims are made.",
  "missing_functionality": [],
  "incorrect_or_misleading_points": [],
  "complete_enough": true
}
