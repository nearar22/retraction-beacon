import sys
import pytest

CONTRACT = "contracts/retraction_beacon.py"
PUB = "https://publisher.example.org/notices/demo"
REG = "https://registry.example.net/records/demo"


def create(contract):
    return contract.create_record("paper-demo", "https://doi.org/10.5555/RB-DEMO-2026", "Synthetic Catalyst Study for Contract Testing", PUB, REG)


def patch_now(contract, monkeypatch, callback):
    instance = object.__getattribute__(contract, "_instance")
    monkeypatch.setattr(sys.modules[instance.__class__.__module__], "_now", callback)


def result(status="RETRACTED"):
    if status == "RETRACTED":
        return {"status": "RETRACTED", "severity": 100, "doi_confirmed": True, "effective_date": "2026-11-15", "action": "DO_NOT_CITE", "summary": "Both authorities identify the exact DOI as formally retracted.", "evidence": [{"source_index": 0, "quote": "DOI 10.5555/rb-demo-2026 is retracted"}, {"source_index": 1, "quote": "registry status: retracted"}], "source_receipts": [{"source_index": 0, "url": PUB, "host": "publisher.example.org", "available": True, "sha256": "a" * 64}, {"source_index": 1, "url": REG, "host": "registry.example.net", "available": True, "sha256": "b" * 64}]}
    return {"status": status, "severity": 0, "doi_confirmed": True, "effective_date": "", "action": "NO_CHANGE", "summary": "Neither authority publishes a current notice for the exact DOI.", "evidence": [], "source_receipts": []}


def test_create_normalizes_doi_and_rejects_duplicate(direct_deploy):
    contract = direct_deploy(CONTRACT)
    assert create(contract) == "paper-demo"
    assert contract.get_record("paper-demo")["doi"] == "10.5555/rb-demo-2026"
    with pytest.raises(Exception): create(contract)


def test_invalid_doi_https_and_duplicate_hosts_rejected(direct_deploy):
    contract = direct_deploy(CONTRACT)
    with pytest.raises(Exception): contract.create_record("bad-doi", "paper", "Long enough paper title", PUB, REG)
    with pytest.raises(Exception): contract.create_record("bad-http", "10.5555/demo", "Long enough paper title", "http://publisher.test/a", REG)
    with pytest.raises(Exception): contract.create_record("same-host", "10.5555/demo", "Long enough paper title", "https://same.test/a", "https://same.test/b")


def test_first_refresh_is_permissionless_and_persists_receipt(direct_vm, direct_deploy, direct_alice, monkeypatch):
    contract = direct_deploy(CONTRACT); create(contract)
    monkeypatch.setattr(contract, "_evaluate", lambda *args: result())
    patch_now(contract, monkeypatch, lambda: 1000); direct_vm.sender = direct_alice
    refreshed = contract.refresh_status("paper-demo")
    state = contract.get_record("paper-demo")
    assert refreshed["revision"] == 1 and len(refreshed["revision_receipt"]) == 64
    assert state["current"]["status"] == "RETRACTED" and state["next_refresh_at"] == 22600


def test_refresh_cooldown_is_enforced(direct_deploy, monkeypatch):
    contract = direct_deploy(CONTRACT); create(contract)
    monkeypatch.setattr(contract, "_evaluate", lambda *args: result())
    patch_now(contract, monkeypatch, lambda: 1000); contract.refresh_status("paper-demo")
    with pytest.raises(Exception): contract.refresh_status("paper-demo")


def test_later_refresh_preserves_previous_revision(direct_deploy, monkeypatch):
    contract = direct_deploy(CONTRACT); create(contract)
    queue = [result("NO_NOTICE"), result()]
    monkeypatch.setattr(contract, "_evaluate", lambda *args: queue.pop(0))
    clock = {"now": 1000}; patch_now(contract, monkeypatch, lambda: clock["now"])
    contract.refresh_status("paper-demo"); clock["now"] = 23000; contract.refresh_status("paper-demo")
    state = contract.get_record("paper-demo")
    assert state["revision"] == 2 and state["history"][0]["status"] == "NO_NOTICE" and state["current"]["status"] == "RETRACTED"


