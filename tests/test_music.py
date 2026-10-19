import pytest

from chordsai.music import MusicError, frequency, keyboard, parse_chord, parse_note


def names(chord_name: str) -> list[str]:
    return [note.name for note in parse_chord(chord_name).notes]


# ------------------------------------------------------------------- frequencies


@pytest.mark.parametrize(
    ("midi", "hz"),
    [(69, 440.0), (60, 261.63), (57, 220.0), (81, 880.0), (61, 277.18), (21, 27.5), (108, 4186.01)],
)
def test_equal_temperament_with_a4_at_440(midi, hz):
    assert frequency(midi) == hz


def test_a4_is_440_not_one_semitone_flat():
    # The original prototype computed A4 as ~415 Hz (it used note - 10 instead of note - 9).
    assert parse_note("A4").frequency == 440.0


# ------------------------------------------------------------------------- notes


@pytest.mark.parametrize(
    ("text", "name", "midi"),
    [
        ("C", "C4", 60),
        ("C4", "C4", 60),
        ("c", "C4", 60),
        ("A", "A4", 69),
        ("C#", "C#4", 61),
        ("Db", "Db4", 61),
        ("Bb3", "Bb3", 58),
        ("F#5", "F#5", 78),
        ("E♭", "Eb4", 63),
        ("G♯2", "G#2", 44),
        ("B#3", "B#3", 60),  # enharmonic with C4
        ("Cb4", "Cb4", 59),  # enharmonic with B3
        ("C-1", "C-1", 0),
        (" a4 ", "A4", 69),
    ],
)
def test_parse_note(text, name, midi):
    note = parse_note(text)
    assert (note.name, note.midi) == (name, midi)


def test_enharmonic_notes_have_the_same_pitch():
    assert parse_note("C#4").frequency == parse_note("Db4").frequency


def test_note_to_dict():
    assert parse_note("A4").to_dict() == {"name": "A4", "midi": 69, "frequency": 440.0}


@pytest.mark.parametrize("text", ["", "H", "X#", "Cm", "C##x", "C10", "do", "A 4"])
def test_invalid_notes_raise_a_readable_error(text):
    with pytest.raises(MusicError):
        parse_note(text)


def test_out_of_range_note():
    with pytest.raises(MusicError, match="range"):
        parse_note("G#9")


# ------------------------------------------------------------------------ chords


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("C", ["C4", "E4", "G4"]),  # plain names play the full chord, not just the root
        ("G", ["G4", "B4", "D5"]),
        ("Am", ["A4", "C5", "E5"]),
        ("F#m", ["F#4", "A4", "C#5"]),
        ("Db", ["Db4", "F4", "Ab4"]),
        ("Ebm", ["Eb4", "Gb4", "Bb4"]),
        ("Csus2", ["C4", "D4", "G4"]),
        ("Csus4", ["C4", "F4", "G4"]),
        ("Bdim", ["B4", "D5", "F5"]),
        ("Cdim", ["C4", "Eb4", "Gb4"]),
        ("Caug", ["C4", "E4", "G#4"]),
        ("C+", ["C4", "E4", "G#4"]),
        ("G7", ["G4", "B4", "D5", "F5"]),
        ("Cmaj7", ["C4", "E4", "G4", "B4"]),
        ("Bbmaj7", ["Bb4", "D5", "F5", "A5"]),
        ("Dm7", ["D4", "F4", "A4", "C5"]),
        ("Bm7b5", ["B4", "D5", "F5", "A5"]),
        ("Bdim7", ["B4", "D5", "F5", "Ab5"]),
        ("C6", ["C4", "E4", "G4", "A4"]),
        ("Am6", ["A4", "C5", "E5", "F#5"]),
        ("Cadd9", ["C4", "E4", "G4", "D5"]),
        ("C9", ["C4", "E4", "G4", "Bb4", "D5"]),
        ("E5", ["E4", "B4"]),
        ("D7sus4", ["D4", "G4", "A4", "C5"]),
    ],
)
def test_chord_notes(text, expected):
    assert names(text) == expected


def test_chord_notes_are_spelled_by_degree():
    assert names("Eaug") == ["E4", "G#4", "B#4"]  # B#, not C
    assert names("G#aug")[-1] == "D##5"


@pytest.mark.parametrize(
    ("text", "name", "label"),
    [
        ("C major 7", "Cmaj7", "C major seventh"),
        ("C major seventh", "Cmaj7", "C major seventh"),
        ("CM7", "Cmaj7", "C major seventh"),
        ("CΔ7", "Cmaj7", "C major seventh"),
        ("Cmaj", "C", "C major"),
        ("C major", "C", "C major"),
        ("C major chord", "C", "C major"),
        ("D minor", "Dm", "D minor"),
        ("Dmin", "Dm", "D minor"),
        ("D-", "Dm", "D minor"),
        ("A minor seventh", "Am7", "A minor seventh"),
        ("A min7", "Am7", "A minor seventh"),
        ("A-7", "Am7", "A minor seventh"),
        ("G dominant seventh", "G7", "G dominant seventh"),
        ("G dominant 7", "G7", "G dominant seventh"),
        ("F diminished", "Fdim", "F diminished"),
        ("F°", "Fdim", "F diminished"),
        ("F augmented", "Faug", "F augmented"),
        ("G suspended fourth", "Gsus4", "G suspended fourth"),
        ("Gsus", "Gsus4", "G suspended fourth"),
        ("B half-diminished", "Bm7b5", "B half-diminished seventh"),
        ("Bø", "Bm7b5", "B half-diminished seventh"),
        ("C minor major 7", "CmMaj7", "C minor major seventh"),
        ("F minor 6", "Fm6", "F minor sixth"),
        ("E power chord", "E5", "E power chord"),
        ("bb", "Bb", "Bb major"),
        ("f#m", "F#m", "F# minor"),
        ("B♭m", "Bbm", "Bb minor"),
    ],
)
def test_common_spellings(text, name, label):
    chord = parse_chord(text)
    assert (chord.name, chord.label) == (name, label)


def test_case_matters_only_where_it_should():
    assert parse_chord("CM7").quality == "major seventh"
    assert parse_chord("Cm7").quality == "minor seventh"
    assert parse_chord("CMAJ7").quality == "major seventh"


def test_chord_octave():
    assert [n.name for n in parse_chord("C", octave=3).notes] == ["C3", "E3", "G3"]


def test_chord_to_dict():
    data = parse_chord("Am").to_dict()
    assert data["type"] == "chord" and data["name"] == "Am" and data["label"] == "A minor"
    assert data["notes"][0] == {"name": "A4", "midi": 69, "frequency": 440.0}


@pytest.mark.parametrize("text", ["", "H", "Cxyz", "Cmaj13#11", "hello", "C/G"])
def test_unknown_chords_raise_a_readable_error(text):
    with pytest.raises(MusicError):
        parse_chord(text)


def test_slash_chords_say_they_are_not_supported():
    with pytest.raises(MusicError, match="Slash chords"):
        parse_chord("C/G")


# ---------------------------------------------------------------------- keyboard


def test_two_octave_keyboard():
    keys = keyboard(60, 2)
    assert len(keys) == 25 and keys[0]["name"] == "C4" and keys[-1]["name"] == "C6"
    assert sum(not key["black"] for key in keys) == 15
    assert {key["name"] for key in keys if key["black"]} >= {"C#4", "F#5", "A#5"}
    a4 = next(key for key in keys if key["midi"] == 69)
    assert a4["frequency"] == 440.0 and not a4["black"]
