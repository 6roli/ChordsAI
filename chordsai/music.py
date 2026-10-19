"""Music theory in plain Python: note and chord names → notes with MIDI numbers and frequencies.

No language model is involved, so the notes are always right. Conventions:
- Scientific pitch notation: C4 is middle C (MIDI 60) and A4 = 440 Hz (MIDI 69).
- Notes without an octave are in octave 4; chords are built upwards from their root.
- Chord notes are spelled by degree, so Db major is Db F Ab (not C# F G#) and Cdim is C Eb Gb.
"""

import re
from dataclasses import asdict, dataclass

A4_FREQUENCY = 440.0
A4_MIDI = 69
DEFAULT_OCTAVE = 4

LETTERS = "CDEFGAB"
NATURAL_PITCH = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
ACCIDENTALS = {"": 0, "#": 1, "##": 2, "b": -1, "bb": -2}
_ACCIDENTAL_SYMBOLS = {"♯": "#", "♭": "b", "𝄪": "##", "𝄫": "bb"}

_NOTE_RE = re.compile(r"^([A-Ga-g])(##|bb|#|b)?(-?\d)?$")
_ROOT_RE = re.compile(r"^([A-Ga-g])(#|b)?(.*)$")


class MusicError(ValueError):
    """A name that is not a note or chord this module understands. The message is safe to show."""


@dataclass(frozen=True)
class Note:
    name: str  # spelled with its octave, e.g. "C#4"
    midi: int
    frequency: float  # Hz, rounded to 2 decimals

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Chord:
    name: str  # canonical symbol, e.g. "Cmaj7"
    root: str  # e.g. "C"
    quality: str  # e.g. "major seventh"
    notes: tuple[Note, ...]

    @property
    def label(self) -> str:
        return f"{self.root} {self.quality}"

    def to_dict(self) -> dict:
        return {"type": "chord", "name": self.name, "label": self.label, "notes": [n.to_dict() for n in self.notes]}


def frequency(midi: int) -> float:
    """Equal temperament, A4 = 440 Hz. (The original prototype used `note - 10`, one semitone flat.)"""
    return round(A4_FREQUENCY * 2 ** ((midi - A4_MIDI) / 12), 2)


def make_note(letter: str, accidental: str, octave: int) -> Note:
    midi = (octave + 1) * 12 + NATURAL_PITCH[letter] + ACCIDENTALS[accidental]
    if not 0 <= midi <= 127:
        raise MusicError(f"{letter}{accidental}{octave} is outside the playable range.")
    return Note(name=f"{letter}{accidental}{octave}", midi=midi, frequency=frequency(midi))


def _clean(text: str) -> str:
    text = text.strip()
    for symbol, ascii_symbol in _ACCIDENTAL_SYMBOLS.items():
        text = text.replace(symbol, ascii_symbol)
    return text


def parse_note(name: str, default_octave: int = DEFAULT_OCTAVE) -> Note:
    """'A' → A4 (440 Hz); 'c#5', 'Bb3', 'E♭' are also accepted."""
    match = _NOTE_RE.match(_clean(name))
    if not match:
        raise MusicError(f"'{name}' is not a note name. Try something like C, F#, Bb or A4.")
    letter, accidental, octave = match.groups()
    return make_note(letter.upper(), accidental or "", int(octave) if octave else default_octave)


# Intervals as (scale degree, semitones above the root). The degree decides the letter, so spelling is correct.
QUALITIES: dict[str, tuple[tuple[int, int], ...]] = {
    "major": ((1, 0), (3, 4), (5, 7)),
    "minor": ((1, 0), (3, 3), (5, 7)),
    "suspended second": ((1, 0), (2, 2), (5, 7)),
    "suspended fourth": ((1, 0), (4, 5), (5, 7)),
    "diminished": ((1, 0), (3, 3), (5, 6)),
    "augmented": ((1, 0), (3, 4), (5, 8)),
    "power chord": ((1, 0), (5, 7)),
    "dominant seventh": ((1, 0), (3, 4), (5, 7), (7, 10)),
    "major seventh": ((1, 0), (3, 4), (5, 7), (7, 11)),
    "minor seventh": ((1, 0), (3, 3), (5, 7), (7, 10)),
    "minor major seventh": ((1, 0), (3, 3), (5, 7), (7, 11)),
    "diminished seventh": ((1, 0), (3, 3), (5, 6), (7, 9)),
    "half-diminished seventh": ((1, 0), (3, 3), (5, 6), (7, 10)),
    "seventh suspended fourth": ((1, 0), (4, 5), (5, 7), (7, 10)),
    "major sixth": ((1, 0), (3, 4), (5, 7), (6, 9)),
    "minor sixth": ((1, 0), (3, 3), (5, 7), (6, 9)),
    "added ninth": ((1, 0), (3, 4), (5, 7), (9, 14)),
    "dominant ninth": ((1, 0), (3, 4), (5, 7), (7, 10), (9, 14)),
    "major ninth": ((1, 0), (3, 4), (5, 7), (7, 11), (9, 14)),
    "minor ninth": ((1, 0), (3, 3), (5, 7), (7, 10), (9, 14)),
}

# Canonical suffix shown after the root.
_SUFFIX = {
    "major": "",
    "minor": "m",
    "suspended second": "sus2",
    "suspended fourth": "sus4",
    "diminished": "dim",
    "augmented": "aug",
    "power chord": "5",
    "dominant seventh": "7",
    "major seventh": "maj7",
    "minor seventh": "m7",
    "minor major seventh": "mMaj7",
    "diminished seventh": "dim7",
    "half-diminished seventh": "m7b5",
    "seventh suspended fourth": "7sus4",
    "major sixth": "6",
    "minor sixth": "m6",
    "added ninth": "add9",
    "dominant ninth": "9",
    "major ninth": "maj9",
    "minor ninth": "m9",
}

