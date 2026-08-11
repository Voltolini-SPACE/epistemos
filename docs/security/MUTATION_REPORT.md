# EPISTEMOS Mutation Report (targeted critical-boundary harness)

Method: per-mutant, copy the package, apply one source mutation, run the invariant
suite against the copy, classify by pytest **exit code** (mission §32). Reproduce:
`python tools/mutation_harness.py`.

- CONTROL (unmutated copy) pytest rc = 0 (0 = green baseline)
- Every mutant below is **non-equivalent by construction** (it changes a load-
  bearing predicate), so the target is `SURVIVED == 0`.

```
MUTANTS_TOTAL              = 12
MUTANTS_NON_EQUIVALENT     = 12   (all curated mutants change behavior)
MUTANTS_KILLED            = 12
MUTANTS_SURVIVED          = 0
INVALID_MUTATIONS         = 0
CRITICAL_NON_EQUIVALENT_SURVIVED = 0
```

| mutant | boundary | result | detail | protects |
|--------|----------|--------|--------|----------|
| `temporal_lower_ge_to_gt` | temporal | **KILLED** | pytest rc=1 | valid-time lower bound inclusion |
| `temporal_upper_lt_to_le` | temporal | **KILLED** | pytest rc=1 | valid-time upper bound exclusion (half-open) |
| `ledger_skip_content_hash` | ledger | **KILLED** | pytest rc=1 | payload tamper detection |
| `ledger_skip_prev_link` | ledger | **KILLED** | pytest rc=1 | chain-break detection |
| `ledger_skip_seq_check` | ledger | **KILLED** | pytest rc=1 | reorder/removal/duplicate detection |
| `model_skip_confidence_bound` | validation | **KILLED** | pytest rc=1 | confidence [0,1] bound |
| `model_skip_valid_interval` | temporal | **KILLED** | pytest rc=1 | valid_to >= valid_from |
| `identity_skip_name_regex` | identity | **KILLED** | pytest rc=1 | namespace/tenant identifier validation (unicode confusables) |
| `identity_skip_owner_guard` | agent-isolation | **KILLED** | pytest rc=1 | cross-agent write (owner) guard |
| `core_skip_ref_scope` | tenant-isolation | **KILLED** | pytest rc=1 | cross-tenant reference scope check |
| `core_supersede_no_close` | supersession | **KILLED** | pytest rc=1 | supersede must close old belief |
| `core_import_no_verify` | import | **KILLED** | pytest rc=1 | import chain verification on tamper |

**MUTATION_CRITICAL = PASS**

