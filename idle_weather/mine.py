"""Mine weather sentences from Project Gutenberg texts.

Reads plain-text books, finds the phrases in :mod:`idle_weather.phrases`,
cuts a display excerpt with Idle Hours' cleaner, scores it with Idle Hours'
quality filter plus a few weather-specific adjustments, and writes one JSONL
row per candidate. The baker (:mod:`idle_weather.bake`) turns that into the
runtime database.

    idle-weather mine --books data/gutenberg --output output/candidates.jsonl
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from collections.abc import Iterator
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from idle_hours import atomic_io
from idle_hours.clean_display_quotes import best_display_quote, curl_quotes, split_sentences
from idle_hours.enrich_metadata import parse_header
from idle_hours.gutenberg_time_miner import fetch_gutenberg_text
from idle_hours.quality_filter import score_quote

from idle_weather.conditions import CONDITIONS
from idle_weather.phrases import WEATHER_CONTEXT, WEATHER_LEXICON, compile_negative, compile_patterns

PATTERNS = compile_patterns()
NEGATIVE = compile_negative()
NEGATIVE_WINDOW = 40

_START_RE = re.compile(r"^\*\*\*\s*START OF.*?\*\*\*.*$", re.MULTILINE | re.IGNORECASE)
_END_RE = re.compile(r"^\*\*\*\s*END OF.*$", re.MULTILINE | re.IGNORECASE)
_CONTEXT_RE = re.compile(r"\b(?:" + "|".join(re.escape(w) for w in WEATHER_CONTEXT) + r")\b", re.IGNORECASE)
_VERSE_NUMBER_RE = re.compile(r"\b\d+:\d+\b")
_LEXICON_RE = re.compile(r"\b(?:" + "|".join(re.escape(w) for w in WEATHER_LEXICON) + r")\b", re.IGNORECASE)
# Titles whose full stop does not end a sentence, so the capital after them is a name ("Mrs. Gale").
_TITLE_BEFORE_RE = re.compile(r"\b(?:Mr|Mrs|Messrs|Ms|Dr|St|Mt|Capt|Col|Gen|Lt|Sgt|Rev|Prof|Sir|Lady|Lord|Miss|Master|Madame|Mme|Mlle|Monsieur|M)\.?\s*$")
_SENTENCE_START_CHARS = set(".!?\"'“‘—(:;")

# Sentences either side of the hit the cleaner may join into a run.
CONTEXT_SENTENCES = 2
# Verse: a paragraph of several short lines is a poem, and joined into prose it
# loses the line breaks that made it read.
VERSE_MIN_LINES = 3
VERSE_MAX_AVG_LINE = 48


def book_body(text: str) -> str:
    """The text between Gutenberg's START and END markers (the whole text if absent)."""
    start = _START_RE.search(text)
    if start:
        text = text[start.end():]
    end = _END_RE.search(text)
    if end:
        text = text[: end.start()]
    return text


def is_verse(lines: list[str]) -> bool:
    if len(lines) < VERSE_MIN_LINES:
        return False
    avg = sum(len(line) for line in lines) / len(lines)
    return avg < VERSE_MAX_AVG_LINE


def paragraphs(body: str) -> Iterator[str]:
    """Prose paragraphs of ``body``, each joined onto one line. Verse is skipped."""
    for block in re.split(r"\n\s*\n", body):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines or is_verse(lines):
            continue
        para = " ".join(lines)
        if sum(ch.isupper() for ch in para) > 0.5 * sum(ch.isalpha() for ch in para):
            continue
        yield re.sub(r"\s+", " ", para)


def _proper_noun(para: str, start: int, matched: str) -> bool:
    """Whether a capital in the match makes it a name ("Mr. Frost", "Snow Hill") not weather."""
    words = matched.split()
    if any(word[:1].isupper() for word in words[1:]):
        return True
    if matched[:1].isupper():
        before = para[:start].rstrip()
        if _TITLE_BEFORE_RE.search(before):
            return True
        return bool(before) and before[-1] not in _SENTENCE_START_CHARS
    return False


