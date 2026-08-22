"""E-3: the lexical index stores a *representation*, and changing it is a migration.

E-2 measured a real gain from normalising plurals and could not adopt it: the FTS5 `tokenize=`
option is fixed at CREATE, so a transformation SQLite cannot express made the index and the scan
answer the same question differently. E-3 moves the transformation up instead of down — the
normalised text is what gets persisted, so SQLite tokenizes already-normalised content and a
query normalised the same way matches it.

That makes the tokenizer choice a property of the stored data, which is why these tests care as
much about migrating an existing database as about the retrieval result.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from epistemos import Engine, Principal
from epistemos.index import IndexHealth
from epistemos.index.text import ASCII, PLURAL, get_tokenizer

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "benchmarks"))

CTX = Principal(tenant="acme", agent="a", namespace="kb")

CORPUS = [
    "Several audits were recorded for the payments scope.",
    "The retention window is ninety days. Policies apply to all regions.",
    "Approaches to escalation vary; the escalation paths are documented.",
    "Status is green. The analysis was completed and access was granted.",
    "The payments-api handles authorisations across regions.",
]


def _seed(engine, texts=CORPUS):
    return [engine.ingest_document(CTX, title=f"d{i}", text=t) for i, t in enumerate(texts)]


# -- the representation contract --------------------------------------------


def test_the_shipped_tokenizer_persists_text_unchanged():
    """Every tokenizer that existed before E-3 must keep writing exactly what it wrote before —
    otherwise adding the hook would silently invalidate every existing index."""
    text = "Several audits were recorded."
    assert ASCII.normalize_text(text) == text


def test_the_plural_tokenizer_persists_a_normalised_representation():
    assert PLURAL.normalize_text("Several audits were recorded") == "several audit were recorded"
    assert PLURAL.normalize_text("Policies apply") == "policy apply"
    # Conservative by design: words whose trailing s is not a plural marker are untouched.
    for word in ("status", "analysis", "access", "process", "always"):
        assert PLURAL.normalize_text(word) == word


def test_normalisation_is_idempotent():
    """Normalising twice must equal normalising once, or a rebuild would drift from the original
    write and `verify` would flag an index that is actually fine."""
    for text in CORPUS:
        once = PLURAL.normalize_text(text)
        assert PLURAL.normalize_text(once) == once


def test_the_stored_content_is_the_normalised_form(tmp_path):
    eng = Engine.open(str(tmp_path / "kb.epistemos"), tokenizer="plural")
    _seed(eng, ["Several audits were recorded."])
    rows = eng.store._conn.execute("SELECT content FROM fts_idx").fetchall()
    assert rows, "nothing indexed"
    assert "audit" in rows[0][0] and "audits" not in rows[0][0]
    eng.close()


# -- parity: the gate that blocked E-2 --------------------------------------


@pytest.mark.parametrize("tokenizer", ["ascii", "plural"])
def test_scan_and_index_agree_on_every_query(tmp_path, tokenizer):
    """The scan is the correctness reference and the index is an optimisation. They may rank
    differently — they use different lexical scores by design — but they must never disagree on
    *which* documents match, because that is a recall break, not a preference."""
    eng = Engine.open(str(tmp_path / f"kb-{tokenizer}.epistemos"), tokenizer=tokenizer)
    _seed(eng)
    assert eng.lexical_index is not None, "no index: this test would prove nothing"

    queries = ["audits", "audit", "policies", "policy", "retention", "escalation",
               "approaches", "status", "analysis", "payments", "authorisations", "regions"]
    indexed = {q: {r["id"] for r in eng.search(CTX, text=q, limit=1000)} for q in queries}
    eng.lexical_index = None                      # same store, same data, scan path
    scan = {q: {r["id"] for r in eng.search(CTX, text=q, limit=1000)} for q in queries}
    eng.close()

    mismatched = {q: (sorted(indexed[q]), sorted(scan[q])) for q in queries
                  if indexed[q] != scan[q]}
    assert not mismatched, f"scan/index recall parity broken for {mismatched}"


def test_the_e2_failure_mode_no_longer_reproduces(tmp_path):
    """Control: the same plural transformation *without* the persisted-representation fix broke
    parity. If this ever passes with the old shape again, E-3's premise is wrong."""
    from e2_tokenizers import PluralNormalising

    broken = PluralNormalising()          # transforms tokens, declares fts_tokenize="ascii"
    assert broken.normalize_text("Several audits") == "Several audits", (
        "the E-2 tokenizer is expected to leave content unnormalised — that was the defect")

    eng = Engine.open(str(tmp_path / "broken.epistemos"), tokenizer=broken)
    _seed(eng, ["Several audits were recorded."])
    idx = len(eng.search(CTX, text="audits", limit=100))
    eng.lexical_index = None
    scan = len(eng.search(CTX, text="audits", limit=100))
    eng.close()
    assert (idx, scan) == (0, 1), "E-2's break must still reproduce for the fix to mean anything"

    # And the E-3 tokenizer, on the same corpus and query, does not break.
    fixed = Engine.open(str(tmp_path / "fixed.epistemos"), tokenizer="plural")
    _seed(fixed, ["Several audits were recorded."])
    idx2 = len(fixed.search(CTX, text="audits", limit=100))
    fixed.lexical_index = None
    scan2 = len(fixed.search(CTX, text="audits", limit=100))
    fixed.close()
    assert idx2 == scan2 == 1


