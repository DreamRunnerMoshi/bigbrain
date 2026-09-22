"""Unit tests for bigbrain.common.audit."""

from pathlib import Path

from bigbrain.common.audit import GENESIS_HASH, AuditLog


def test_first_record_chains_from_genesis(tmp_path: Path) -> None:
    log = AuditLog(tmp_path, "session-1")

    event = log.record("intent_decrypted", {"channel": "headphones"})

    assert event.prev_hash == GENESIS_HASH
    assert len(event.entry_hash) == 64
    assert log.verify_chain() is True


def test_sequential_records_chain_onto_each_other(tmp_path: Path) -> None:
    log = AuditLog(tmp_path, "session-2")

    first = log.record("intent_decrypted", {"worker": "w1"})
    second = log.record("offer_built", {"worker": "w1", "product": "p1"})
    third = log.record("offer_sent", {"worker": "w1", "offer": "o1"})

    assert second.prev_hash == first.entry_hash
    assert third.prev_hash == second.entry_hash
    assert log.verify_chain() is True


def test_reopened_log_continues_the_same_chain(tmp_path: Path) -> None:
    first_log = AuditLog(tmp_path, "session-3")
    first_log.record("intent_decrypted", {"n": 1})
    first_log.record("offer_built", {"n": 2})
    expected_chain = [event.entry_hash for event in first_log.read_all()]

    reopened = AuditLog(tmp_path, "session-3")  # same dir + session: append, never truncate
    appended = reopened.record("offer_sent", {"n": 3})

    events = reopened.read_all()
    assert appended.prev_hash == expected_chain[-1]
    assert [event.entry_hash for event in events] == [*expected_chain, appended.entry_hash]
    assert reopened.verify_chain() is True


def test_tampered_line_breaks_the_chain(tmp_path: Path) -> None:
    log = AuditLog(tmp_path, "session-4")
    log.record("intent_decrypted", {"keywords": "noise cancelling"})
    log.record("offer_sent", {"offer": "o1"})
    original = log.path.read_text(encoding="utf-8")

    tampered = original.replace("noise cancelling", "noise cancelling!", 1)
    assert tampered != original  # the value changed, the line is still valid JSON
    log.path.write_text(tampered, encoding="utf-8")

    assert log.verify_chain() is False


def test_dropped_middle_entry_breaks_the_chain(tmp_path: Path) -> None:
    log = AuditLog(tmp_path, "session-6")
    log.record("intent_decrypted", {"n": 1})
    log.record("offer_built", {"n": 2})
    log.record("offer_sent", {"n": 3})

    lines = log.path.read_text(encoding="utf-8").splitlines(keepends=True)
    del lines[1]  # silently removing an event must not read as a valid chain
    log.path.write_text("".join(lines), encoding="utf-8")

    assert log.verify_chain() is False


def test_read_all_returns_events_in_file_order(tmp_path: Path) -> None:
    log = AuditLog(tmp_path, "session-5")
    types = ("intent_decrypted", "offer_built", "offer_sent")

    for event_type in types:
        log.record(event_type, {})

    assert [event.event_type for event in log.read_all()] == list(types)
    assert all(event.session_id == "session-5" for event in log.read_all())
