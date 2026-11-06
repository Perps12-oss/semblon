"""Related objects and people for one photograph.

Reads the existing graph. Does not write nodes, edges, faces, or persons.
"""

from __future__ import annotations

import sqlite3

EXPLORE_LIMIT = 240
_MAX_TARGETS = 200

NOT_IN_MEMORY = (
    "This photo is not in memory yet. Related objects appear after visual labels are saved."
)
PEOPLE_FROM_DESK = (
    "This photo is not in memory yet. People shown here come from the People desk."
)
GROUPING_NOT_RUN = "Same-object grouping has not been run for this archive."
PEOPLE_UNLINKED = "People in this photo are not linked in memory yet."
LABELS_NOT_SAVED = "Visual labels have not been saved for this photo."
EMPTY_OBJECTS = "No related objects found yet."
EMPTY_PEOPLE = "No people found for this photo yet."
EMPTY_RELATIONSHIPS = "No shared appearances recorded yet."
SHOWING_CAP = "Showing the first 200 related items."


def related_for_media(conn: sqlite3.Connection, media_id: str) -> dict:
    """One photo's tags, object groups, people, and shared appearances."""
    media_id = str(media_id or "").strip()
    if not media_id or not _has_table(conn, "brain_nodes"):
        return _empty(media_id, NOT_IN_MEMORY)

    photo_id = _photo_id(conn, media_id)
    faces = _faces_on_media(conn, media_id)
    edges = _outgoing(conn, photo_id) if photo_id is not None else []

    tags: list[dict] = []
    objects: list[dict] = []
    face_nodes: list[dict] = []
    for edge in edges:
        kind = edge["node_type"]
        if kind == "Tag":
            if edge["status"] == "retracted":
                continue
            tags.append(edge)
        elif kind == "ObjectCluster":
            objects.append(edge)
        elif kind == "FaceCluster":
            face_nodes.append(edge)

    truncated = False
    if len(tags) + len(objects) + len(face_nodes) > _MAX_TARGETS:
        truncated = True
        budget = _MAX_TARGETS
        tags = tags[:budget]
        budget -= len(tags)
        objects = objects[: max(budget, 0)]
        budget -= len(objects)
        face_nodes = face_nodes[: max(budget, 0)]

    target_ids = [int(row["id"]) for row in tags + objects + face_nodes]
    counts = _photo_counts(conn, target_ids)

    object_ids = [int(row["id"]) for row in objects]
    same_as = _same_as_for(conn, object_ids)
    claims = _human_claims(conn, [int(row["id"]) for row in same_as])

    object_cards: list[dict] = []
    for edge in objects:
        node_id = int(edge["id"])
        partners = [
            row
            for row in same_as
            if node_id in (int(row["source_node_id"]), int(row["target_node_id"]))
        ]
        count = counts.get((node_id, "HAS_OBJECT"), 0)
        if not partners:
            object_cards.append(
                _object_card(edge, None, None, count)
            )
            continue
        for partner in partners:
            object_cards.append(
                _object_card(edge, partner, claims.get(int(partner["id"])), count)
            )
    if len(object_cards) == 1:
        object_cards[0]["title"] = "Similar object"
    else:
        for index, card in enumerate(object_cards, start=1):
            card["title"] = f"Similar object {index}"

    tag_cards = [_tag_card(edge, counts.get((int(edge["id"]), "HAS_TAG"), 0)) for edge in tags]
    people = _people_cards(conn, media_id, face_nodes, faces, counts)
    relationships = _relationship_rows(conn, tags, object_cards)

    coverage: list[str] = []
    if photo_id is None and not faces:
        coverage.append(NOT_IN_MEMORY)
    elif photo_id is None and faces:
        coverage.append(PEOPLE_FROM_DESK)
    else:
        if not tags and not objects and not _has_observation(conn, media_id):
            coverage.append(LABELS_NOT_SAVED)
        if tags and not objects and not _any_object_clusters(conn):
            coverage.append(GROUPING_NOT_RUN)
    if faces and not face_nodes:
        coverage.append(PEOPLE_UNLINKED)
    if truncated:
        coverage.append(SHOWING_CAP)

    payload = _empty(media_id, " ".join(coverage))
    payload["processed"] = photo_id is not None or bool(faces)
    payload["objects"] = tag_cards + object_cards
    payload["people"] = people
    payload["relationships"] = relationships
    payload["objectsNote"] = "" if payload["objects"] else EMPTY_OBJECTS
    payload["peopleNote"] = "" if payload["people"] else EMPTY_PEOPLE
    payload["relationshipsNote"] = "" if payload["relationships"] else EMPTY_RELATIONSHIPS
    payload["empty"] = not (
        payload["objects"] or payload["people"] or payload["relationships"]
    )
    return payload