# -- rebuild ----------------------------------------------------------------


def test_rebuild_is_deterministic(tmp_path):
    """Rebuilding from the ledger must land on the same index bytes, or `verify` is measuring
    noise and a migration can never be proven complete."""
    eng = Engine.open(str(tmp_path / "kb.epistemos"), tokenizer="plural")
    _seed(eng)

    def snapshot():
        rows = eng.store._conn.execute(
            "SELECT fts_map.obj_id, fts_idx.content FROM fts_idx "
            "JOIN fts_map ON fts_map.rid = fts_idx.rowid"
        ).fetchall()
        return sorted(tuple(r) for r in rows)

    first = snapshot()
    for _ in range(3):
        eng.lexical_index.rebuild(eng.store)
        assert snapshot() == first
    eng.close()


def test_rebuild_reproduces_query_results(tmp_path):
    eng = Engine.open(str(tmp_path / "kb.epistemos"), tokenizer="plural")
    _seed(eng)
    before = [r["id"] for r in eng.search(CTX, text="audits policies", limit=50)]
    eng.lexical_index.rebuild(eng.store)
    after = [r["id"] for r in eng.search(CTX, text="audits policies", limit=50)]
    assert before == after
    eng.close()


# -- migrating an existing database -----------------------------------------


def test_an_existing_ascii_database_migrates_wholesale(tmp_path):
    """The decisive migration case: a database written under the old representation, reopened
    under the new one. Nothing may survive in the old form."""
    path = str(tmp_path / "kb.epistemos")
    old = Engine.open(path, tokenizer="ascii")
    _seed(old)
    assert old.search(CTX, text="audits", limit=10)
    assert not old.search(CTX, text="audit", limit=10), "ascii must not match the singular"
    old.close()

    new = Engine.open(path, tokenizer="plural")
    detail = new.lexical_index.verify_detail()
    assert detail["ok"], detail["divergences"]
    assert detail["representation"] == "normalized"

    # Every indexed row is in the new representation — no partially-migrated index.
    rows = [r[0] for r in new.store._conn.execute("SELECT content FROM fts_idx").fetchall()]
    assert rows
    assert all(c == PLURAL.normalize_text(c) for c in rows), "some rows are still un-normalised"

    # And the migrated index answers in the new representation.
    assert new.search(CTX, text="audit", limit=10)
    assert new.search(CTX, text="audits", limit=10)
    new.close()


