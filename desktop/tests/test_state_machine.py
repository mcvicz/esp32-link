"""Unit tests for the ConnectionState finite-state machine transitions."""

import pytest

from esp32_link.domain.state import (
    ConnectionState,
    ConnectionStateMachine,
    IllegalTransitionError,
)


def test_initial_state_is_disconnected() -> None:
    fsm = ConnectionStateMachine()
    assert fsm.state == ConnectionState.DISCONNECTED


def test_legal_transition_disconnected_to_connecting() -> None:
    fsm = ConnectionStateMachine()
    fsm.transition_to(ConnectionState.CONNECTING)
    assert fsm.state == ConnectionState.CONNECTING


def test_illegal_transition_raises() -> None:
    fsm = ConnectionStateMachine()
    with pytest.raises(IllegalTransitionError):
        fsm.transition_to(ConnectionState.CONNECTED)


def test_can_transition_to_reflects_table() -> None:
    fsm = ConnectionStateMachine()
    assert fsm.can_transition_to(ConnectionState.CONNECTING)
    assert not fsm.can_transition_to(ConnectionState.RECONNECTING)


def test_full_happy_path() -> None:
    fsm = ConnectionStateMachine()
    fsm.transition_to(ConnectionState.CONNECTING)
    fsm.transition_to(ConnectionState.CONNECTED)
    fsm.transition_to(ConnectionState.RECONNECTING)
    fsm.transition_to(ConnectionState.CONNECTED)
    fsm.transition_to(ConnectionState.DISCONNECTED)
    assert fsm.state == ConnectionState.DISCONNECTED


def test_error_recovery() -> None:
    fsm = ConnectionStateMachine()
    fsm.transition_to(ConnectionState.CONNECTING)
    fsm.transition_to(ConnectionState.ERROR)
    fsm.transition_to(ConnectionState.CONNECTING)
    assert fsm.state == ConnectionState.CONNECTING


def test_cannot_jump_from_connected_to_connecting() -> None:
    fsm = ConnectionStateMachine()
    fsm.transition_to(ConnectionState.CONNECTING)
    fsm.transition_to(ConnectionState.CONNECTED)
    with pytest.raises(IllegalTransitionError):
        fsm.transition_to(ConnectionState.CONNECTING)