def photos_for_related(conn: sqlite3.Connection, item: dict) -> list[dict]:
    """Photographs for one related item, oldest file time first. Bounded."""
    kind = str(item.get("kind") or "")
    if kind == "tag":
        return _photos_for_edge(conn, "HAS_TAG", int(item.get("nodeId") or 0))
    if kind == "object":
        return _photos_for_edge(conn, "HAS_OBJECT", int(item.get("nodeId") or 0))
    if kind != "person":
        return []
    if item.get("inMemory") and int(item.get("nodeId") or 0):
        linked = _photos_for_edge(conn, "HAS_FACE", int(item["nodeId"]))
        if linked:
            return linked
    subject = str(item.get("subject") or "")
    if item.get("unassigned"):
        return _photos_for_face(conn, subject)
    return _photos_for_cluster(conn, subject)


def _empty(media_id: str, coverage: str) -> dict:
    return {
        "mediaId": media_id,
        "processed": False,
        "coverage": coverage,
        "empty": True,
        "objects": [],
        "people": [],
        "relationships": [],
        "objectsNote": EMPTY_OBJECTS,
        "peopleNote": EMPTY_PEOPLE,
        "relationshipsNote": EMPTY_RELATIONSHIPS,
    }


def _card(**fields) -> dict:
    row = {
        "key": "",
        "kind": "",
        "title": "",
        "state": "unresolved",
        "stateLabel": "",
        "count": 0,
        "countLabel": "",
        "thumb": "",
        "nodeId": 0,
        "partnerId": 0,
        "canCorrect": False,
        "subject": "",
        "faceId": "",
        "inMemory": False,
        "named": False,
        "unassigned": False,
    }
    row.update(fields)
    return row


def _has_table(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return row is not None


def _photo_id(conn: sqlite3.Connection, media_id: str) -> int | None:
    row = conn.execute(
        "SELECT id FROM brain_nodes WHERE node_type='Photo' AND label=?",
        (media_id,),
    ).fetchone()
    if row is None:
        return None
    return int(row["id"])


def _outgoing(conn: sqlite3.Connection, photo_id: int) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """
            SELECT e.edge_type, n.id, n.node_type, n.label, n.status
              FROM brain_edges e
              JOIN brain_nodes n ON n.id = e.target_node_id
             WHERE e.source_node_id = ?
               AND e.edge_type IN ('HAS_TAG', 'HAS_OBJECT', 'HAS_FACE')
             ORDER BY n.node_type, n.label, n.id
            """,
            (int(photo_id),),
        ).fetchall()
    )


def _photo_counts(conn: sqlite3.Connection, target_ids: list[int]) -> dict[tuple[int, str], int]:
    if not target_ids:
        return {}
    marks, params = _in(target_ids)
    rows = conn.execute(
        f"""
        SELECT target_node_id, edge_type, COUNT(*)
          FROM brain_edges
         WHERE edge_type IN ('HAS_TAG', 'HAS_OBJECT', 'HAS_FACE')
           AND target_node_id IN ({marks})
         GROUP BY target_node_id, edge_type
        """,
        params,
    ).fetchall()
    return {(int(row[0]), str(row[1])): int(row[2]) for row in rows}


def _same_as_for(conn: sqlite3.Connection, object_ids: list[int]) -> list[sqlite3.Row]:
    if not object_ids:
        return []
    marks, params = _in(object_ids)
    return list(
        conn.execute(
            f"""
            SELECT id, source_node_id, target_node_id, contradiction_state
              FROM brain_edges
             WHERE edge_type = 'SAME_AS'
               AND (
                    source_node_id IN ({marks})
                 OR target_node_id IN ({marks})
               )
             ORDER BY id
            """,
            (*params, *params),
        ).fetchall()
    )


