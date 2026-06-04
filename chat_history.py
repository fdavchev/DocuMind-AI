# chat_history.py

def init_memory() -> list:
    """
    Creates a fresh conversation history as a plain list.
    Each entry is a dict with 'role' and 'content'.
    """
    return []


def add_message(history: list, role: str, content: str) -> list:
    """
    Appends a new message to the history.
    role must be either 'user' or 'assistant'.
    """
    history.append({"role": role, "content": content})
    return history


def get_history(history: list) -> list:
    """
    Returns the full conversation history list.
    """
    return history


def clear_history(history: list) -> list:
    """
    Wipes the conversation and returns an empty list.
    """
    history.clear()
    return history

def export_history(history: list) -> str:
    """
    Converts chat history to a formatted plain-text string for download.
    """
    if not history:
        return "No conversation history to export."

    lines = ["=== Chat History Export ===\n"]
    for i, msg in enumerate(history, 1):
        role = "You" if msg["role"] == "user" else "Assistant"
        lines.append(f"[{i}] {role}:\n{msg['content']}\n")
        lines.append("-" * 40 + "\n")

    return "\n".join(lines)