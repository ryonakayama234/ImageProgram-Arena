"""Reviewer unit tests: no confirmation inputs or hidden answer passed to Model."""
import unittest
from dataclasses import dataclass

import numpy as np

from adapters.imageprogram_reference.cc02_arc_review import (
    _arc_points,
    _components_from_public,
    audit_continue,
    development_continue_annotation,
)


@dataclass(frozen=True)
class Node:
    node_id: str
    pixels: int
    mean_l8: float
    region: str


@dataclass(frozen=True)
class Edge:
    src: str
    dst: str
    kind: str


@dataclass(frozen=True)
class Graph:
    nodes: tuple
    edges: tuple
    candidate_set_sha256: str = "fixed-graph"


@dataclass(frozen=True)
class Decision:
    arm: str = "B"
    candidate_set_sha256: str = "fixed-graph"
    selected_nodes: tuple = ("fragment-000", "fragment-001")
    action: str = "stop"


def synthetic(index, *, include_target=True, threshold_ink=0):
    arc = _arc_points(development_continue_annotation(index).path)
    image = np.full((72, 72), 255, dtype=np.uint8)
    for x in range(10, 29):
        image[27 + index, x] = 0
    for x in range(33, 53):
        image[27 + index, x] = 0
    if include_target:
        for x, y in arc:
            image[y, x] = threshold_ink
    comps = _components_from_public(image, 200, 16)
    nodes = tuple(Node(f"fragment-{i:03d}", len(comp),
                       float(np.mean([image[y, x] for x, y in comp])),
                       "context" if min(x for x, _ in comp) >= 55 else "focus")
                  for i, comp in enumerate(comps))
    graph = Graph(nodes, ())
    return {"pixels_l8": image, "raster_digest": "test-raster"}, graph


class ArcAuditTests(unittest.TestCase):
    def test_exact_arc_lengths_and_source_bounds(self):
        for i in range(6):
            arc = _arc_points(development_continue_annotation(i).path)
            self.assertGreaterEqual(len(arc), 10)
            self.assertTrue(all(58 <= x < 72 and 0 <= y < 72 for x, y in arc))
        with self.assertRaisesRegex(ValueError, "development-index-only"):
            development_continue_annotation(6)

    def test_candidate_missing_on_weak_ink(self):
        public, graph = synthetic(3, threshold_ink=218)
        result = audit_continue(public, graph, Decision(),
                                development_continue_annotation(3))
        self.assertEqual(result["diagnostic_stage"], "P_CANDIDATE_ABSENT")
        self.assertEqual(result["arc_coverage_all_context_nodes"], 0)

    def test_edge_absence_distinguished_from_detection(self):
        public, graph = synthetic(0)
        result = audit_continue(public, graph, Decision(),
                                development_continue_annotation(0))
        self.assertEqual(result["diagnostic_stage"], "G_CONTINUATION_EDGE_ABSENT")
        self.assertEqual(result["arc_coverage_all_context_nodes"], 1)

    def test_selection_failure_and_action_correct_are_distinguished(self):
        public, graph = synthetic(0)
        graph = Graph(graph.nodes, (Edge("fragment-001", "fragment-002",
                                        "possible_continuation"),))
        ann = development_continue_annotation(0)
        self.assertEqual(audit_continue(public, graph, Decision(), ann)[
            "diagnostic_stage"], "R_SELECTION_FAILURE")
        approved = Decision(action="continue")
        result = audit_continue(public, graph, approved, ann)
        self.assertEqual(result["diagnostic_stage"],
                         "ACTION_CORRECT_PATH_EDGE_UNOBSERVED")
        self.assertEqual(result["path_edge_receipt"], "UNAVAILABLE_IN_FROZEN_V2")

    def test_mismatch_is_rejected_not_assumed(self):
        public, graph = synthetic(0)
        wrong_nodes = list(graph.nodes)
        wrong_nodes[0] = Node("fragment-000", 999, 0.0, "focus")
        bad_graph = Graph(tuple(wrong_nodes), graph.edges)
        with self.assertRaisesRegex(ValueError, "node-component-size-mismatch"):
            audit_continue(public, bad_graph, Decision(),
                           development_continue_annotation(0))
        with self.assertRaisesRegex(ValueError, "decision-graph-mismatch"):
            audit_continue(public, graph, Decision(candidate_set_sha256="bad"),
                           development_continue_annotation(0))

    def test_private_annotation_must_match_visible_pixels(self):
        public, graph = synthetic(0, include_target=False)
        with self.assertRaisesRegex(ValueError, "annotation-not-visible"):
            audit_continue(public, graph, Decision(),
                           development_continue_annotation(0))


if __name__ == "__main__":
    unittest.main()
