{
  "score": 4.6,
  "reason": "The description matches the implementation closely: it says the function sends the IMAP IDLE command, stores the tag for later completion, reads the immediate server response, raises an IMAPClientError if that response is anything other than no response, and otherwise returns immediately. That is essentially exactly what the code does. The main omission is that the real function is gated by a required IDLE capability decorator, which is not mentioned, but that is secondary to the core behavior.",
  "missing_functionality": [
    "Does not mention that the method is decorated with require_capability(\"IDLE\"), so it is only usable when the server advertises the IDLE capability."
  ],
  "incorrect_or_misleading_points": [],
  "complete_enough": true
}
