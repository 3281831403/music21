#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# Name:         accept_m21abc.py
# Purpose:      Acceptance checks for ABC v2.1 information fields (K, M, L, Q)
#               appearing either on their own line or inline in square brackets.
#
# Authors:      music21 contributors
# Copyright:    Copyright © 2026 Michael Scott Asato Cuthbert
# License:      BSD, see license.txt
# -----------------------------------------------------------------------------
'''
Acceptance tests for ABC information-field handling.

Each field, whether written on its own line (``K:D``) or inline (``[K:D]``),
must take effect at the position where it appears:

* a key field changes both the key signature and the following pitches;
* a meter field changes the measure length;
* a default-length field changes the length of following notes;
* a tempo field produces a metronome mark;
* inline and whole-line spellings give the same musical result;
* a MusicXML round trip keeps the key, meter, note-length and tempo positions.

Run directly with ``python accept_m21abc.py`` or through ``pytest``.
'''
from __future__ import annotations

import os
import tempfile
import unittest

from music21 import chord as chordModule
from music21 import converter
from music21 import key as keyModule
from music21 import note as noteModule
from music21 import tempo


# Every measure below is filled exactly to its meter so the export adds no
# padding rests.
STANDALONE_ABC = '''X:1
T:Standalone fields
M:4/4
L:1/4
K:G
ABCD|
K:D
ABCD|
M:3/4
ABC|
Q:1/4=60
ABC|
'''

INLINE_ABC = '''X:1
T:Inline fields
M:4/4
L:1/4
K:G
ABCD|[K:D]ABCD|[M:3/4][L:1/8]ABCDEF|[Q:1/4=60]GABcde|
'''


def _measureList(score):
    return list(score.parts.first().getElementsByClass('Measure'))


def _musicxmlRoundTrip(score):
    handle = tempfile.NamedTemporaryFile(suffix='.musicxml', delete=False)
    filePath = handle.name
    handle.close()
    try:
        score.write('musicxml', fp=filePath)
        return converter.parse(filePath)
    finally:
        os.remove(filePath)


class TestStandaloneFields(unittest.TestCase):
    def setUp(self):
        self.score = converter.parse(STANDALONE_ABC, format='abc')
        self.measures = _measureList(self.score)

    def test_key_changes_signature_and_pitches(self):
        self.assertEqual(self.measures[0].keySignature.sharps, 1)   # G
        self.assertEqual(self.measures[1].keySignature.sharps, 2)   # D
        # C is sharped once the D-major key is in force
        self.assertEqual([n.name for n in self.measures[1].notes],
                         ['A', 'B', 'C#', 'D'])

    def test_meter_changes_measure_length(self):
        self.assertEqual(self.measures[0].timeSignature.ratioString, '4/4')
        self.assertEqual(self.measures[2].timeSignature.ratioString, '3/4')
        self.assertEqual(self.measures[2].barDuration.quarterLength, 3.0)

    def test_tempo_produces_metronome_mark(self):
        marks = list(self.score.flatten().getElementsByClass(
            tempo.MetronomeMark))
        self.assertEqual(len(marks), 1)
        self.assertEqual(marks[0].number, 60)

    def test_default_length_changes_following_notes(self):
        score = converter.parse(
            'X:1\nM:2/4\nL:1/4\nK:C\nAB|\nL:1/8\nABCD|\n',
            format='abc',
        )
        measures = _measureList(score)
        self.assertEqual([n.quarterLength for n in measures[0].notes],
                         [1.0, 1.0])
        self.assertEqual([n.quarterLength for n in measures[1].notes],
                         [0.5, 0.5, 0.5, 0.5])


class TestInlineFields(unittest.TestCase):
    def setUp(self):
        self.score = converter.parse(INLINE_ABC, format='abc')
        self.measures = _measureList(self.score)

    def test_inline_key_changes_signature_and_pitches(self):
        keySignatures = list(self.score.flatten().getElementsByClass(
            keyModule.KeySignature))
        self.assertEqual([k.sharps for k in keySignatures], [1, 2])
        self.assertEqual([n.name for n in self.measures[1].notes],
                         ['A', 'B', 'C#', 'D'])

    def test_inline_meter_changes_measure_length(self):
        ratios = {m.timeSignature.ratioString
                  for m in self.measures if m.timeSignature is not None}
        self.assertIn('3/4', ratios)

    def test_inline_default_length_changes_note_lengths(self):
        eighthMeasure = next(
            m for m in self.measures
            if m.notes and all(n.quarterLength == 0.5 for n in m.notes)
        )
        self.assertEqual(len(eighthMeasure.notes), 6)

    def test_inline_tempo_produces_metronome_mark(self):
        marks = list(self.score.flatten().getElementsByClass(
            tempo.MetronomeMark))
        self.assertEqual(len(marks), 1)
        self.assertEqual(marks[0].number, 60)

    def test_bracket_chord_is_not_swallowed(self):
        score = converter.parse(
            'X:1\nM:4/4\nL:1/4\nK:G\n[K:F]AB|[ce]FG|\n', format='abc'
        )
        chords = list(score.flatten().getElementsByClass(chordModule.Chord))
        self.assertEqual(len(chords), 1)
        self.assertEqual([p.name for p in chords[0].pitches], ['C', 'E'])
        # the field still changed the key
        self.assertEqual(
            list(score.flatten().getElementsByClass(
                keyModule.KeySignature))[-1].sharps,
            -1,
        )


class TestInlineAndStandaloneEquivalence(unittest.TestCase):
    def test_same_pitches_and_keys(self):
        standalone = converter.parse(
            'X:1\nM:4/4\nL:1/4\nK:G\nABCD|\nK:F\nABcd|\n', format='abc'
        )
        inline = converter.parse(
            'X:1\nM:4/4\nL:1/4\nK:G\nABCD|[K:F]ABcd|\n', format='abc'
        )
        self.assertEqual(
            [(n.name, n.quarterLength) for n in standalone.flatten().notes],
            [(n.name, n.quarterLength) for n in inline.flatten().notes],
        )
        self.assertEqual(
            [k.sharps for k in standalone.flatten().getElementsByClass(
                keyModule.KeySignature)],
            [k.sharps for k in inline.flatten().getElementsByClass(
                keyModule.KeySignature)],
        )


class TestMusicXmlRoundTrip(unittest.TestCase):
    def test_positions_are_stable(self):
        for abc in (STANDALONE_ABC, INLINE_ABC):
            with self.subTest(abc=abc[:20]):
                score = converter.parse(abc, format='abc')
                reloaded = _musicxmlRoundTrip(score)

                self.assertEqual(
                    _signaturePositions(score), _signaturePositions(reloaded)
                )
                self.assertEqual(
                    [n.quarterLength for n in score.flatten().notes],
                    [n.quarterLength for n in reloaded.flatten().notes],
                )
                # export introduces no padding rests
                self.assertEqual(
                    len(score.flatten().getElementsByClass(noteModule.Rest)),
                    len(reloaded.flatten().getElementsByClass(
                        noteModule.Rest)),
                )


def _signaturePositions(score):
    positions = []
    for measure in score.parts.first().getElementsByClass('Measure'):
        for element in measure:
            className = element.classes[0]
            if className not in ('Key', 'KeySignature', 'TimeSignature',
                                 'MetronomeMark'):
                continue
            positions.append((
                className,
                measure.number,
                float(element.offset),
                getattr(element, 'sharps', None),
                element.ratioString if className == 'TimeSignature' else None,
                getattr(element, 'number', None),
            ))
    return positions


if __name__ == '__main__':
    unittest.main(verbosity=2)