def _human_claims(conn: sqlite3.Connection, edge_ids: list[int]) -> dict[int, str]:
    if not edge_ids or not _has_table(conn, "brain_evidence"):
        return {}
    marks, params = _in(edge_ids)
    rows = conn.execute(
        f"""
        SELECT edge_id, claim_key
          FROM brain_evidence
         WHERE edge_id IN ({marks})
           AND claim_key LIKE 'human:%'
         ORDER BY created_at DESC, id DESC
        """,
        params,
    ).fetchall()
    latest: dict[int, str] = {}
    for row in rows:
        edge_id = int(row["edge_id"])
        if edge_id not in latest:
            latest[edge_id] = str(row["claim_key"])
    return latest


def _tag_state(status: str) -> tuple[str, str]:
    if status == "confirmed":
        return "confirmed", "Confirmed"
    if status == "tentative":
        return "suggested", "Seen in more than one photo"
    if status == "candidate":
        return "suggested", "Only seen here"
    if status == "contradicted":
        return "contradicted", "Marked as not the same"
    return "unresolved", "Not confirmed"


def _tag_card(edge: sqlite3.Row, count: int) -> dict:
    state, label = _tag_state(str(edge["status"] or ""))
    node_id = int(edge["id"])
    title = str(edge["label"] or "").strip() or "Untitled label"
    return _card(
        key=f"tag:{node_id}",
        kind="tag",
        title=title,
        state=state,
        stateLabel=label,
        count=int(count),
        countLabel=_appears(count),
        nodeId=node_id,
    )


def _object_card(edge: sqlite3.Row, partner, claim: str | None, count: int) -> dict:
    node_id = int(edge["id"])
    partner_id = 0
    if partner is not None:
        source = int(partner["source_node_id"])
        target = int(partner["target_node_id"])
        partner_id = target if source == node_id else source
        state, label = _pair_state(str(partner["contradiction_state"] or ""), claim)
        key = f"object:{node_id}:{partner_id}"
        correct = True
    else:
        state, label = "suggested", "Seen in this photo"
        key = f"object:{node_id}"
        correct = False
    return _card(
        key=key,
        kind="object",
        title="Similar object",
        state=state,
        stateLabel=label,
        count=int(count),
        countLabel=_appears(count),
        nodeId=node_id,
        partnerId=int(partner_id),
        canCorrect=correct,
    )


def _pair_state(contradiction_state: str, claim: str | None) -> tuple[str, str]:
    if claim == "human:same_object":
        return "confirmed", "You said these are the same object"
    if claim == "human:different_object":
        return "contradicted", "You said these are different"
    if contradiction_state == "contradicted":
        return "contradicted", "Marked as not the same object"
    return "suggested", "Possible visual match"


def _people_cards(
    conn: sqlite3.Connection,
    media_id: str,
    face_nodes: list,
    faces: list[dict],
    counts: dict[tuple[int, str], int],
) -> list[dict]:
    cluster_ids: list[str] = []
    for node in face_nodes:
        label = str(node["label"] or "")
        if label:
            cluster_ids.append(label)
    for face in faces:
        if face["cluster_id"]:
            cluster_ids.append(face["cluster_id"])
    names = _names_for_clusters(conn, list(dict.fromkeys(cluster_ids)))
    face_by_cluster: dict[str, dict] = {}
    for face in faces:
        cid = face["cluster_id"]
        if cid and cid not in face_by_cluster:
            face_by_cluster[cid] = face

    people: list[dict] = []
    seen: set[str] = set()
    for node in face_nodes:
        subject = str(node["label"] or "")
        if not subject or subject in seen:
            continue
        seen.add(subject)
        face = face_by_cluster.get(subject)
        display = names.get(subject) or (face["display_name"] if face else "")
        named = bool(display)
        count = counts.get((int(node["id"]), "HAS_FACE"), 0)
        people.append(
            _card(
                key=f"person:{subject}",
                kind="person",
                title=display or "Unnamed person",
                state="confirmed" if named else "suggested",
                stateLabel=(
                    "Named in People"
                    if named
                    else "A group in People. Not a name until you give one."
                ),
                count=int(count),
                countLabel=_appears(count),
                nodeId=int(node["id"]),
                subject=subject,
                faceId=face["face_id"] if face else "",
                inMemory=True,
                named=named,
            )
        )

    unlinked: list[str] = []
    for face in faces:
        cid = face["cluster_id"]
        if not cid or cid in seen:
            continue
        seen.add(cid)
        unlinked.append(cid)
        display = names.get(cid) or face["display_name"]
        named = bool(display)
        people.append(
            _card(
                key=f"person:{cid}",
                kind="person",
                title=display or "Unnamed person",
                state="not_linked",
                stateLabel="In this photo. Not linked in memory yet.",
                count=0,
                countLabel="In this photo",
                subject=cid,
                faceId=face["face_id"],
                inMemory=False,
                named=named,
            )
        )
    extra_counts = _cluster_photo_counts(conn, unlinked)
    for card in people:
        if card["inMemory"] or card["unassigned"]:
            continue
        count = extra_counts.get(card["subject"], 0)
        if count:
            card["count"] = int(count)
            card["countLabel"] = _appears(count)

    for face in faces:
        if face["cluster_id"]:
            continue
        people.append(
            _card(
                key=f"unassigned:{face['face_id']}",
                kind="person",
                title=face["display_name"] or "A face in this photo",
                state="not_linked",
                stateLabel="In this photo. Not linked in memory yet.",
                count=1,
                countLabel="In this photo",
                subject=face["face_id"],
                faceId=face["face_id"],
                inMemory=False,
                named=bool(face["display_name"]),
                unassigned=True,
            )
        )
    return people


