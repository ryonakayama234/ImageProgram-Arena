"""GRADE-only source-author geometry annotations for P02 technical fixtures.

Not imported during public PREDICT. These are NOT blind human labels,
artist-intent ground truth, or generalizable ownership annotations.
"""
# Must align exactly with public CASES order; never passed to Model.
# target stroke index, excluded competing-ink stroke index
SOURCE_STROKE_INDICES = (
    (0, 1),   # t-right
    (0, 1),   # t-left
    (1, 2),   # y-up
    (2, 1),   # y-down
    (0, 1),   # x-one
    (1, 0),   # x-two
    (0, 1),   # parallel
    (0, 1),   # near-miss
    (1, None),  # corner
    (0, 1),   # thick-t
    (0, 2),   # t-distractor
    (0, 2),   # junction-grid
)
