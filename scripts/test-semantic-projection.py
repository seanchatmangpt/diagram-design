#!/usr/bin/env python3

import unittest

from semantic_projection import (
    CHATMAN_CONTROL_PLANE_SHA,
    ProjectionRefusal,
    chatman_git_subject,
    project_graph,
)


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

SHA = "0123456789abcdef0123456789abcdef01234567"


class SemanticProjectionTests(unittest.TestCase):
    def test_projection_preserves_source_identity_without_claiming_admission(self):
        result = project_graph(GRAPH, ["ontology:Customer", "ontology:Order"])
        projection = result["projection"]
        receipt = result["receipt"]
        self.assertEqual(
            [node["id"] for node in projection["nodes"]],
            ["ontology:Customer", "ontology:Order"],
        )
        self.assertEqual([edge["id"] for edge in projection["edges"]], ["edge:places"])
        self.assertEqual(receipt["invented_node_count"], 0)
        self.assertEqual(receipt["status"], "PARTIAL_ALIVE")
        self.assertTrue(receipt["source_admission_required"])
        self.assertFalse(receipt["actuation_authority"])
        self.assertEqual(receipt["chatman"]["standing"], "UNKNOWN")
        self.assertFalse(receipt["chatman"]["subject_bound"])
        self.assertFalse(receipt["chatman"]["may_actuate"])

    def test_exact_subject_allows_only_partial_alive_in_chatman(self):
        subject = chatman_git_subject("repository:source-ontology", SHA)
        result = project_graph(
            GRAPH,
            ["ontology:Customer", "ontology:Order"],
            chatman_subject=subject,
        )
        chatman = result["receipt"]["chatman"]
        self.assertTrue(chatman["subject_bound"])
        self.assertEqual(chatman["subject"], subject)
        self.assertEqual(chatman["standing"], "PARTIAL_ALIVE")
        self.assertEqual(chatman["authority"], "observe")
        self.assertFalse(chatman["may_actuate"])
        self.assertTrue(chatman["receipt_required_for_do"])
        self.assertTrue(chatman["source_admission_required"])

    def test_chatman_control_plane_pin_is_exact(self):
        subject = chatman_git_subject("repository:source-ontology", SHA)
        result = project_graph(GRAPH, ["ontology:Customer"], chatman_subject=subject)
        chatman = result["receipt"]["chatman"]
        self.assertEqual(
            chatman["control_plane_sha"],
            "9e720d51f1a36f2ddae42dbd917eb921eb4db733",
        )
        self.assertEqual(chatman["control_plane_sha"], CHATMAN_CONTROL_PLANE_SHA)
        self.assertEqual(chatman["ecosystem_id"], "ecosystem:chatman")

    def test_invalid_chatman_exact_subject_is_refused(self):
        with self.assertRaises(ProjectionRefusal):
            chatman_git_subject("repository:source-ontology", "bad")
        with self.assertRaises(ProjectionRefusal):
            chatman_git_subject("SourceOntology", SHA)
        with self.assertRaises(ProjectionRefusal):
            chatman_git_subject("repository:sémantique", SHA)

    def test_unknown_node_is_refused_instead_of_invented(self):
        with self.assertRaises(ProjectionRefusal):
            project_graph(GRAPH, ["ontology:Customer", "invented:Thing"])

    def test_non_string_selection_is_refused(self):
        with self.assertRaises(ProjectionRefusal):
            project_graph(GRAPH, ["ontology:Customer", 42])

    def test_dangling_source_edge_is_refused(self):
        graph = dict(GRAPH)
        graph["edges"] = [
            {"source": "ontology:Customer", "target": "missing:Order"}
        ]
        with self.assertRaises(ProjectionRefusal):
            project_graph(graph, ["ontology:Customer"])

    def test_receipt_is_deterministic(self):
        subject = chatman_git_subject("repository:source-ontology", SHA)
        first = project_graph(
            GRAPH,
            ["ontology:Order", "ontology:Invoice"],
            chatman_subject=subject,
        )
        second = project_graph(
            GRAPH,
            ["ontology:Order", "ontology:Invoice"],
            chatman_subject=subject,
        )
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
