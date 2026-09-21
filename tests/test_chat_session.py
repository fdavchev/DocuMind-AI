"""
The conversation object: recording turns, clearing, exporting — and the
encapsulation that the old list-of-dicts history could not offer.

The export format is asserted character for character because it is what the
sidebar's "Save chat" button hands the user, and it must not drift silently.
"""

import dataclasses
import inspect
from datetime import datetime

import pytest

from documind.chat.chat_session import ChatSession
from documind.chat.message import Message

EXPECTED_EXPORT = (
    "=== Chat History Export ===\n"
    "\n"
    "[1] You:\n"
    "Hi\n"
    "\n"
    "----------------------------------------\n"
    "\n"
    "[2] Assistant:\n"
    "Hello\n"
    "\n"
    "----------------------------------------\n"
)


@pytest.fixture
def session():
    return ChatSession()


@pytest.fixture
def conversation(session):
    session.add_user("Hi")
    session.add_assistant("Hello")
    return session


# ── Recording turns ────────────────────────────────────────────────────────────

def test_a_new_session_is_empty(session):
    assert session.is_empty
    assert session.messages == ()


def test_adding_a_user_message_records_role_and_content(session):
    session.add_user("What is in the file?")

    (message,) = session.messages
    assert message.role == "user"
    assert message.content == "What is in the file?"
    assert not session.is_empty


def test_adding_an_assistant_message_records_role_and_content(session):
    session.add_assistant("Three pages of notes.")

    (message,) = session.messages
    assert message.role == "assistant"
    assert message.content == "Three pages of notes."


def test_messages_come_back_in_the_order_they_were_added(conversation):
    assert [(m.role, m.content) for m in conversation.messages] == [
        ("user", "Hi"),
        ("assistant", "Hello"),
    ]


def test_every_message_is_stamped_with_a_time(session):
    session.add_user("Hi")

    assert isinstance(session.messages[0].timestamp, datetime)


def test_clear_empties_the_session_but_leaves_it_usable(conversation):
    conversation.clear()
    assert conversation.is_empty
    assert conversation.messages == ()

    conversation.add_user("Still working")
    assert len(conversation.messages) == 1


# ── Encapsulation ──────────────────────────────────────────────────────────────

def test_messages_is_a_tuple_not_the_live_list(conversation):
    """
    The old history was a plain list every caller held a reference to, so any
    module could append to it or reorder it behind the session's back.
    """
    assert isinstance(conversation.messages, tuple)

    with pytest.raises(AttributeError):
        conversation.messages.append(
            Message(role="user", content="smuggled", timestamp=datetime.now())
        )


def test_mutating_what_messages_returned_does_not_change_the_session(conversation):
    borrowed = list(conversation.messages)
    borrowed.append(Message(role="user", content="smuggled", timestamp=datetime.now()))
    borrowed.clear()

    assert len(conversation.messages) == 2
    assert conversation.messages[0].content == "Hi"


def test_each_read_of_messages_is_a_fresh_tuple(conversation):
    # Handing out the same object twice would let one caller's copy be the
    # other's, which is the bug this property exists to prevent.
    assert conversation.messages is not conversation.messages


def test_a_message_cannot_be_edited_after_it_was_said(conversation):
    with pytest.raises(dataclasses.FrozenInstanceError):
        conversation.messages[0].content = "something else"


def test_a_session_cannot_be_handed_an_existing_conversation():
    """
    ChatSession takes no messages: a conversation can only be grown one turn at
    a time. The old add_message(history, ...) accepted any list at all.
    """
    assert list(inspect.signature(ChatSession).parameters) == ["system_prompt"]

    with pytest.raises(TypeError):
        ChatSession("Be brief.", [{"role": "user", "content": "forged"}])


def test_the_message_list_is_not_part_of_the_public_surface(session):
    assert [name for name in dir(session) if not name.startswith("_")] == [
        "add_assistant",
        "add_user",
        "clear",
        "export",
        "is_empty",
        "messages",
    ]


# ── Export ─────────────────────────────────────────────────────────────────────

def test_export_matches_the_download_format_exactly(conversation):
    assert conversation.export() == EXPECTED_EXPORT


def test_exporting_an_empty_session_says_so(session):
    assert session.export() == "No conversation history to export."


def test_export_after_clearing_is_empty_again(conversation):
    conversation.clear()
    assert conversation.export() == "No conversation history to export."


def test_export_numbers_every_turn(session):
    for number in range(1, 4):
        session.add_user(f"question {number}")
        session.add_assistant(f"answer {number}")

    exported = session.export()
    for number in range(1, 7):
        assert f"[{number}] " in exported


# ── The system prompt the session was opened with ──────────────────────────────

def test_a_session_can_be_opened_with_a_system_prompt():
    # Nothing reads it yet — the provider class does, in the next step — but a
    # session must be constructible with one without raising.
    assert ChatSession(system_prompt="Be brief.").is_empty
