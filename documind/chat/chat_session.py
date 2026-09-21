# documind/chat/chat_session.py
#
# WHAT THIS FILE DOES:
# Holds one conversation and is the only thing allowed to change it. Messages
# are added through add_user/add_assistant, removed only by clear(), and read
# back as a tuple.
#
# WHY THE LIST IS PRIVATE:
# The old chat_history.py kept the conversation in a plain list that every
# caller held a reference to. Any module could append to it, reorder it, edit a
# message that had already been shown, or hand a completely unrelated list to
# add_message() — and none of that would raise. Here the list exists only
# inside the object, and `messages` hands out a fresh tuple, so a caller that
# mutates what it was given changes its own copy and nothing else. The
# conversation can only move forward, one message at a time, through the two
# methods that add one.

from datetime import datetime

from documind.chat.message import Message

EXPORT_HEADER = "=== Chat History Export ===\n"
EXPORT_SEPARATOR = "-" * 40 + "\n"
EMPTY_EXPORT = "No conversation history to export."


class ChatSession:
    """One conversation: its messages, and the only ways to change them."""

    def __init__(self, system_prompt: str | None = None):
        self._messages: list[Message] = []

        # Held, but deliberately not used yet: the prompt is still assembled by
        # llm_chain.py from the config. The provider class added in the next
        # step is what will read it off the session.
        self._system_prompt = system_prompt

    @property
    def messages(self) -> tuple[Message, ...]:
        """
        Every message so far, oldest first.

        A tuple, and a new one each time: a caller cannot append to it, and
        cannot reach the list the session actually keeps.
        """
        return tuple(self._messages)

    @property
    def is_empty(self) -> bool:
        """True before anything has been said."""
        return not self._messages

    def add_user(self, content: str) -> None:
        """Records what the user just sent."""
        self._add("user", content)

    def add_assistant(self, content: str) -> None:
        """Records the reply the assistant just finished streaming."""
        self._add("assistant", content)

    def clear(self) -> None:
        """Forgets the whole conversation, keeping the session itself usable."""
        self._messages.clear()

    def export(self) -> str:
        """The conversation as the plain text the sidebar offers for download."""
        if not self._messages:
            return EMPTY_EXPORT

        lines = [EXPORT_HEADER]
        for number, message in enumerate(self._messages, start=1):
            speaker = "You" if message.role == "user" else "Assistant"
            lines.append(f"[{number}] {speaker}:\n{message.content}\n")
            lines.append(EXPORT_SEPARATOR)

        return "\n".join(lines)

    def _add(self, role: str, content: str) -> None:
        self._messages.append(
            Message(role=role, content=content, timestamp=datetime.now())
        )
