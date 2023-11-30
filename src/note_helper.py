import math
import re

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]            

RE_NOTE_NAME = re.compile("([A-G]#?)(\d)")


def frequency_to_note(freq, standard_pitch=440.0, rounding=True):
    if freq == 0.0:
        return -1

    # 12-tone equal temperament
    C0 = standard_pitch * math.pow(2.0, -4.75)            
    value = 12 * math.log2(freq / C0)

    if rounding:
        value = round(value)

    return value


def note_to_frequency(note, standard_pitch=440.0):
    C0 = standard_pitch * math.pow(2.0, -4.75)   

    return C0 * math.pow(2.0, note / 12.0)


def note_name_to_value(note_name):
    name, octave = parse_note_name(note_name)    

    return 12 * octave + NOTE_NAMES.index(name) 


def value_to_note_name(value):
    octave = value // 12
    n = value % 12 

    return NOTE_NAMES[n] + str(octave)       


def parse_note_name(note_name):
    m = RE_NOTE_NAME.match(note_name)

    assert m

    name, octave = m.groups()

    return name, int(octave)


def get_note_distance(note_a, note_b):
    value_a = note_name_to_value(note_a)
    value_b = note_name_to_value(note_b)

    return abs(value_a - value_b)