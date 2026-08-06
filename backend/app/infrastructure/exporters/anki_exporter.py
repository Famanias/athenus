"""Export flashcards to standard Anki formats: CSV and .apkg.

The .apkg writer produces a minimal-but-valid Anki collection archive:

- ``collection.anki2`` (SQLite) with the ``col``, ``notes``, ``cards``,
  ``revlog`` and ``graves`` tables.
- ``media`` (a JSON mapping of media filename to hash, empty here).

Note/card data is model-version-agnostic (schema version 11 used by Anki 2.1.x).
"""
import csv
import io
import json
import os
import re
import sqlite3
import time
import uuid
import zipfile
from typing import IO, List, Optional

from app.domain.learning.entities import FlashcardCard

ANSI_TO_HTML = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
}

_TAG_RE = re.compile(r"[\s,;:]+")


def _escape_html(text: str) -> str:
    if not text:
        return ""
    out = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return out


def _tagify(concept: Optional[str]) -> str:
    if not concept:
        return "athenus"
    tags = _TAG_RE.split(concept.lower().strip())
    return " ".join(t for t in tags if t) or "athenus"


def _front_html(card: FlashcardCard) -> str:
    if card.card_type == "cloze" and card.cloze_text:
        return _escape_html(card.cloze_text)
    return _escape_html(card.front)


def _back_html(card: FlashcardCard) -> str:
    parts: List[str] = []
    if card.card_type == "cloze":
        if card.cloze_text:
            parts.append(_escape_html(card.cloze_text))
        if card.back:
            parts.append(_escape_html(card.back))
    else:
        parts.append(_escape_html(card.front))
        if card.back:
            parts.append(_escape_html(card.back))
        elif card.options:
            parts.append("<br>".join(_escape_html(o) for o in card.options))
    if card.start_time is not None:
        parts.append(f'<br><br><i><a href="athenus://seek?t={card.start_time:.1f}">Jump to source (video)</a></i>')
    return "<hr>".join(parts)


def _tags(card: FlashcardCard) -> str:
    return _tagify(card.concept_name)


