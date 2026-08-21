#!/usr/bin/env python3

import unittest

from semantic_projection import ProjectionRefusal, project_graph


GRAPH = {
    "nodes": [
        {"id": "ontology:Customer", "label": "Customer"},
        {"id": "ontology:Order", "label": "Order"},
        {"id": "ontology:Invoice", "label": "Invoice"},
    ],
    "edges": [
        {
            "id": "edge:places",
            "source": "ontology:Customer",
            "target": "ontology:Order",
            "label": "places",
        },
        {
            "id": "edge:billed-by",
            "source": "ontology:Order",
            "target": "ontology:Invoice",
            "label": "billed by",
        },
    ],
}


class SemanticProjectionTests(unittest.TestCase):
    def test_projection_preserves_source_identity(self):
        result = project_graph(GRAPH, ["ontology:Customer", "ontology:Order"])
        projection = result["projection"]
        self.assertEqual(
            [node["id"] for node in projection["nodes"]],
            ["ontology:Customer", "ontology:Order"],
        )
        self.assertEqual([edge["id"] for edge in projection["edges"]], ["edge:places"])
        self.assertEqual(result["receipt"]["invented_node_count"], 0)
        self.assertFalse(result["receipt"]["actuation_authority"])

    def test_unknown_node_is_refused_instead_of_invented(self):
        with self.assertRaises(ProjectionRefusal):
            project_graph(GRAPH, ["ontology:Customer", "invented:Thing"])

    def test_dangling_source_edge_is_refused(self):
        graph = dict(GRAPH)
        graph["edges"] = [
            {"source": "ontology:Customer", "target": "missing:Order"}
        ]
        with self.assertRaises(ProjectionRefusal):
            project_graph(graph, ["ontology:Customer"])

    def test_receipt_is_deterministic(self):
        first = project_graph(GRAPH, ["ontology:Order", "ontology:Invoice"])
        second = project_graph(GRAPH, ["ontology:Order", "ontology:Invoice"])
        self.assertEqual(first["receipt"], second["receipt"])

    def test_selection_order_is_part_of_projection_identity(self):
        forward = project_graph(GRAPH, ["ontology:Customer", "ontology:Order"])
        reverse = project_graph(GRAPH, ["ontology:Order", "ontology:Customer"])
        self.assertNotEqual(
            forward["receipt"]["projection_digest"],
            reverse["receipt"]["projection_digest"],
        )


if __name__ == "__main__":
    unittest.main()
