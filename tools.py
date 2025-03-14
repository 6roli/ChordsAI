import threading
import sounddevice as sd
import matplotlib.pyplot as plt
import numpy as np
from langchain_core.tools import tool

from langchain_community.tools.tavily_search import TavilySearchResults
from dotenv import load_dotenv
from langgraph.prebuilt import ToolNode


class Tools:
    # notes_dictionary = {
    #         "C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6,
    #         "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11
    #     }
    notes_dictionary = {"cromatic":{"C":0,"D":2,"E":4,"F":5,"G":7,"A":9,"B":11},
                    "alter":{"C#":1,"Db":1,"D#":3,"Eb":3,"F#":6,"Gb":6,"G#":8,
                             "Ab":8,"A#":10,"Bb":10}}
    interval = {"2major":2,"3minor":3,"3major":4,"fourth":5,"4augm":6,"fifth":7,"5augm":8}
    triads = {"Maj":["3major","fifth"],
                        "m":["3minor","fifth"],
                        "sus2":["2major","fifth"],
                        "sus4":["fourth","fifth"],
                        "dim":["3minor","4augm"],
                        "aug":["3major","5augm"],
                        "+":["3major","5augm"]} 
    def __init__(self):
        
        load_dotenv()
        self.search_tool = TavilySearchResults(max_results=2)

    @staticmethod
    def get_frequency(note, octave):
        expo = (octave - 4) * 12 + (note - 10)
        return 440 * ((2 ** (1 / 12)) ** expo)  

    @tool
    def play_note(note, octave=4):
        "Tool to play a note."
        # Convert note name to its corresponding integer value
                # Antes --> note_value=Tools.notes_dictionary.get(note)
        note_value = Tools.notes_dictionary["cromatic"].get(note, Tools.notes_dictionary["alter"].get(note))
        if note_value is None:
            raise ValueError(f"Invalid note: {note}")

        framerate = 44100
        time = 1000
        frequency = Tools.get_frequency(note_value, octave)
        t = np.linspace(0, time / 1000, int(framerate * time / 1000))
        wave = np.sin(2 * np.pi * frequency * t)
        sd.play(wave, framerate)
        sd.wait()

        return f"Played note: {note} , at octave: {octave}"
    
    @staticmethod
    def play(frequency,time=1000,framerate=44100):
        t = np.linspace(0,time/1000,int(framerate*time/1000))
        wave = np.sin(2*np.pi * frequency * t)

        sd.play(wave,framerate)
        sd.wait()

    @tool
    def play_chord(chord):
        """Tool to play a chord."""
        root, rest = Tools.strip_chord(chord)
        root_note = Tools.notes_dictionary["cromatic"].get(root, Tools.notes_dictionary["alter"].get(root))
        # if root_note is None:
        #     raise ValueError(f"Invalid root note: {root}")
        intervals = Tools.triads.get(rest, [])
        chord_notes = [root_note] + [root_note + Tools.interval[interval] for interval in intervals]

        threads = []
        for note in chord_notes:
            freq = Tools.get_frequency(note, 4)
            th = threading.Thread(target=lambda:Tools.play(freq,1000))
            th.start()
            threads.append(th)
        
        for thread in threads:
            thread.join()
        return "Chord tool used"
    @staticmethod
    def strip_chord(chord):

        if "#" in chord or "b" in chord: #alter
            root, rest = chord[:2] , chord.split(chord[:2])[1]
        else: #cromaticos
            root, rest = chord[0] , chord.split(chord[0])[1]
        return root, rest
    

    def get_tool_node(self):
        # This is used for the stategraph (Set of tools)
        tools = [self.play_note, self.search_tool, self.play_chord]
        tool_node = ToolNode(tools=tools)
        return tool_node


