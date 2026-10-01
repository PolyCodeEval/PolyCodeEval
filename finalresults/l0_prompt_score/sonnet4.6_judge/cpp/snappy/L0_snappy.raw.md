# L0 Prompt Review: snappy

## Summary

The snappy prompt is thorough, listing the full C++ and C API surfaces, streaming interfaces, iovec scatter-gather operations, and the CompressionOptions struct. The format requirement for the stubs header is noted. The test suite covers string API, streaming API, and C API, all well-represented in the prompt. Minor gaps are the exact MaxCompressedLength formula and internal algorithm constraints.

## Dimension Notes

- **Completeness (4.5):** Covers Compress/Uncompress string and buffer APIs, RawCompress/RawUncompress, streaming API (Source/Sink), ByteArraySource, UncheckedByteArraySink, iovec operations (RawCompressFromIOVec, RawUncompressToIOVec, CompressFromIOVec), MaxCompressedLength, GetUncompressedLength, IsValidCompressedBuffer, IsValidCompressed, UncompressAsMuchAsPossible, C API. The snappy-stubs-public.h requirement is called out.

- **Unambiguity (4.0):** The C API signatures are explicitly shown with exact types. The CompressionOptions fields and static methods are specified. The streaming Source/Sink interfaces are described. MaxCompressedLength formula (32 + n + n/6) is not specified, though tests verify it — an implementor would need to know this.

- **Testability (4.0):** Roundtrip, compression ratio, GetUncompressedLength, invalid input rejection are all supported by the prompt's API descriptions. The MaxCompressedLength formula is what tests actually check numerically, and it's not stated in the prompt — this is a notable testability gap.

- **Consistency (4.5):** Verified against snappy.h header. CompressionOptions with level, Min/Max/DefaultCompressionLevel() matches. Compress, Uncompress, RawCompress, RawUncompress signatures match. C API types (snappy_status enum, function signatures) match snappy-c.h. No conflicts.

## Overall: 4.25
