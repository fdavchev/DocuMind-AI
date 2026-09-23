# documind/chat/message.py
#
# WHAT THIS FILE DOES:
# Defines the one thing a conversation is made of: a single turn, carrying who
# spoke, what was said, and when.
#
# WHY AN OBJECT INSTEAD OF A DICTIONARY:
# The conversation used to be a list of {"role": ..., "content": ...} dicts.
# Nothing in that shape says which keys exist, so a misspelled "contnt" is only
# discovered when a reply comes out blank in front of a user. A named field
# cannot be misspelled without an error, and it left room for the timestamp,
# which the dictionary version never had anywhere to put.
#
# WHY FROZEN:
# A turn that has been spoken is a fact about the past. Nothing downstream has
# any business rewriting what the user said, so nothing downstream is allowed to.

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Message:
    """
    One turn of a conversation.

    `role` is either "user" or "assistant" — the two speakers the UI knows how
    to draw and the prompt builder knows how to label.
    """

    role: str
    content: str
    timestamp: datetime
