# Rebuilt diplomacy specification

## Relations and authority

Enable `diplomacy_enabled=true`. Initial international relations remain war. Other relations are peace, nap and alliance; self marks the diagonal. Relations are symmetric, and bandits remain hostile independently.

Alliances are complete cliques. A member can negotiate for its whole current bloc. Peace or NAP between two members atomically covers all cross-bloc pairs. Peace does not revoke existing NAP promises. Alliance requires prior peace/NAP between the blocs, then synchronizes all their existing external wars, including the enemy countries' alliance blocs. Any required war violating NAP rejects the entire transaction. New declarations likewise affect whole blocs and are blocked by any cross-bloc NAP.

Leaving converts the leaving country's alliance edges to peace. Others stay allied; all existing external wars continue. Merged alliance edges expire together at the earliest of existing deadlines and the new duration, preventing silent commitment extensions. Expiry converts NAP/alliance to peace, never automatic war.

## Decisions

Default configuration, simulation hours:

- diplomacy_decision_hours = 168 (7 days).
- diplomacy_event_cooldown_hours = 0 (events immediate next military decision).
- diplomacy_proposal_hours = 168.
- diplomacy_nap_hours = 672 (4 weeks).
- diplomacy_alliance_hours = 2016 (12 weeks).

Durations are positive integers; event cooldown may be zero. Meaningful event signatures include own settlement IDs, own public relations, own healthy party/garrison/militia total in 500-person buckets, IDs of battles besieging owned settlements, and visible hostile healthy party/garrison/militia totals in 250-person buckets separately by enemy country. Visibility uses only ordinary own sensors. Configured event cooldown does not delay the regular weekly cycle or replies.

A hold action consumes the current evaluation. Initiating actions also consume it, even if subsequently rejected. Replies can be sent immediately on the next military decision, independently of the weekly gate.

## API and privacy

Command `type: diplomacy`, with action:

- propose_peace / propose_nap / propose_alliance / declare_war require integer target.
- accept / reject require string proposal_id.
- hold / leave_alliance require neither.
- Optional reason is a string or structured dictionary for audit.

World.command returns queued status. SDK Environment.step collects all countries before resolving and returns diplomatic_results. World.step also resolves pending commands before physics advances. Match logs include final country-specific receipts.

Observation.diplomacy provides enabled, supported_actions, decision_due, reply_due, incoming/outgoing private proposals, private events receipts, public_relations as a string-keyed nested matrix, alliance_components, pair-keyed treaties and configured durations. Proposals contain id, from_nation, to_nation, kind, created_hour, expires_hour and promised blocs. Omniscient host logs are not agent observations. No allied vision, private evaluations, orders, supplies, unit control, joint victory or coordinated target selection is shared.

## Simultaneous adjudication

Use one relationship snapshot for the entire decision batch. A proposal created in a batch cannot be accepted within that same batch. Changed bloc membership invalidates old offers. Rejection wins over acceptance of the same offer in one batch.

Identical complete write sets coalesce, so reciprocal identical offers do not deadlock. Compatible non-alliance overlapping writes may coexist. Different writes to any pair reject every conflicting transaction in full. Different alliance transactions touching a common country also conflict, preventing unadjudicated transitive mergers. Sorting is for reproducibility, not a first-country priority. Failed/conflicting accepted offers require a new proposal.

## Combat and extinction

Attack, siege, raid, contact, frontier targeting and stale-order handling require actual hostility. New ceasefires clear hostile orders and active raid timers against the newly nonhostile country.

Explicit simplification: a ceased war pair cancels its entire connected siege/relief engagement, preserving surviving units with no additional casualties, capture or spoils. A still-hostile third party may need to reengage. Existing allied participants alone do not trigger cancellation.

Combat ends when the surviving countries have no hostile edges. All coalition survivors retain units and supplies. The surviving original initiating attacker is selected for ownership, otherwise the country with greatest surviving healthy strength, breaking ties by country ID. Capture requires hostility to the defender. Spoils are taken only from defeated countries, not surviving coalition members; there is no shared-loot subsystem. All eligible surviving hostile besiegers can return from victorious relief combat with individual suspended losses restored.

Extinction removes the extinct country's treaties and proposals. Existing deterministic clan migration conserves physical assets. Migrants adopt their destination country's relations, not their previous country's treaty promises or private intelligence.

## Reconstruction evidence

Run tests against these exact rebuilt files and record hashes. Historical lost-version pass reports are not validation. Focused core and independent regression suites cover atomic treaty operations, conflicting/reciprocal proposals, war synchronization, event gates, private observation, SDK, save/load determinism, coalition survival/loot and relief continuation. Full-world evolution is distinct from small-state randomized diplomacy testing.