def _model_definition() -> dict:
    """A single Basic+cloze-compatible model used for all exported notes."""
    return {
        "sortf": 0,
        "did": 1,
        "latexPre": "\\documentclass[12pt]{article}\n\\special{papersize=3in,5in}\n\\usepackage[utf8]{inputenc}\n\\usepackage{amssymb,amsmath}\n\\pagestyle{empty}\n\\setlength{\\parindent}{0in}\n\\begin{document}",
        "latexPost": "\\end{document}",
        "mod": int(time.time()),
        "usn": 0,
        "vers": [],
        "type": 0,
        "css": ".card { font-family: arial; font-size: 18px; text-align: center; color: black; background-color: white; }",
        "name": "Athenus Concept Card",
        "flds": [
            {"name": "Front", "ord": 0, "sticky": False, "rtl": False, "font": "Arial", "size": 18, "media": []},
            {"name": "Back", "ord": 1, "sticky": False, "rtl": False, "font": "Arial", "size": 18, "media": []},
        ],
        "tmpls": [
            {
                "name": "Card 1",
                "ord": 0,
                "qfmt": "{{Front}}",
                "afmt": "{{FrontSide}}<hr id=answer>{{Back}}",
                "bqfmt": "",
                "bafmt": "",
                "did": None,
                "bfont": "Arial",
                "bsize": 18,
            }
        ],
        "req": [[0, "all", [0]]],
    }


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------
def export_deck_csv(cards: List[FlashcardCard]) -> str:
    """Return deck contents as an Anki-importable CSV string (front,back,tags)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_MINIMAL)
    writer.writerow(["#separator:comma", "#html:true", "#tags column:3"])
    for card in cards:
        writer.writerow([_front_html(card), _back_html(card), _tags(card)])
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# .apkg export
# ---------------------------------------------------------------------------
def _init_anki_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE col (id integer primary key, crt integer not null, mod integer not null, "
        "scm integer not null, ver integer not null, dty integer not null, usn integer not null, "
        "ls integer not null, conf text not null, models text not null, decks text not null, "
        "dconf text not null, tags text not null)"
    )
    conn.execute(
        "CREATE TABLE notes (id integer primary key, guid text not null, mid integer not null, "
        "mod integer not null, usn integer not null, tags text not null, flds text not null, "
        "sfld integer not null, csum integer not null, flags integer not null, data text not null)"
    )
    conn.execute(
        "CREATE TABLE cards (id integer primary key, nid integer not null, did integer not null, "
        "ord integer not null, mod integer not null, usn integer not null, type integer not null, "
        "queue integer not null, due integer not null, ivl integer not null, factor integer not null, "
        "reps integer not null, lapses integer not null, left integer not null, odue integer not null, "
        "odid integer not null, flags integer not null, data text not null)"
    )
    conn.execute(
        "CREATE TABLE revlog (id integer primary key, cid integer not null, usn integer not null, "
        "ease integer not null, ivl integer not null, lastIvl integer not null, factor integer not null, "
        "time integer not null, type integer not null)"
    )
    conn.execute(
        "CREATE TABLE graves (usn integer not null, oid integer not null, type integer not null)"
    )


def export_deck_apkg(cards: List[FlashcardCard], output: IO[bytes]) -> None:
    """Write a valid Anki .apkg archive for the given cards to ``output``."""
    now_ms = int(time.time() * 1000)
    model_id = 1600000000000
    deck_id = 1
    deck_name = "Athenus"

    col_conf = {
        "activeDecks": [deck_id],
        "curDeck": deck_id,
        "newSpread": 0,
        "collapseTime": 1200,
        "timeLim": 0,
        "estTimes": True,
        "dueCounts": True,
        "curModel": str(model_id),
        "nextPos": len(cards) + 1,
        "sortType": "noteFld",
        "sortBackwards": False,
        "addToCur": True,
    }
    models = json.dumps({str(model_id): _model_definition()})
    decks = json.dumps({str(deck_id): {"id": deck_id, "name": deck_name, "mod": now_ms // 1000, "usn": -1, "lrnToday": [0, 0], "revToday": [0, 0], "newToday": [0, 0], "timeToday": [0, 0], "dyn": 0, "extendNew": 10, "extendRev": 50, "conf": 1, "collapsed": False}})
    dconf = json.dumps({"1": {"id": 1, "mod": now_ms // 1000, "name": "Default", "usn": -1, "maxTaken": 60, "autoplay": True, "timer": 0, "replayq": True, "new": {"bury": False, "delays": [1, 10], "initialFactor": 2500, "ints": [1, 4, 7], "order": 1, "perDay": 20, "separate": True}, "rev": {"bury": False, "ease4": 1.3, "ivlFct": 1, "maxIvl": 36500, "minInt": 1, "fuzz": 0.05, "perDay": 200, "hardFactor": 1.2}, "lapse": {"delays": [10], "mult": 0, "minInt": 1, "leechFails": 8, "leechAction": 0}, "dyn": False}})

    import tempfile

    db_path = os.path.join(tempfile.gettempdir(), f"anki_{uuid.uuid4().hex}.anki2")
    conn = sqlite3.connect(db_path)
    _init_anki_db(conn)
    conn.execute(
        "INSERT INTO col (id, crt, mod, scm, ver, dty, usn, ls, conf, models, decks, dconf, tags) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (1, now_ms // 1000, now_ms // 1000, now_ms // 1000, 11, 0, 0, 0, json.dumps(col_conf), models, decks, dconf, "{}"),
    )
    now_secs = now_ms // 1000
    for i, card in enumerate(cards):
        nid = now_ms + i
        guid = uuid.uuid4().hex
        csum = sum(ord(ch) for ch in (card.front or "")) & 0xFFFFFFFF
        front = _front_html(card)
        back = _back_html(card)
        conn.execute(
            "INSERT INTO notes (id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (nid, guid, model_id, now_secs, -1, _tags(card), json.dumps([front, back], ensure_ascii=False), 0, csum, 0, ""),
        )
        conn.execute(
            "INSERT INTO cards (id, nid, did, ord, mod, usn, type, queue, due, ivl, factor, reps, lapses, left, odue, odid, flags, data) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (nid + 1000, nid, deck_id, 0, now_secs, -1, 0, 0, i + 1, 0, 2500, 0, 0, 0, 0, 0, 0, ""),
        )
    conn.commit()
    conn.close()
    with open(db_path, "rb") as f:
        collection_bytes = f.read()
    try:
        os.remove(db_path)
    except OSError:
        pass

    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("collection.anki2", collection_bytes)
        zf.writestr("media", "{}")