def _figurative(para: str, start: int, end: int) -> bool:
    window = para[max(0, start - NEGATIVE_WINDOW): end + NEGATIVE_WINDOW]
    return any(p.search(window) for p in NEGATIVE)


def find_matches(para: str) -> list[tuple[str, re.Match[str], bool]]:
    """Non-overlapping ``(condition, match, weak)`` in ``para``: longest first, ties to the earlier condition."""
    hits: list[tuple[int, int, int, str, re.Match[str], bool]] = []
    for rank, cond in enumerate(CONDITIONS):
        for pattern, weak in PATTERNS[cond]:
            for m in pattern.finditer(para):
                if not m.group(0).strip():
                    continue
                hits.append((m.start(), -(m.end() - m.start()), rank, cond, m, weak))
    hits.sort(key=lambda h: (h[1], h[2], h[0]))
    taken: list[tuple[int, int]] = []
    kept: list[tuple[int, str, re.Match[str], bool]] = []
    for start, _neg_len, _rank, cond, m, weak in hits:
        end = m.end()
        if any(start < t_end and end > t_start for t_start, t_end in taken):
            continue
        taken.append((start, end))
        kept.append((start, cond, m, weak))
    kept.sort(key=lambda k: k[0])
    return [(cond, m, weak) for _start, cond, m, weak in kept]


def _sentence_spans(para: str) -> list[tuple[int, int, str]]:
    spans = []
    pos = 0
    for sentence in split_sentences(para):
        at = para.find(sentence, pos)
        if at < 0:
            continue
        spans.append((at, at + len(sentence), sentence))
        pos = at + len(sentence)
    return spans


def weather_score(display_quote: str, matched_text: str, base: int, weak: bool) -> tuple[int, list[str]]:
    """Adjust Idle Hours' 0–100 quality score for the weather panel.

    The panel wants a sentence about the weather, so beyond Idle Hours' checks
    an excerpt gains for every other weather word it names and for scenery
    that puts it outdoors, and loses when only a bare noun found it.
    """
    score = base
    reasons: list[str] = []
    at = display_quote.lower().find(matched_text.lower())
    rest = display_quote[:at] + " " + display_quote[at + len(matched_text):] if at >= 0 else display_quote
    phrase_words = {w.lower() for w in re.findall(r"[A-Za-z]+", matched_text)}
    lexicon = {m.group(0).lower() for m in _LEXICON_RE.finditer(rest)} - phrase_words
    if lexicon:
        bonus = min(18, 6 * len(lexicon))
        score += bonus
        reasons.append(f"weather_words+{bonus}")
    context = {m.group(0).lower() for m in _CONTEXT_RE.finditer(display_quote)} - lexicon
    if context:
        bonus = min(6, 2 * len(context))
        score += bonus
        reasons.append(f"scenery+{bonus}")
    if weak:
        score -= 12
        reasons.append("weak_phrase")
    # Chapter-and-verse numbering ("43:15 By his great power…") is scripture
    # or a reference work, not a scene.
    if _VERSE_NUMBER_RE.search(display_quote):
        score -= 40
        reasons.append("verse_number")
    # The phrase should be what the sentence is about, not an aside in a long
    # run: a short excerpt with the phrase in it reads as weather.
    if len(matched_text) >= 0.5 * len(display_quote):
        score -= 15
        reasons.append("phrase_is_the_quote")
    if display_quote.count("“") + display_quote.count('"') >= 4:
        score -= 5
        reasons.append("dialogue_heavy")
    return score, reasons


