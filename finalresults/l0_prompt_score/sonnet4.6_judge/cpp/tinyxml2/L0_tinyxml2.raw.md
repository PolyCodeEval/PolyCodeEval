# L0 Prompt Review: tinyxml2

## Summary

The tinyxml2 prompt is extremely comprehensive, listing virtually every public method of the library organized by class. The node types, visitor pattern, handle wrapper, printer API, and all mutation methods are covered. This is one of the most complete prompts in the set.

## Dimension Notes

- **Completeness (5.0):** Covers all DOM node types, XMLDocument with full error handling API, XMLElement with text/attribute/child operations, XMLPrinter with all push/open/close operations, XMLHandle for null-safe navigation, XMLVisitor for tree traversal, ShallowClone/DeepClone, CDATA support, XMLNode user data, and InsertFirstChild/InsertAfterChild/DeleteChild. Essential and non-essential API equally well covered.

- **Unambiguity (4.5):** All method names are specified, and key semantics are described (e.g., ShallowClone is pure virtual, ChildElementCount counts direct children, FirstChildElement has optional name filter). Minor: the XMLError error code type isn't explicitly mentioned as the return of Parse/QueryXxxText. The exact XML_ERROR_xxx constant names beyond XML_SUCCESS are not enumerated.

- **Testability (4.5):** All blackbox test scenarios (parse success/failure, attribute access, text, navigation, ChildElementCount, XMLHandle chains, XMLVisitor counting, CDATA, deep clone, printer) derive directly from the prompt. ErrorIDToName mapping for non-SUCCESS codes requires the error constants to be defined, which is implied but not explicitly named.

- **Consistency (4.5):** Verified against test includes (../src/tinyxml2.h). All method names used in tests match exactly. XMLHandle::FirstChildElement, XMLElement::ChildElementCount, XMLDocument::Parse, XMLDocument::ErrorIDToName all match. The 'tinyxml2' namespace usage matches.

## Overall: 4.62
