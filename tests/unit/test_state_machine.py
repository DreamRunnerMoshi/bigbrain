"""Tests for session state machine (protocol/state_machine.py).

Covers completeness, legal edges, illegal edges (exhaustive product), happy paths
(Shopify checkout and mandate), re-approval loop (I10), rejection, expiry, failed
advances, and terminal states.
"""

import pytest

from bigbrain.protocol.state_machine import (
    TRANSITIONS,
    IllegalTransitionError,
    SessionState,
    SessionStateMachine,
    transition,
)


class TestCompletenessAndStructure:
    """Requirement 1: every SessionState member is in TRANSITIONS."""

    def test_transitions_completeness(self) -> None:
        """Every SessionState is a key in TRANSITIONS."""
        assert set(TRANSITIONS.keys()) == set(SessionState)


class TestLegalTransitions:
    """Requirement 3: every legal edge succeeds."""

    @pytest.mark.parametrize(
        "from_state,to_state",
        [
            (SessionState.DRAFT, SessionState.BROADCAST),
            (SessionState.BROADCAST, SessionState.COLLECTING),
            (SessionState.COLLECTING, SessionState.NEGOTIATING),
            (SessionState.COLLECTING, SessionState.EXPIRED),
            (SessionState.NEGOTIATING, SessionState.SHORTLISTED),
            (SessionState.NEGOTIATING, SessionState.EXPIRED),
            (SessionState.SHORTLISTED, SessionState.AWAITING_HUMAN),
            (SessionState.SHORTLISTED, SessionState.EXPIRED),
            (SessionState.AWAITING_HUMAN, SessionState.APPROVED),
            (SessionState.AWAITING_HUMAN, SessionState.REJECTED_ALL),
            (SessionState.AWAITING_HUMAN, SessionState.EXPIRED),
            (SessionState.APPROVED, SessionState.CHECKOUT_REQUESTED),
            (SessionState.APPROVED, SessionState.MANDATE_ISSUED),
            (SessionState.CHECKOUT_REQUESTED, SessionState.CHECKOUT_READY),
            (SessionState.CHECKOUT_REQUESTED, SessionState.TERMS_CHANGED),
            (SessionState.CHECKOUT_READY, SessionState.HANDED_OFF),
            (SessionState.HANDED_OFF, SessionState.DONE),
            (SessionState.MANDATE_ISSUED, SessionState.DONE),
            (SessionState.TERMS_CHANGED, SessionState.AWAITING_HUMAN),
            (SessionState.REJECTED_ALL, SessionState.CLOSED),
            (SessionState.EXPIRED, SessionState.CLOSED),
        ],
    )
    def test_legal_edges_succeed(self, from_state: SessionState, to_state: SessionState) -> None:
        """Every legal edge in TRANSITIONS returns to_state without raising."""
        result = transition(from_state, to_state)
        assert result == to_state


class TestIllegalTransitionsExhaustive:
    """Requirement 2: exhaustive illegal-transition coverage over full 16x16 product."""

    def test_all_illegal_transitions_raise(self) -> None:
        """Every pair (a, b) where b NOT in TRANSITIONS[a] raises IllegalTransitionError.

        This test iterates the full SessionState × SessionState product (256 pairs) and
        tests every illegal edge exhaustively (not just a hand-picked sample).
        """
        all_states = list(SessionState)
        illegal_count = 0

        for from_state in all_states:
            for to_state in all_states:
                if to_state not in TRANSITIONS[from_state]:
                    illegal_count += 1
                    with pytest.raises(IllegalTransitionError) as exc_info:
                        transition(from_state, to_state)

                    # Assert exception attributes are set correctly
                    assert exc_info.value.from_state == from_state
                    assert exc_info.value.to_state == to_state

        # Verify we actually tested a substantial number of illegal transitions
        # (256 total pairs - ~21 legal edges ≈ 235+ illegal)
        assert illegal_count >= 230, f"Expected 230+ illegal cases, got {illegal_count}"


