# Task Plan: Three-round Ti6Al4V optimization campaign

## Goal
Run and guide three additional optimization rounds for the Ti6Al4V SingleTrack Powder60um case, preserving a snapshot for each round and adjusting the Bayesian search strategy based on observed results.

## Current Phase
Phase 3

## Phases
### Phase 1: Campaign Setup
- [x] Capture baseline optimization state and existing best result
- [x] Define per-round snapshot layout and execution method
- [x] Document round 1 search-strategy changes
- **Status:** complete

### Phase 2: Round 1 Preparation
- [x] Create baseline snapshot metadata
- [x] Create round 1 config and warmstart history copy
- [x] Verify launch command and inputs
- **Status:** complete

### Phase 3: Round 1 Execution & Review
- [ ] Run one new Bayesian optimization iteration
- [ ] Verify new history/result artifacts
- [ ] Interpret whether round 1 improved the best solution
- **Status:** in_progress

### Phase 4: Round 2 Preparation/Execution
- [ ] Choose round 2 changes from round 1 evidence
- [ ] Preserve round 1 snapshot
- [ ] Run and review round 2
- **Status:** pending

### Phase 5: Round 3 Preparation/Execution
- [ ] Choose round 3 changes from round 2 evidence
- [ ] Preserve round 2 snapshot
- [ ] Run and review round 3
- **Status:** pending

### Phase 6: Delivery
- [ ] Summarize all three rounds
- [ ] Recommend next optimization direction
- [ ] List modified files and saved artifacts
- **Status:** pending

## Key Questions
1. What is the safest way to preserve each round without overwriting the existing `runs` history?
2. Which round 1 changes are most justified by the current objective landscape and boundary behavior?
3. After each new iteration, did the best objective improve, stagnate, or worsen?

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| Preserve each optimization round in its own directory | The user explicitly wants snapshots and round-to-round comparability |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| `session-catchup.py` not found at the default `${CLAUDE_PLUGIN_ROOT}` path | 1 | Continued manually by reading skill templates and creating planning files directly |
| `bayes` CLI startup failed with `ModuleNotFoundError: No module named 'ACBICI'` | 1 | Fixed package init imports so optional ACBICI dependencies no longer block Bayesian workflow |

## Notes
- Keep each round limited to one new Bayesian batch initially so we can re-steer after every result.
- Prefer expanding bounds over shrinking them so warmstart samples remain valid.