# Case-sensitive symbols first ("M7" is major seventh, "m7" minor seventh) …
_EXACT = {
    "M": "major", "M7": "major seventh", "Maj7": "major seventh", "Δ": "major seventh", "Δ7": "major seventh",
    "mM7": "minor major seventh", "mMaj7": "minor major seventh", "M9": "major ninth", "M6": "major sixth", "°": "diminished",
    "°7": "diminished seventh", "ø": "half-diminished seventh", "ø7": "half-diminished seventh", "-": "minor",
    "-7": "minor seventh", "+": "augmented",
}
# … then lower-case spellings after normalising words like "major" and "seventh".
_LOWER = {
    "": "major", "maj": "major", "m": "minor", "min": "minor",
    "sus2": "suspended second", "sus4": "suspended fourth", "sus": "suspended fourth",
    "dim": "diminished", "o": "diminished", "aug": "augmented", "5": "power chord",
    "7": "dominant seventh", "dom7": "dominant seventh",
    "maj7": "major seventh", "ma7": "major seventh",
    "m7": "minor seventh", "min7": "minor seventh",
    "mmaj7": "minor major seventh",
    "dim7": "diminished seventh", "o7": "diminished seventh",
    "m7b5": "half-diminished seventh", "m7-5": "half-diminished seventh", "halfdim": "half-diminished seventh",
    "halfdim7": "half-diminished seventh",
    "7sus4": "seventh suspended fourth", "7sus": "seventh suspended fourth",
    "6": "major sixth", "maj6": "major sixth", "m6": "minor sixth",
    "add9": "added ninth", "add2": "added ninth",
    "9": "dominant ninth", "maj9": "major ninth", "m9": "minor ninth",
}
_WORDS = [
    (r"half[- ]?diminished", "halfdim"), (r"suspended", "sus"), (r"dominant", "dom"), (r"major", "maj"),
    (r"minor", "min"), (r"diminished", "dim"), (r"augmented", "aug"), (r"power", "5"),
    (r"seventh|7th", "7"), (r"sixth|6th", "6"), (r"ninth|9th", "9"), (r"second|2nd", "2"), (r"fourth|4th", "4"),
    (r"fifth|5th", "5"), (r"\bchord\b|\btriad\b", ""), (r"[\s()]", ""),
]
_AFTER_WORDS = {"min": "m", "minmaj7": "mmaj7", "dom": "7", "dom7": "7", "5": "5", "sus4": "sus4", "sus2": "sus2"}


def _quality(suffix: str) -> str | None:
    if suffix in _EXACT:
        return _EXACT[suffix]
    text = suffix.lower()
    for pattern, replacement in _WORDS:
        text = re.sub(pattern, replacement, text)
    text = text.replace("min7", "m7").replace("minmaj", "mmaj")
    text = _AFTER_WORDS.get(text, text)
    if text.startswith("min") and text[3:] in {"6", "9", "7b5"}:
        text = "m" + text[3:]
    return _LOWER.get(text)


def _spell(root_letter: str, root_midi: int, degree: int, semitones: int) -> Note:
    """The note `semitones` above the root, written with the letter of the given degree."""
    letter = LETTERS[(LETTERS.index(root_letter) + degree - 1) % 7]
    target = root_midi + semitones
    offset = (target - NATURAL_PITCH[letter]) % 12
    if offset > 6:
        offset -= 12
    accidental = {v: k for k, v in ACCIDENTALS.items()}[offset]
    natural_midi = target - offset
    return Note(name=f"{letter}{accidental}{natural_midi // 12 - 1}", midi=target, frequency=frequency(target))


def parse_chord(name: str, octave: int = DEFAULT_OCTAVE) -> Chord:
    """'C' → C E G; 'Am7', 'F#m', 'Bbmaj7', 'C major 7', 'D minor', 'Gsus4' … (root in the given octave)."""
    text = _clean(name)
    match = _ROOT_RE.match(text)
    if not match:
        raise MusicError(f"'{name}' does not start with a note name (A to G).")
    letter, accidental, suffix = match.groups()
    letter, accidental = letter.upper(), accidental or ""
    if "/" in suffix:
        raise MusicError(f"Slash chords like '{name}' are not supported yet; try the chord before the slash.")
    quality = _quality(suffix.strip())
    if quality is None:
        raise MusicError(
            f"I don't know the chord '{name}'. Try e.g. C, Am, F#m, Bb7, Cmaj7, Dm7, Gsus4, Bdim or Eaug."
        )
    root = make_note(letter, accidental, octave)
    notes = tuple(_spell(letter, root.midi, degree, semitones) for degree, semitones in QUALITIES[quality])
    root_name = f"{letter}{accidental}"
    return Chord(name=f"{root_name}{_SUFFIX[quality]}", root=root_name, quality=quality, notes=notes)


def keyboard(start_midi: int = 60, octaves: int = 2) -> list[dict]:
    """Keys for the on-screen piano (sharps for black keys), with the index of the white key to their left."""
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    keys, white_index = [], -1
    for midi in range(start_midi, start_midi + 12 * octaves + 1):
        name = names[midi % 12]
        black = name.endswith("#")
        if not black:
            white_index += 1
        keys.append(
            {"midi": midi, "name": f"{name}{midi // 12 - 1}", "black": black, "frequency": frequency(midi), "white_index": white_index}
        )
    return keys
