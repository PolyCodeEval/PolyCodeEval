{
  "score": 4.7,
  "reason": "The description matches the implementation very closely. It correctly covers the duplicate-TLS guard, issuing STARTTLS, validating the response with the normal OK check, wrapping the socket with TLS using the host name and optional SSL context, updating the socket and file objects, setting the starttls-done flag, and returning the first response element. The main omission is that the real function is decorated with a STARTTLS capability requirement, so unsupported servers are rejected before entering the body. The note about a default context is slightly indirect because that behavior is not implemented here explicitly, but delegated to the wrapping helper, so it is acceptable rather than clearly wrong.",
  "missing_functionality": [
    "The function is guarded by a capability check decorator requiring STARTTLS support before execution."
  ],
  "incorrect_or_misleading_points": [
    "The statement that a default SSL context may be used if the wrapping helper supports it is not enforced directly by this function body; it relies on tls.wrap_socket to handle that."
  ],
  "complete_enough": true
}