def candidates_from_book(path: Path, source_id: str) -> Iterator[dict]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    title, author = parse_header(path)
    for para_index, para in enumerate(paragraphs(book_body(raw))):
        matches = find_matches(para)
        if not matches:
            continue
        spans = None
        for cond, m, weak in matches:
            matched = m.group(0).strip()
            if _proper_noun(para, m.start(), matched) or _figurative(para, m.start(), m.end()):
                continue
            # Half of a hyphenated compound ("rain-drops", "sleet-glazed"):
            # the renderer cannot highlight a span that splits a word.
            if para[m.start() - 1: m.start()] == "-" or para[m.end(): m.end() + 1] == "-":
                continue
            if spans is None:
                spans = _sentence_spans(para)
            hit = next((i for i, (s, e, _t) in enumerate(spans) if s <= m.start() < e), None)
            if hit is None:
                continue
            lo, hi = max(0, hit - CONTEXT_SENTENCES), min(len(spans), hit + CONTEXT_SENTENCES + 1)
            row = {
                "source_id": source_id,
                "title": title,
                "author": author,
                "condition": cond,
                "matched_text": matched,
                "quote_text": spans[hit][2],
                "context_text": " ".join(t for _s, _e, t in spans[lo:hi]),
                "paragraph": para_index,
                "offset": m.start(),
            }
            display, fragment, status = best_display_quote(row)
            display = curl_quotes(display)
            row["matched_text"] = curl_quotes(matched)
            if row["matched_text"].lower() not in display.lower():
                continue
            # Show the phrase as the excerpt spells it ("The rain", not "the rain").
            at = display.lower().find(row["matched_text"].lower())
            row["matched_text"] = display[at: at + len(row["matched_text"])]
            base, flags = score_quote(display, fragment, status)
            score, extra = weather_score(display, row["matched_text"], base, weak)
            del row["quote_text"], row["context_text"]
            row.update(
                display_quote=display,
                display_fragment=fragment,
                cleanup_status=status,
                quality_score=score,
                quality_flags=flags + extra,
                key=f"{source_id}:{para_index}:{m.start()}",
            )
            yield row


def book_files(books_dir: Path, ids: list[str], fetch: bool) -> Iterator[tuple[Path, str]]:
    if ids:
        for ebook_id in ids:
            path = books_dir / f"pg{ebook_id}.txt"
            if not path.exists():
                if not fetch:
                    print(f"missing {path}; pass --fetch to download it", file=sys.stderr)
                    continue
                path = fetch_gutenberg_text(ebook_id, books_dir)
            yield path, ebook_id
        return
    for path in sorted(books_dir.glob("pg*.txt")):
        yield path, path.stem[2:]


def _mine_one(item: tuple[Path, str]) -> list[dict]:
    return list(candidates_from_book(*item))


def read_book_list(path: Path) -> list[str]:
    ids = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            ids.append(line)
    return ids


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--books", default="data/gutenberg", help="Directory of pgNNN.txt files.")
    parser.add_argument("--book-list", default=None, help="File of Gutenberg ids to mine (default: every pg*.txt in --books).")
    parser.add_argument("--fetch", action="store_true", help="Download listed books missing from --books.")
    parser.add_argument("--output", default="output/candidates.jsonl")
    parser.add_argument("--jobs", type=int, default=0, help="Worker processes (default: one per CPU).")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    books_dir = Path(args.books).expanduser()
    ids = read_book_list(Path(args.book_list)) if args.book_list else []
    files = list(book_files(books_dir, ids, args.fetch))
    books = len(files)
    with ProcessPoolExecutor(max_workers=args.jobs or None) as pool:
        rows = [row for book_rows in pool.map(_mine_one, files) for row in book_rows]
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    atomic_io.atomic_write_lines(out, (json.dumps(r, ensure_ascii=False) for r in rows))
    counts = Counter(r["condition"] for r in rows)
    print(f"Mined {len(rows)} candidates from {books} books into {out}")
    for cond in CONDITIONS:
        print(f"  {cond:10} {counts.get(cond, 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
