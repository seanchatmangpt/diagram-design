#!/usr/bin/env python3
"""Deterministic semantic-graph projection with Chatman Ecosystem evidence.

Diagram Design is a rendering surface. This utility proves that a projection
preserves supplied semantic identity without inventing nodes or relationships.
It also emits a bounded Chatman Ecosystem observation envelope pinned to the
exact control-plane contract. The envelope never grants actuation authority;
source admission, canonical receipts, replay, and Crown remain external.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence


CHATMAN_SCHEMA = "chatman-ecosystem.integration/v1"
CHATMAN_ECOSYSTEM_ID = "ecosystem:chatman"
CHATMAN_CONTROL_PLANE_REPOSITORY = "seanchatmangpt/chatman-ecosystem"
CHATMAN_CONTROL_PLANE_SHA = "9e720d51f1a36f2ddae42dbd917eb921eb4db733"
CHATMAN_REPOSITORY_ID = "repository:diagram-design"
CHATMAN_MANIFEST_PATH = Path(__file__).resolve().parent.parent / ".chatman" / "ecosystem.json"


class ProjectionRefusal(ValueError):
    """Raised when a projection or integration input violates the contract."""


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _validate_chatman_manifest() -> Dict[str, Any]:
    try:
        payload = json.loads(CHATMAN_MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProjectionRefusal("cannot load Chatman integration manifest: {}".format(exc)) from exc
    expected = {
        "schema": CHATMAN_SCHEMA,
        "ecosystem_id": CHATMAN_ECOSYSTEM_ID,
        "control_plane_repository": CHATMAN_CONTROL_PLANE_REPOSITORY,
        "control_plane_sha": CHATMAN_CONTROL_PLANE_SHA,
        "repository_id": CHATMAN_REPOSITORY_ID,
        "role": "semantic-projection",
        "authority_class": "observe",
        "do_path": "broker_only",
        "receipt_policy": "required_for_mutation",
        "exact_subject_kind": "git_commit",
        "standing_ceiling": "PARTIAL_ALIVE",
    }
    if payload != expected:
        raise ProjectionRefusal("checked-in Chatman integration manifest drifted")
    return payload


def chatman_git_subject(repository_id: str, sha: str) -> Dict[str, str]:
    """Build a canonical Chatman ``GitCommit`` exact subject."""

    valid_repository = (
        isinstance(repository_id, str)
        and repository_id.startswith("repository:")
        and len(repository_id) > len("repository:")
        and all(
            character.islower()
            or character.isdigit()
            or character in "-_"
            for character in repository_id[len("repository:") :]
        )
    )
    valid_sha = (
        isinstance(sha, str)
        and len(sha) == 40
        and all(character in "0123456789abcdefABCDEF" for character in sha)
    )
    if not valid_repository or not valid_sha:
        raise ProjectionRefusal("Chatman exact subject requires canonical repository id and 40-hex SHA")
    return {"kind": "git_commit", "repository": repository_id, "sha": sha.lower()}


def _chatman_envelope(subject: Optional[Mapping[str, str]]) -> Dict[str, Any]:
    manifest = _validate_chatman_manifest()
    if subject is not None:
        subject = chatman_git_subject(subject.get("repository", ""), subject.get("sha", ""))
    return {
        "schema": manifest["schema"],
        "ecosystem_id": manifest["ecosystem_id"],
        "control_plane_repository": manifest["control_plane_repository"],
        "control_plane_sha": manifest["control_plane_sha"],
        "authority": "observe",
        "standing": "PARTIAL_ALIVE" if subject is not None else "UNKNOWN",
        "subject_bound": subject is not None,
        "subject": subject,
        "may_actuate": False,
        "receipt_required_for_do": True,
        "source_admission_required": True,
    }


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
    chatman_subject: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    """Project a supplied graph without inventing semantic content.

    The local projection computation can be ``PARTIAL_ALIVE`` because source
    identity is preserved and verified. Chatman standing is stricter: without
    an exact subject it remains ``UNKNOWN``; with a valid exact Git subject it
    can reach only ``PARTIAL_ALIVE`` because source admission and Crown are
    owned outside this renderer.
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

    projection = {"nodes": nodes, "edges": edges}
    receipt = {
        "status": "PARTIAL_ALIVE",
        "source_admission_required": True,
        "source_digest": _digest(graph),
        "projection_digest": _digest(projection),
        "selected_node_ids": requested,
        "omitted_node_count": len(indexed) - len(requested),
        "invented_node_count": 0,
        "actuation_authority": False,
        "chatman": _chatman_envelope(chatman_subject),
    }
    return {"projection": projection, "receipt": receipt}


def _load_ids(path: Path) -> Sequence[str]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ProjectionRefusal("selection file must be a JSON array of node ids")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Project a semantic graph and emit deterministic Chatman-compatible evidence."
    )
    parser.add_argument("graph", type=Path, help="JSON graph containing nodes and edges")
    parser.add_argument("selection", type=Path, help="JSON array of selected node ids")
    parser.add_argument("--output", type=Path, help="write JSON to this path instead of stdout")
    parser.add_argument(
        "--chatman-subject-repository-id",
        help="canonical repository:<id> for the exact source subject",
    )
    parser.add_argument(
        "--chatman-subject-sha",
        help="40-hex Git SHA for the exact source subject",
    )
    args = parser.parse_args()

    if bool(args.chatman_subject_repository_id) != bool(args.chatman_subject_sha):
        raise ProjectionRefusal(
            "--chatman-subject-repository-id and --chatman-subject-sha must be supplied together"
        )
    chatman_subject = None
    if args.chatman_subject_repository_id:
        chatman_subject = chatman_git_subject(
            args.chatman_subject_repository_id,
            args.chatman_subject_sha,
        )

    graph = json.loads(args.graph.read_text(encoding="utf-8"))
    if not isinstance(graph, Mapping):
        raise ProjectionRefusal("source graph must be a JSON object")
    result = project_graph(graph, _load_ids(args.selection), chatman_subject=chatman_subject)
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
