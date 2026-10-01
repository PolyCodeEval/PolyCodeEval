{
  "score": 4.5,
  "reason": "The description matches the implemented logic very closely: it covers token extraction from a servlet request, the specific failure cases for missing, expired, invalid, and undecodable tokens, lookup of the user from the `identity` claim, storage of the user in handshake attributes, and success behavior. The main mismatch is that it says non-servlet requests are allowed to proceed, while the implementation actually rejects them by returning `false`. Aside from that, it is detailed enough to guide an implementation.",
  "missing_functionality": [
    "The implementation rejects non-servlet requests by returning false; this behavior is not described accurately."
  ],
  "incorrect_or_misleading_points": [
    "The description says that if the request is not a servlet HTTP request, the handshake is allowed to proceed, but the implementation returns false and rejects the handshake."
  ],
  "complete_enough": true
}