class TestHappyPathShopify:
    """Requirement 4: happy path through Shopify checkout."""

    def test_shopify_checkout_flow(self) -> None:
        """Walk DRAFT -> BROADCAST -> ... -> DONE for Shopify checkout.

        Assert .state == DONE at end, .is_terminal True only at end,
        .history equals full list in order.
        """
        machine = SessionStateMachine()

        # Initial state
        assert machine.state == SessionState.DRAFT
        assert machine.is_terminal is False
        assert machine.history == [SessionState.DRAFT]

        # Step through each transition
        machine.advance(SessionState.BROADCAST)
        assert machine.is_terminal is False

        machine.advance(SessionState.COLLECTING)
        assert machine.is_terminal is False

        machine.advance(SessionState.NEGOTIATING)
        assert machine.is_terminal is False

        machine.advance(SessionState.SHORTLISTED)
        assert machine.is_terminal is False

        machine.advance(SessionState.AWAITING_HUMAN)
        assert machine.is_terminal is False

        machine.advance(SessionState.APPROVED)
        assert machine.is_terminal is False

        machine.advance(SessionState.CHECKOUT_REQUESTED)
        assert machine.is_terminal is False

        machine.advance(SessionState.CHECKOUT_READY)
        assert machine.is_terminal is False

        machine.advance(SessionState.HANDED_OFF)
        assert machine.is_terminal is False

        machine.advance(SessionState.DONE)
        assert machine.state == SessionState.DONE
        assert machine.is_terminal is True

        # Verify complete history
        expected_history = [
            SessionState.DRAFT,
            SessionState.BROADCAST,
            SessionState.COLLECTING,
            SessionState.NEGOTIATING,
            SessionState.SHORTLISTED,
            SessionState.AWAITING_HUMAN,
            SessionState.APPROVED,
            SessionState.CHECKOUT_REQUESTED,
            SessionState.CHECKOUT_READY,
            SessionState.HANDED_OFF,
            SessionState.DONE,
        ]
        assert machine.history == expected_history


class TestHappyPathMandate:
    """Requirement 5: happy path through sim/AP2 mandate."""

    def test_mandate_flow(self) -> None:
        """Walk DRAFT -> ... -> APPROVED -> MANDATE_ISSUED -> DONE.

        Assert final state DONE and is_terminal True.
        """
        machine = SessionStateMachine()

        machine.advance(SessionState.BROADCAST)
        machine.advance(SessionState.COLLECTING)
        machine.advance(SessionState.NEGOTIATING)
        machine.advance(SessionState.SHORTLISTED)
        machine.advance(SessionState.AWAITING_HUMAN)
        machine.advance(SessionState.APPROVED)

        # Branch to mandate path instead of checkout
        machine.advance(SessionState.MANDATE_ISSUED)
        machine.advance(SessionState.DONE)

        assert machine.state == SessionState.DONE
        assert machine.is_terminal is True


class TestReapprovalLoop:
    """Requirement 6: re-approval loop (I10)."""

    def test_reapproval_cycle(self) -> None:
        """Walk through APPROVED -> CHECKOUT_REQUESTED -> TERMS_CHANGED -> AWAITING_HUMAN
        -> APPROVED again, then through to DONE.

        Assert AWAITING_HUMAN appears twice in .history.
        """
        machine = SessionStateMachine()

        machine.advance(SessionState.BROADCAST)
        machine.advance(SessionState.COLLECTING)
        machine.advance(SessionState.NEGOTIATING)
        machine.advance(SessionState.SHORTLISTED)
        machine.advance(SessionState.AWAITING_HUMAN)  # First time
        machine.advance(SessionState.APPROVED)

        machine.advance(SessionState.CHECKOUT_REQUESTED)
        machine.advance(SessionState.TERMS_CHANGED)
        machine.advance(SessionState.AWAITING_HUMAN)  # Second time (loop back)

        machine.advance(SessionState.APPROVED)
        machine.advance(SessionState.CHECKOUT_REQUESTED)
        machine.advance(SessionState.CHECKOUT_READY)
        machine.advance(SessionState.HANDED_OFF)
        machine.advance(SessionState.DONE)

        # Count occurrences of AWAITING_HUMAN in history
        awaiting_human_count = machine.history.count(SessionState.AWAITING_HUMAN)
        assert awaiting_human_count == 2, (
            f"Expected AWAITING_HUMAN twice, got {awaiting_human_count} times"
        )


