"""`epistemos ingest` — the vault sync, proven against a real directory tree.

The properties that matter: deterministic walk with include/exclude, idempotency on re-run
(zero new claims, identical store), change detection with `supersedes`, per-file fail-closed
errors, unicode search on Portuguese content, and a `verify` that still passes afterwards.
"""

from __future__ import annotations

import json

import pytest

from epistemos.cli import main
from epistemos.core import Engine
from epistemos.identity import Principal

pytestmark = pytest.mark.integration

CTX = Principal(tenant="default", agent="compiler", namespace="kb")


def _vault(tmp_path):
    base = tmp_path / "vault"
    (base / "Obsidian").mkdir(parents=True)
    (base / "Sessões").mkdir()
    (base / "repo-dump").mkdir()
    (base / ".obsidian").mkdir()

    (base / "HOME.md").write_text(
        "---\nstatus: ativo\ntags: [hub]\n---\n\nVeja [[Sessões de Trabalho]] e #missão.\n",
        encoding="utf-8",
    )
    (base / "Obsidian" / "Projeto.md").write_text(
        "---\nowner: \"Léo\"\n---\n\nLigado a [[HOME|início]].\n\nEstado: em produção\n",
        encoding="utf-8",
    )
    (base / "Sessões" / "Sessões de Trabalho.md").write_text(
        "Notas da sessão. Link para [[Projeto]].\n\n```bash\nOwner: falso\n```\n",
        encoding="utf-8",
    )
    (base / "repo-dump" / "README.md").write_text("Owner: repo-dump\n", encoding="utf-8")
    (base / ".obsidian" / "config.md").write_text("Interno: sim\n", encoding="utf-8")
    (base / "notas.txt").write_text("Não é markdown\n", encoding="utf-8")
    (base / "lixo.md").write_bytes(b"\xff\xfe invalido \xff")
    return base


def _run(capsys, *argv) -> tuple[int, dict]:
    rc = main([*argv, "--json"])
    out = capsys.readouterr().out
    return rc, json.loads(out)


def test_ingest_walk_idempotency_supersedes_and_unicode(tmp_path, capsys):
    base = _vault(tmp_path)
    db = str(tmp_path / "vault.epistemos")
    args = ["ingest", str(base), "--db", db, "--exclude", "repo-dump/**"]

    # -- first run: everything compiles, the broken file is an error, not an abort ----------
    rc, report = _run(capsys, *args)
    assert rc == 1  # lixo.md is undecodable — visible failure, per-file
    summary = report["summary"]
    assert summary["new"] == 3
    assert summary["error"] == 1
    assert summary["tokenizer"] == "unicode"  # new vault database defaults to unicode
    paths = {f["path"] for f in report["files"]}
    assert "repo-dump/README.md" not in paths      # excluded subtree
    assert not any(p.startswith(".obsidian") for p in paths)  # dot-dirs never walked
    assert "notas.txt" not in paths                # not matched by **/*.md
    first_created = summary["claims_created"]
    assert first_created > 0
    by_rule = summary["by_rule"]
    assert by_rule.get("wikilink", 0) >= 3
    assert by_rule.get("frontmatter", 0) >= 3
    assert by_rule.get("tag", 0) >= 1

    # -- second run: byte-identical vault, zero new claims, identical store -----------------
    eng = Engine.open(db)
    docs_before = len(list(eng.store.objects("default", "kb", "document")))
    claims_before = len(list(eng.store.objects("default", "kb", "claim")))
    eng.close()

    rc2, report2 = _run(capsys, *args)
    assert rc2 == 1  # the broken file is still broken — honesty over habituation
    s2 = report2["summary"]
    assert s2["claims_created"] == 0
    assert s2["unchanged"] == 3
    assert s2["new"] == 0 and s2["changed"] == 0

    eng = Engine.open(db)
    assert len(list(eng.store.objects("default", "kb", "document"))) == docs_before
    assert len(list(eng.store.objects("default", "kb", "claim"))) == claims_before

    # -- unicode proof: an accent-less query finds the accented Portuguese note -------------
    hits = eng.search(CTX, text="sessoes", limit=10)
    assert hits, "unicode tokenizer must fold Sessões -> sessoes"
    eng.close()

    # -- verify still passes on the ingested database ---------------------------------------
    assert main(["verify", db]) == 0
    capsys.readouterr()


def test_ingest_edit_is_one_changed_file_with_supersedes(tmp_path, capsys):
    base = _vault(tmp_path)
    (base / "lixo.md").unlink()  # keep this scenario clean
    db = str(tmp_path / "vault.epistemos")
    rc, report = _run(capsys, "ingest", str(base), "--db", db,
                      "--exclude", "repo-dump/**")
    assert rc == 0

    (base / "HOME.md").write_text(
        "---\nstatus: arquivado\n---\n\nVeja [[Projeto]].\n", encoding="utf-8"
    )
    rc2, report2 = _run(capsys, "ingest", str(base), "--db", db,
                        "--exclude", "repo-dump/**")
    assert rc2 == 0
    s2 = report2["summary"]
    assert s2["changed"] == 1 and s2["unchanged"] == 2 and s2["new"] == 0

    eng = Engine.open(db)
    homes = [
        obj for obj in eng.store.objects("default", "kb", "document")
        if isinstance(obj.get("metadata"), dict)
        and obj["metadata"].get("vault_path") == "HOME.md"
    ]
    assert len(homes) == 2
    superseding = [o for o in homes if o["metadata"].get("supersedes")]
    assert len(superseding) == 1
    assert superseding[0]["metadata"]["supersedes"] in {o["id"] for o in homes}
    eng.close()


def test_ingest_dry_run_writes_nothing(tmp_path, capsys):
    base = _vault(tmp_path)
    (base / "lixo.md").unlink()
    db = tmp_path / "vault.epistemos"
    rc, report = _run(capsys, "ingest", str(base), "--dry-run",
                      "--exclude", "repo-dump/**")
    assert rc == 0
    assert report["summary"]["dry_run"] is True
    assert report["summary"]["extractions"] > 0
    assert not db.exists()


def test_ingest_requires_a_db_outside_dry_run(tmp_path, capsys):
    base = _vault(tmp_path)
    assert main(["ingest", str(base)]) == 2
    capsys.readouterr()


def test_ingest_refuses_a_non_directory(tmp_path, capsys):
    assert main(["ingest", str(tmp_path / "nao-existe")]) == 2
    capsys.readouterr()


def test_glob_match_has_real_globstar_semantics():
    """Regression: fnmatch treats ** like *, demanding a slash — `**/*.md` must match a file at
    the walk root, and `*`/`?` must stop at slashes."""
    from epistemos.cli import _glob_match

    assert _glob_match("HOME.md", "**/*.md")            # zero directories
    assert _glob_match("a/b/c.md", "**/*.md")           # many directories
    assert _glob_match("repo-dump/x/y.md", "repo-dump/**")
    assert _glob_match("node_modules", "**/node_modules")
    assert _glob_match("a/node_modules", "**/node_modules")
    assert not _glob_match("a/b.md", "*.md")            # * stops at slash
    assert not _glob_match("ab.md", "?.md")
    assert _glob_match("Sessões/nota.md", "Sessões/**")  # unicode path survives re.escape
