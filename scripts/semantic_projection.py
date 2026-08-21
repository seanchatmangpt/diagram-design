#!/usr/bin/env python3
"""Deterministic semantic-graph projection with a non-authoritative receipt.

Diagram Design is a rendering surface.  This utility makes that boundary
machine-checkable: every projected node must already exist in the supplied
source graph, edges are retained only when both endpoints survive selection,
and the emitted receipt binds source and projection identities without
claiming source admission or actuation authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence


class ProjectionRefusal(ValueError):
    """Raised when a requested projection would manufacture semantic content."""


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _index_nodes(graph: Mapping[str, Any]) -> Dict[str, Mapping[str, Any]]:
    nodes = graph.get("nodes")
    if not isinstance(nodes, list):
        raise ProjectionRefusal("source graph must contain a nodes array")

    indexed: Dict[str, Mapping[str, Any]] = {}
    for node in nodes:
        if not isinstance(node, Mapping):
            raise ProjectionRefusal("every node must be an object")
        node_id = node.get("id")
        if not isinstance(node_id, str) or not node_id:
            raise ProjectionRefusal("every node must have a non-empty string id")
        if node_id in indexed:
            raise ProjectionRefusal("duplicate source node id: {}".format(node_id))
        indexed[node_id] = node
    return indexed


def project_graph(
    graph: Mapping[str, Any],
    selected_ids: Iterable[str],
) -> Dict[str, Any]:
    """Project a supplied graph without inventing nodes or relationships.

    Source admission is intentionally outside this function.  The returned
    receipt therefore reports ``PARTIAL_ALIVE`` even though the projection
    computation itself is deterministic and verified against source identity.
    """

    indexed = _index_nodes(graph)
    requested = list(dict.fromkeys(selected_ids))
    if not all(isinstance(node_id, str) and node_id for node_id in requested):
        raise ProjectionRefusal("selection must contain non-empty string node ids")

    missing = [node_id for node_id in requested if node_id not in indexed]
    if missing:
        raise ProjectionRefusal(
            "projection requested unknown node ids: {}".format(", ".join(missing))
        )

    selected = set(requested)
    nodes: List[Mapping[str, Any]] = [indexed[node_id] for node_id in requested]

    source_edges = graph.get("edges", [])
    if not isinstance(source_edges, list):
        raise ProjectionRefusal("source graph edges must be an array")

    edges: List[Mapping[str, Any]] = []
    for edge in source_edges:
        if not isinstance(edge, Mapping):
            raise ProjectionRefusal("every edge must be an object")
        source = edge.get("source")
        target = edge.get("target")
        if not isinstance(source, str) or not isinstance(target, str):
            raise ProjectionRefusal("every edge must name string source and target ids")
        if source not in indexed or target not in indexed:
            raise ProjectionRefusal(
                "source graph contains dangling edge {} -> {}".format(source, target)
            )
        if source in selected and target in selected:
            edges.append(edge)

    projection = {
        "nodes": nodes,
        "edges": edges,
    }
    receipt = {
        "status": "PARTIAL_ALIVE",
        "source_admission_required": True,
        "source_digest": _digest(graph),
        "projection_digest": _digest(projection),
        "selected_node_ids": requested,
        "omitted_node_count": len(indexed) - len(requested),
        "invented_node_count": 0,
        "actuation_authority": False,
    }
    return {"projection": projection, "receipt": receipt}


def _load_ids(path: Path) -> Sequence[str]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ProjectionRefusal("selection file must be a JSON array of node ids")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Project a semantic graph and emit a deterministic non-authoritative receipt."
    )
    parser.add_argument("graph", type=Path, help="JSON graph containing nodes and edges")
    parser.add_argument("selection", type=Path, help="JSON array of selected node ids")
    parser.add_argument("--output", type=Path, help="write JSON to this path instead of stdout")
    args = parser.parse_args()

    graph = json.loads(args.graph.read_text(encoding="utf-8"))
    if not isinstance(graph, Mapping):
        raise ProjectionRefusal("source graph must be a JSON object")
    result = project_graph(graph, _load_ids(args.selection))
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