class TestRejectedAllPath:
    """Requirement 7: rejected-all path."""

    def test_rejected_all_flow(self) -> None:
        """Walk through SHORTLISTED -> AWAITING_HUMAN -> REJECTED_ALL -> CLOSED.

        Assert final state CLOSED and is_terminal True.
        """
        machine = SessionStateMachine()

        machine.advance(SessionState.BROADCAST)
        machine.advance(SessionState.COLLECTING)
        machine.advance(SessionState.NEGOTIATING)
        machine.advance(SessionState.SHORTLISTED)
        machine.advance(SessionState.AWAITING_HUMAN)
        machine.advance(SessionState.REJECTED_ALL)
        machine.advance(SessionState.CLOSED)

        assert machine.state == SessionState.CLOSED
        assert machine.is_terminal is True


class TestExpiredPath:
    """Requirement 8: expired path, parametrized over every state that can expire."""

    @pytest.mark.parametrize(
        "expiring_state",
        [
            SessionState.COLLECTING,
            SessionState.NEGOTIATING,
            SessionState.SHORTLISTED,
            SessionState.AWAITING_HUMAN,
        ],
    )
    def test_expiry_from_each_state(self, expiring_state: SessionState) -> None:
        """From each state that can expire, advance to EXPIRED, then to CLOSED."""
        machine = SessionStateMachine(initial=expiring_state)
        assert machine.state == expiring_state

        machine.advance(SessionState.EXPIRED)
        assert machine.state == SessionState.EXPIRED

        machine.advance(SessionState.CLOSED)
        assert machine.state == SessionState.CLOSED
        assert machine.is_terminal is True


class TestFailedAdvanceDoesNotCorruptState:
    """Requirement 9: failed advance leaves state unchanged."""

    def test_illegal_advance_preserves_state_and_history(self) -> None:
        """Attempt an illegal transition, assert it raises, state unchanged, history clean."""
        machine = SessionStateMachine(initial=SessionState.COLLECTING)
        initial_state = machine.state
        initial_history = machine.history.copy()

        # Try to jump directly to DONE (illegal from COLLECTING)
        with pytest.raises(IllegalTransitionError):
            machine.advance(SessionState.DONE)

        # Verify state and history unchanged
        assert machine.state == initial_state
        assert machine.state == SessionState.COLLECTING
        assert machine.history == initial_history
        assert len(machine.history) == 1


class TestTerminalStates:
    """Requirement 10: terminal states have no legal transitions."""

    def test_done_terminal(self) -> None:
        """DONE is terminal: no outgoing edges."""
        assert TRANSITIONS[SessionState.DONE] == frozenset()

    def test_closed_terminal(self) -> None:
        """CLOSED is terminal: no outgoing edges."""
        assert TRANSITIONS[SessionState.CLOSED] == frozenset()

    def test_transition_from_done_always_raises(self) -> None:
        """Attempting transition from DONE to any other state raises."""
        for target_state in SessionState:
            if target_state == SessionState.DONE:
                continue  # Skip DONE -> DONE
            with pytest.raises(IllegalTransitionError):
                transition(SessionState.DONE, target_state)

    def test_transition_from_closed_always_raises(self) -> None:
        """Attempting transition from CLOSED to any other state raises."""
        for target_state in SessionState:
            if target_state == SessionState.CLOSED:
                continue  # Skip CLOSED -> CLOSED
            with pytest.raises(IllegalTransitionError):
                transition(SessionState.CLOSED, target_state)
