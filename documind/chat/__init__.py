# documind/chat/__init__.py
#
# The package's public surface: a conversation, and the turns it is made of.
# Importing from the package rather than from the module inside it means a
# caller names what it wants, not where it currently lives.

from documind.chat.chat_session import ChatSession
from documind.chat.message import Message

__all__ = ["ChatSession", "Message"]