def test_only_owner_can_archive(direct_vm, direct_deploy, direct_alice, monkeypatch):
    contract = direct_deploy(CONTRACT); create(contract)
    monkeypatch.setattr(contract, "_evaluate", lambda *args: result()); contract.refresh_status("paper-demo")
    direct_vm.sender = direct_alice
    with pytest.raises(Exception): contract.archive_record("paper-demo")


def test_non_terminal_status_cannot_be_archived(direct_deploy, monkeypatch):
    contract = direct_deploy(CONTRACT); create(contract)
    monkeypatch.setattr(contract, "_evaluate", lambda *args: result("NO_NOTICE")); contract.refresh_status("paper-demo")
    with pytest.raises(Exception): contract.archive_record("paper-demo")


def test_terminal_record_archives_once_and_blocks_refresh(direct_deploy, monkeypatch):
    contract = direct_deploy(CONTRACT); create(contract)
    monkeypatch.setattr(contract, "_evaluate", lambda *args: result()); contract.refresh_status("paper-demo")
    archived = contract.archive_record("paper-demo")
    assert archived["state"] == "ARCHIVED" and len(archived["receipt"]) == 64
    with pytest.raises(Exception): contract.archive_record("paper-demo")
    with pytest.raises(Exception): contract.refresh_status("paper-demo")


def test_normalizer_accepts_numeric_string_and_binds_both_sources(direct_deploy):
    contract = direct_deploy(CONTRACT); instance = object.__getattribute__(contract, "_instance")
    normalize = sys.modules[instance.__class__.__module__]._normalize
    fetched = [{"source_index": 0, "url": PUB, "host": "publisher.example.org", "available": True, "content": "Publisher notice: DOI 10.5555/rb-demo-2026 is retracted effective 2026-11-15.", "sha256": "a" * 64}, {"source_index": 1, "url": REG, "host": "registry.example.net", "available": True, "content": "Independent registry status: retracted for DOI 10.5555/rb-demo-2026.", "sha256": "b" * 64}]
    raw = {"status": "RETRACTED", "severity": "100", "doi_confirmed": True, "effective_date": "2026-11-15", "action": "DO_NOT_CITE", "summary": "Both frozen authorities identify the same DOI as retracted.", "evidence": [{"source_index": 0, "quote": "DOI 10.5555/rb-demo-2026 is retracted"}, {"source_index": 1, "quote": "registry status: retracted for DOI 10.5555/rb-demo-2026"}]}
    assert normalize(raw, fetched)["severity"] == 100


def test_normalizer_rejects_forged_quote_or_single_source_retraction(direct_deploy):
    contract = direct_deploy(CONTRACT); instance = object.__getattribute__(contract, "_instance")
    normalize = sys.modules[instance.__class__.__module__]._normalize
    fetched = [{"source_index": 0, "url": PUB, "host": "publisher.example.org", "available": True, "content": "Publisher notice for DOI 10.5555/rb-demo-2026.", "sha256": "a" * 64}, {"source_index": 1, "url": REG, "host": "registry.example.net", "available": True, "content": "Registry entry for DOI 10.5555/rb-demo-2026.", "sha256": "b" * 64}]
    forged = {"status": "RETRACTED", "severity": 100, "doi_confirmed": True, "effective_date": "", "action": "DO_NOT_CITE", "summary": "A fabricated retraction must never pass deterministic validation.", "evidence": [{"source_index": 0, "quote": "This paper was formally retracted."}, {"source_index": 1, "quote": "Registry entry for DOI 10.5555/rb-demo-2026."}]}
    with pytest.raises(Exception): normalize(forged, fetched)

