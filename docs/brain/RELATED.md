# Related to this photo

**Date:** 2026-11-05  
**Branch:** `grok/related-to-photo`  
**Schema:** 12. No new tables.

A focused photograph can open **Related** in the production shell (`semblon shell` → `Table.qml`). It is not a second application, viewer, or graph.

`docs/brain/DISCOVER-DESIGN.md` does not exist and was not added. This slice is not the Discover dashboard.

## What a person can do

1. Open a photograph.
2. Choose **Related to this photo** in More…, or the same action in Ctrl+K.
3. See objects, people, and short relationship lines for that photograph.
4. Open **Photographs** for one item. The list is oldest file time first, at most 240.
5. Open any of those photographs in the existing viewer, then **Back to related**.
6. On a suggested object pair, choose **Same object** or **Not the same**.
7. On a person, choose **Open in People**. Naming, merge, split, ignore, and rule-out stay on that desk.

The top bar still shows Back, Previous, Next, Find this part again, and More…. Related is not a fifth always-visible button. **Back to related** appears only after a related photograph has been opened.

## What it reads

`semblon/brain/related.py` reads one photograph. It does not write.

| Shown as | Graph | When the graph has no row |
|---|---|---|
| Objects | `HAS_TAG`, `HAS_OBJECT` | "No related objects found yet." |
| People | `HAS_FACE`, plus existing face rows | Faces already in the archive still appear, marked not linked in memory. |
| Relationships | `CO_OCCURS`, `SAME_AS` | "No shared appearances recorded yet." |

Counts are photograph counts for those nodes, not cluster member counts. Retracted tags are hidden. Object-group labels such as `obj:pack:0` are not shown; the card says "Similar object". Co-occurrence text says it is not a claim about who owns them. A missing graph is not described as proof that nothing is related.

Card thumbnails for items on the open photograph use that photograph. Explore thumbnails use `image://archive/t/`. Face cards use `image://face/` when a face id exists.

Opening Related does not scan the library, rebuild clusters, or call `index_image_regions`. Product observe already writes region embeddings for search. BRAIN object groups stay a batch rebuild. If same-object grouping has never been run, the sheet says so.

## Object corrections

`semblon/brain/object_decisions.py`

Same object and different object are allowed only for two `ObjectCluster` nodes that already have a `SAME_AS` edge. There is no free-form pairing control.

Each new decision:

- Inserts one `brain_observations` row: capability `H-OBJ`, provider `human`, pack `same:{lo}:{hi}` or `diff:{lo}:{hi}` (a numeric suffix if that photo already has that pack).
- Inserts one `brain_evidence` row: claim `human:same_object` (`supports`) or `human:different_object` (`contradicts`), weight 1.0.
- Creates or updates the single `SAME_AS` edge between the two ids. Different sets `contradiction_state` to `contradicted` and increments `contradict_count` only when a new contradicting evidence row is inserted. Same sets the state back to `none` and does not zero `contradict_count`.
- Leaves the older evidence row in place.

Repeating the latest decision does not insert another observation. The latest human claim is what the sheet shows. A later model evidence row with a different claim key does not replace it.

`link_same_as` still deletes model `SAME_AS` edges under the existing erasure intent. Edges whose evidence `claim_key` starts with `human:` are kept, and the rebuild will not insert a model link over that pair.

These writers do not update `faces`, `persons`, or `decisions`.

## Person corrections

The sheet does not name anyone and does not assign `faces.person_id`.

`openRelatedPerson` refreshes the existing People model and selects that group. `relatedPersonDecision` returns `decide(...)`. `decide` is still the only door to `review_board` / `review.py`.

## Not in this slice

- Discover dashboard, natural-language search, graph drawing.
- Running object clustering or region-crop ingest when Related opens.
- Pairing two objects that have no `SAME_AS` suggestion yet.
- A crop thumbnail tighter than the photograph itself.
- More than 240 photographs on an item, or more than 200 items on the first sheet.
- `docs/brain/DISCOVER-DESIGN.md`.

## Tests

`tests/brain/test_related.py` covers empty and partial graphs, tag counts, hidden retracted tags, co-occurrence wording, people reads that do not write identity, explore order and the 240 cap, human same/different provenance, idempotent repeats, preserved contradictions, and `link_same_as` keeping human edges.

`tests/test_related_shell.py` opens Related through `ShellBridge`, saves a same-object decision, walks into the photograph list and back, and checks that the person slot only forwards to `decide`. The production-shell test reads the object card from the visual tree ("Similar object", "Possible visual match"). Cards are Repeaters, because a GridView of this list did not build its delegates.

`tests/test_related_journey.py` is the persisted journey. It writes one sqlite file, shuts the shell down, and opens a new shell on that file after each human step. Same is still on the card. Different leaves the contradiction in place. A later `link_same_as` on two identical centroids does not add an edge and does not clear that contradiction. Naming uses `decide`, writes a `decisions` row, and the name is on the card when Related opens again. Switching photographs and then delivering the previous read does not bring the previous labels back.

Commands and the pre-existing Settings copy failure are in `docs/BUILD-STATUS.md`.