def _faces_on_media(conn: sqlite3.Connection, media_id: str) -> list[dict]:
    if not _has_table(conn, "faces") or not _has_table(conn, "observations"):
        return []
    rows = conn.execute(
        """
        SELECT f.face_id, f.cluster_id, p.display_name
          FROM faces f
          JOIN observations o ON o.observation_id = f.observation_id
          LEFT JOIN persons p
            ON p.person_id = f.person_id AND p.status = 'active'
         WHERE o.media_id = ? AND f.status = 'ok'
         ORDER BY f.face_id
        """,
        (media_id,),
    ).fetchall()
    found = []
    for row in rows:
        found.append(
            {
                "face_id": str(row["face_id"]),
                "cluster_id": str(row["cluster_id"] or ""),
                "display_name": str(row["display_name"] or "").strip(),
            }
        )
    return found


def _names_for_clusters(conn: sqlite3.Connection, cluster_ids: list[str]) -> dict[str, str]:
    if not cluster_ids or not _has_table(conn, "cluster_person"):
        return {}
    marks, params = _in(cluster_ids)
    rows = conn.execute(
        f"""
        SELECT cp.cluster_id, p.display_name
          FROM cluster_person cp
          JOIN persons p ON p.person_id = cp.person_id
         WHERE p.status = 'active' AND cp.cluster_id IN ({marks})
         ORDER BY p.display_name
        """,
        params,
    ).fetchall()
    names: dict[str, str] = {}
    for row in rows:
        cid = str(row["cluster_id"])
        display = str(row["display_name"] or "").strip()
        if cid not in names and display:
            names[cid] = display
    return names


def _cluster_photo_counts(conn: sqlite3.Connection, cluster_ids: list[str]) -> dict[str, int]:
    if not cluster_ids or not _has_table(conn, "faces"):
        return {}
    marks, params = _in(cluster_ids)
    rows = conn.execute(
        f"""
        SELECT f.cluster_id, COUNT(DISTINCT o.media_id)
          FROM faces f
          JOIN observations o ON o.observation_id = f.observation_id
         WHERE f.status = 'ok' AND f.cluster_id IN ({marks})
         GROUP BY f.cluster_id
        """,
        params,
    ).fetchall()
    return {str(row[0]): int(row[1]) for row in rows}


