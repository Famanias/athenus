import re
from typing import List

CONVERSATIONAL_PATTERNS = [
    r"^\s*(hi|hello|hey|greetings|good\s+(morning|afternoon|evening|day|night)|howdy|sup)\s*[!.\?]*\s*$",
    r"^\s*(how\s+are\s+you|how\s+is\s+it\s+going|what['\s]*s\s+up|how\s+do\s+you\s+do)\s*[!.\?]*\s*$",
    r"^\s*(thanks|thank\s+you|thx|cheers|much\s+appreciated)\s*[!.\?]*\s*$",
    r"^\s*(bye|goodbye|see\s+you|see\s+ya|farewell|cya)\s*[!.\?]*\s*$",
    r"^\s*(ok|okay|cool|awesome|great|got\s+it|nice|understood|sure)\s*[!.\?]*\s*$",
    r"^\s*(who\s+are\s+you|what\s+is\s+your\s+name|what\s+can\s+you\s+do)\s*[!.\?]*\s*$",
]


def is_conversational_query(query: str) -> bool:
    """Detects if a user query is a purely social, conversational, or non-informational turn.

    Non-informational queries should bypass vector retrieval context to prevent prompt context pollution
    and eliminate spurious citation generation.
    """
    if not query or not query.strip():
        return True

    normalized = query.strip().lower()

    # 1. Regex pattern matching for standard conversational turns
    for pattern in CONVERSATIONAL_PATTERNS:
        if re.match(pattern, normalized, re.IGNORECASE):
            return True

    # 2. Short single-word greetings or pleasantries without domain terms
    words = re.findall(r'\w+', normalized)
    if len(words) == 1 and words[0] in {"hi", "hello", "hey", "thanks", "thx", "bye", "ok", "okay"}:
        return True

    return False
