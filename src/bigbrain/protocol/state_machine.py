"""Session state machine (BIGBRAIN_SPEC.md section 6.4). BigBrain can't observe whether
the human actually paid on Shopify -- DONE means "handed off", not "paid". Illegal
transitions raise: this is part of I1's backstop, since nothing can reach
CHECKOUT_REQUESTED except via APPROVED, and APPROVED is reached only from
AWAITING_HUMAN after a human decision. See docs/DECISIONS.md ADR-007 for the edges the
spec's diagram leaves implicit (which states can reach EXPIRED / REJECTED_ALL).
"""

from enum import Enum


class SessionState(str, Enum):  # noqa: UP042 -- consistent with common (config.py, envelope.py)
    DRAFT = "DRAFT"
    BROADCAST = "BROADCAST"
    COLLECTING = "COLLECTING"
    NEGOTIATING = "NEGOTIATING"
    SHORTLISTED = "SHORTLISTED"
    AWAITING_HUMAN = "AWAITING_HUMAN"
    APPROVED = "APPROVED"
    CHECKOUT_REQUESTED = "CHECKOUT_REQUESTED"
    CHECKOUT_READY = "CHECKOUT_READY"
    HANDED_OFF = "HANDED_OFF"
    MANDATE_ISSUED = "MANDATE_ISSUED"
    TERMS_CHANGED = "TERMS_CHANGED"
    DONE = "DONE"
    REJECTED_ALL = "REJECTED_ALL"
    EXPIRED = "EXPIRED"
    CLOSED = "CLOSED"


class IllegalTransitionError(Exception):
    """Raised when a transition isn't in TRANSITIONS -- see docs/DECISIONS.md ADR-007."""

    def __init__(self, from_state: SessionState, to_state: SessionState) -> None:
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(f"illegal transition: {from_state.value} -> {to_state.value}")


# Explicit transition table (spec section 6.4 diagram + docs/DECISIONS.md ADR-007 for
# the branch points the diagram doesn't spell out literally: which states can reach
# EXPIRED, and that REJECTED_ALL is reached only from AWAITING_HUMAN).
TRANSITIONS: dict[SessionState, frozenset[SessionState]] = {
    SessionState.DRAFT: frozenset({SessionState.BROADCAST}),
    SessionState.BROADCAST: frozenset({SessionState.COLLECTING}),
    SessionState.COLLECTING: frozenset({SessionState.NEGOTIATING, SessionState.EXPIRED}),
    SessionState.NEGOTIATING: frozenset({SessionState.SHORTLISTED, SessionState.EXPIRED}),
    SessionState.SHORTLISTED: frozenset({SessionState.AWAITING_HUMAN, SessionState.EXPIRED}),
    SessionState.AWAITING_HUMAN: frozenset(
        {SessionState.APPROVED, SessionState.REJECTED_ALL, SessionState.EXPIRED}
    ),
    SessionState.APPROVED: frozenset(
        {SessionState.CHECKOUT_REQUESTED, SessionState.MANDATE_ISSUED}
    ),
    SessionState.CHECKOUT_REQUESTED: frozenset(
        {SessionState.CHECKOUT_READY, SessionState.TERMS_CHANGED}
    ),
    SessionState.CHECKOUT_READY: frozenset({SessionState.HANDED_OFF}),
    SessionState.HANDED_OFF: frozenset({SessionState.DONE}),
    SessionState.MANDATE_ISSUED: frozenset({SessionState.DONE}),
    SessionState.TERMS_CHANGED: frozenset({SessionState.AWAITING_HUMAN}),
    SessionState.DONE: frozenset(),
    SessionState.REJECTED_ALL: frozenset({SessionState.CLOSED}),
    SessionState.EXPIRED: frozenset({SessionState.CLOSED}),
    SessionState.CLOSED: frozenset(),
}


def transition(from_state: SessionState, to_state: SessionState) -> SessionState:
    """Return `to_state` if the edge is legal, else raise IllegalTransitionError."""
    if to_state not in TRANSITIONS[from_state]:
        raise IllegalTransitionError(from_state, to_state)
    return to_state


class SessionStateMachine:
    """Stateful wrapper: tracks the current state and the full history of states
    visited. A failed `advance()` (illegal transition) leaves `.state` unchanged --
    the exception is raised before any assignment happens.
    """

    def __init__(self, initial: SessionState = SessionState.DRAFT) -> None:
        self.state = initial
        self.history: list[SessionState] = [initial]

    def advance(self, to_state: SessionState) -> SessionState:
        self.state = transition(self.state, to_state)
        self.history.append(self.state)
        return self.state

    @property
    def is_terminal(self) -> bool:
        return len(TRANSITIONS[self.state]) == 0