def _relationship_rows(conn: sqlite3.Connection, tags: list, object_cards: list[dict]) -> list[dict]:
    rows: list[dict] = []
    tag_ids = [int(edge["id"]) for edge in tags]
    labels = {int(edge["id"]): str(edge["label"] or "") for edge in tags}
    if len(tag_ids) >= 2:
        marks, params = _in(tag_ids)
        pairs = conn.execute(
            f"""
            SELECT e.support_count, a.id, b.id, a.label, b.label
              FROM brain_edges e
              JOIN brain_nodes a ON a.id = e.source_node_id
              JOIN brain_nodes b ON b.id = e.target_node_id
             WHERE e.edge_type = 'CO_OCCURS'
               AND a.id IN ({marks})
               AND b.id IN ({marks})
             ORDER BY e.support_count DESC, a.label, b.label
            """,
            (*params, *params),
        ).fetchall()
        for pair in pairs:
            support = int(pair["support_count"])
            if support <= 0:
                continue
            left = str(pair[3] or labels.get(int(pair[1]), "")).strip()
            right = str(pair[4] or labels.get(int(pair[2]), "")).strip()
            if not left or not right:
                continue
            rows.append(
                {
                    "key": f"with:{int(pair[1])}:{int(pair[2])}",
                    "title": f"{left} and {right}",
                    "detail": _together(support),
                    "state": "suggested",
                }
            )
    for card in object_cards:
        if not card.get("partnerId"):
            continue
        rows.append(
            {
                "key": str(card["key"]),
                "title": str(card["title"]),
                "detail": str(card["stateLabel"]),
                "state": str(card["state"]),
            }
        )
    return rows


def _photos_for_edge(conn: sqlite3.Connection, edge_type: str, node_id: int) -> list[dict]:
    if node_id <= 0:
        return []
    rows = conn.execute(
        """
        SELECT m.media_id
          FROM brain_edges e
          JOIN brain_nodes photo ON photo.id = e.source_node_id
          JOIN media m ON m.media_id = photo.label
         WHERE e.edge_type = ?
           AND e.target_node_id = ?
           AND photo.node_type = 'Photo'
         ORDER BY m.mtime_ns IS NULL, m.mtime_ns, m.path
         LIMIT ?
        """,
        (edge_type, int(node_id), int(EXPLORE_LIMIT)),
    ).fetchall()
    return [{"mediaId": str(row["media_id"])} for row in rows]


def _photos_for_cluster(conn: sqlite3.Connection, cluster_id: str) -> list[dict]:
    if not cluster_id or not _has_table(conn, "faces"):
        return []
    rows = conn.execute(
        """
        SELECT m.media_id
          FROM faces f
          JOIN observations o ON o.observation_id = f.observation_id
          JOIN media m ON m.media_id = o.media_id
         WHERE f.cluster_id = ? AND f.status = 'ok'
         GROUP BY m.media_id
         ORDER BY MIN(m.mtime_ns) IS NULL, MIN(m.mtime_ns), MIN(m.path)
         LIMIT ?
        """,
        (cluster_id, int(EXPLORE_LIMIT)),
    ).fetchall()
    return [{"mediaId": str(row["media_id"])} for row in rows]


def _photos_for_face(conn: sqlite3.Connection, face_id: str) -> list[dict]:
    if not face_id or not _has_table(conn, "faces"):
        return []
    rows = conn.execute(
        """
        SELECT m.media_id
          FROM faces f
          JOIN observations o ON o.observation_id = f.observation_id
          JOIN media m ON m.media_id = o.media_id
         WHERE f.face_id = ? AND f.status = 'ok'
         ORDER BY m.mtime_ns IS NULL, m.mtime_ns, m.path
         LIMIT ?
        """,
        (face_id, int(EXPLORE_LIMIT)),
    ).fetchall()
    return [{"mediaId": str(row["media_id"])} for row in rows]


def _has_observation(conn: sqlite3.Connection, media_id: str) -> bool:
    if not _has_table(conn, "brain_observations"):
        return False
    row = conn.execute(
        "SELECT 1 FROM brain_observations WHERE media_id=? LIMIT 1",
        (media_id,),
    ).fetchone()
    return row is not None


def _any_object_clusters(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM brain_nodes WHERE node_type='ObjectCluster' LIMIT 1"
    ).fetchone()
    return row is not None


def _appears(count: int) -> str:
    n = int(count)
    if n <= 0:
        return "No photographs linked yet"
    if n == 1:
        return "Appears in 1 photograph"
    return f"Appears in {n} photographs"


def _together(support: int) -> str:
    n = int(support)
    if n >= 3:
        lead = f"Often in the same photographs ({n})."
    elif n == 1:
        lead = "Appears together in 1 photograph."
    else:
        lead = f"Appears together in {n} photographs."
    return lead + " This is not a claim about who owns them."


def _in(values: list) -> tuple[str, list]:
    return ",".join("?" for _ in values), list(values)
