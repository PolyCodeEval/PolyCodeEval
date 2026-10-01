# L0 Prompt Review: imapclient

## Summary

The imapclient prompt provides good coverage of the utility modules (datetime_util, fixed_offset, imap_utf7, response_types) which are the primary focus of the blackbox tests. The main IMAPClient class is described only conceptually without method-level detail, which is a notable gap for a large library.

## Strengths
- datetime_util functions described with parameter semantics (normalise flag behavior)
- format_criteria_date byte output format described with example
- Address/Envelope dataclass fields named
- SearchIds list subclass with modseq attribute described
- BodyData.create() factory method mentioned
- FixedOffset.for_system() class method mentioned

## Weaknesses
- IMAPClient class methods (select_folder, search, fetch, etc.) not described
- ValueError on invalid parse_to_datetime input not mentioned
- FixedOffset tzname format string (+HHMM) not explicitly specified
- 'dotted time' format variant for parse_to_datetime not mentioned

## Overall Assessment
Score 3.88/5.0 — adequate for utility module tests but thin on the main client class.
