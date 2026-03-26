# helpers/tts_engine.py
import pyttsx3

engine = pyttsx3.init()
voices = engine.getProperty('voices')
engine.setProperty('voice', voices[1].id)  # Default voice

def speak(text):
    engine.say(text)
    engine.runAndWait()
