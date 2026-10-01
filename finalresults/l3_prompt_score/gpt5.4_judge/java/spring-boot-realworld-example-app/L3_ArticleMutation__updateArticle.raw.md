{
  "score": 5.0,
  "reason": "The description matches the implementation very closely. It correctly states that the function looks up the article by slug, requires an authenticated user, checks write authorization, updates the article via the command service using title/body/description from the input, and returns a GraphQL mutation result with an empty ArticlePayload and the updated article stored in local context. This is also complete enough to reproduce the essential behavior of the function.",
  "missing_functionality": [],
  "incorrect_or_misleading_points": [],
  "complete_enough": true
}
