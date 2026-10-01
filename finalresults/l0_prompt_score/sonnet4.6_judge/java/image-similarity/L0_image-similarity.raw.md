# L0 Prompt Review: image-similarity

## Summary

The image-similarity prompt is well-specified for the ImageHistogram and ImagePHash classes with clear similarity thresholds and algorithm properties.

## Completeness (4.5)
ImageHistogram (match returning Bhattacharyya coefficient in [0,1], >= 0.8 for similar, >= 0.99 for same image, symmetry) and ImagePHash (distance as Hamming distance >= 0, < 10 for similar, symmetry, self-distance = 0, custom constructor with any positive integers) are covered. The CLI workflow is mentioned. Minor omission: no detail on the input file format for CLI batch processing.

## Unambiguity (4.5)
Similarity thresholds (>= 0.8 for histogram, < 10 for phash), range constraints, symmetry, and self-identity properties are explicitly stated. Both default and parameterized constructors are specified. 'Any positive integer values' for ImagePHash(size, smallerSize) is clear.

## Testability (4.0)
Tests verify same-image scores, cross-image thresholds, symmetry, range constraints, and custom constructor behavior. These are blackbox-verifiable from the prompt. However, tests rely on specific image files (imgs/1.jpg through 4.jpg) being present in the test environment — an infrastructure dependency not mentioned in the prompt but part of test setup rather than prompt quality.

## Consistency (4.5)
No conflicts. Bhattacharyya coefficient specification and Hamming distance specification match test assertions. The custom ImagePHash(32, 8) constructor accepting positive integers is consistent with the spec.

## Overall: 4.38