def test_migration_survives_a_reopen_without_rebuilding_again(tmp_path):
    path = str(tmp_path / "kb.epistemos")
    first = Engine.open(path, tokenizer="ascii")
    _seed(first)
    first.close()

    migrated = Engine.open(path, tokenizer="plural")
    stored = migrated.store._conn.execute(
        "SELECT value FROM meta WHERE key = 'fts_tokenizer'").fetchone()
    assert stored[0] == "plural", "the migration must record which representation is on disk"
    migrated.close()

    again = Engine.open(path, tokenizer="plural")
    assert again.lexical_index.health() == IndexHealth.HEALTHY
    assert again.lexical_index.verify_detail()["ok"]
    again.close()


def test_migrating_back_is_also_a_full_rebuild(tmp_path):
    path = str(tmp_path / "kb.epistemos")
    eng = Engine.open(path, tokenizer="plural")
    _seed(eng)
    eng.close()

    back = Engine.open(path, tokenizer="ascii")
    rows = [r[0] for r in back.store._conn.execute("SELECT content FROM fts_idx").fetchall()]
    assert any("audits" in c for c in rows), "reverting must restore the original representation"
    assert back.lexical_index.verify_detail()["ok"]
    back.close()


def test_a_failed_migration_fails_closed(tmp_path, monkeypatch):
    """If the rebuild produces something that does not verify, the index must stay DEGRADED and
    must NOT record the new tokenizer — otherwise the next open would believe it migrated."""
    path = str(tmp_path / "kb.epistemos")
    old = Engine.open(path, tokenizer="ascii")
    _seed(old)
    old.close()

    from epistemos.index.fts import SqliteFtsIndex

    monkeypatch.setattr(SqliteFtsIndex, "verify", lambda self, store=None: False)
    broken = Engine.open(path, tokenizer="plural")
    assert broken.lexical_index.health() is IndexHealth.DEGRADED
    stored = broken.store._conn.execute(
        "SELECT value FROM meta WHERE key = 'fts_tokenizer'").fetchone()
    assert stored is None or stored[0] != "plural", (
        "a failed migration must not be recorded as done")
    # The engine still answers, via the scan path: correct, merely slower.
    assert broken.search(CTX, text="audits", limit=10)
    broken.close()


# -- verify_detail reports what it compared ----------------------------------


def test_verify_detail_names_the_four_layers(tmp_path):
    eng = Engine.open(str(tmp_path / "kb.epistemos"), tokenizer="plural")
    _seed(eng)
    detail = eng.lexical_index.verify_detail()
    assert detail["ok"] and detail["checked"] == len(CORPUS)
    assert detail["tokenizer"] == "plural"
    assert detail["representation"] == "normalized"
    assert detail["divergences"] == []
    eng.close()


def test_verify_detail_exposes_a_corrupted_content_cell(tmp_path):
    """A rewritten content cell that leaves the mapping intact is the subtle failure; the report
    must show original, normalised and indexed side by side rather than just saying 'false'."""
    eng = Engine.open(str(tmp_path / "kb.epistemos"), tokenizer="plural")
    _seed(eng)
    with eng.store._lock:
        eng.store._conn.execute("UPDATE fts_idx SET content = 'tampered' WHERE rowid = "
                                "(SELECT MIN(rowid) FROM fts_idx)")

    detail = eng.lexical_index.verify_detail()
    assert detail["ok"] is False
    drift = [d for d in detail["divergences"] if d["problem"] == "content drift"]
    assert drift, detail
    first = drift[0]
    assert first["indexed"] == "tampered"
    assert first["normalized"] != first["indexed"]
    assert "original" in first and "tokens_expected" in first
    assert eng.lexical_index.health() is IndexHealth.DEGRADED
    eng.close()


def test_get_tokenizer_resolves_the_new_name():
    assert get_tokenizer("plural") is PLURAL
    assert get_tokenizer(PLURAL) is PLURAL
