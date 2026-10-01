{
  "score": 4.9,
  "reason": "The prompt description matches the implementation very closely at both file and function level. It correctly captures the authorization flows for login, group, refresh, claim extraction, header validation, LocalUser population, avatar normalization, and the exact exception mappings and error codes used in the implemented methods. It also aligns with the file-level role of cleanup through the resolver interface. The only meaningful omission is that the file also contains handleAdmin, verifyAdmin, and handleNotHandlerMethod behavior outside the five hollowed methods, which are relevant to full-file reconstruction but not part of the hollowed bodies.",
  "missing_functionality": [
    "The description does not mention the existing handleAdmin implementation, which logs in first, checks root/admin status via verifyAdmin, and throws AuthenticationException(10001) when unauthorized.",
    "The description does not mention handleNotHandlerMethod returning true.",
    "The description does not explicitly mention that verifyAdmin delegates to groupService.checkIsRootByUserId(user.getId())."
  ],
  "incorrect_or_misleading_points": [],
  "complete_enough": true
}
