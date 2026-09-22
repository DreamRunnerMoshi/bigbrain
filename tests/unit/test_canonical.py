"""Tests for bigbrain.common.canonical module."""

from bigbrain.common.canonical import canonical_json_bytes


class TestCanonicalJsonBytes:
    """Test canonical_json_bytes function."""

    def test_same_keys_different_order_produce_identical_bytes(self) -> None:
        """Two dicts with same keys in different insertion order produce identical bytes."""
        data1 = {"z": 1, "a": 2, "m": 3}
        data2 = {"a": 2, "m": 3, "z": 1}

        assert canonical_json_bytes(data1) == canonical_json_bytes(data2)

    def test_output_contains_no_spaces(self) -> None:
        """Output contains no extra whitespace."""
        data = {"key": "value", "nested": {"a": 1}}
        result = canonical_json_bytes(data)

        # No spaces after commas
        assert b", " not in result
        # No spaces after colons
        assert b": " not in result
        # No standalone spaces
        assert b" " not in result

    def test_non_ascii_string_utf8_roundtrip(self) -> None:
        """Non-ASCII string values encode as UTF-8 bytes, not as \\uXXXX escapes."""
        data = {"a": "café"}
        result = canonical_json_bytes(data)

        # Should contain the literal UTF-8 bytes for "é" (0xC3 0xA9), not an escape
        # The UTF-8 encoding of "café" is: c a f é -> 63 61 66 C3A9
        assert "\\u" not in result.decode("utf-8")
        # Verify it round-trips correctly
        assert b"caf" in result
        assert "café" in result.decode("utf-8")

    def test_nested_dicts_and_lists_sorted(self) -> None:
        """Nested dicts have their keys sorted; lists preserve order."""
        data = {"b": {"z": 1, "a": 2}, "a": [3, 2, 1]}
        result = canonical_json_bytes(data)
        decoded = result.decode("utf-8")

        # Top-level keys should be sorted: "a" before "b"
        a_pos = decoded.index('"a"')
        b_pos = decoded.index('"b"')
        assert a_pos < b_pos

        # Nested object keys should be sorted: "a" before "z"
        assert decoded.index('"a":2') < decoded.index('"z":1')

        # List values should preserve order [3,2,1]
        assert "[3,2,1]" in decoded
