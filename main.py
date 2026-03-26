# main.py — Gitly v1.0 Control Loop
import json
import os
from core.session import GitlySession
from core.processor import process_command
from Speech.text_to_speech import speak
from Speech.recognizer import recognize_speech
from helpers.cli_ui import *
from helpers.cache_maintainer import safe_dump_cache
from rapidfuzz import fuzz



def is_wake_word_spoken(command: str, wake_words: list[str], threshold=90) -> bool:
    command = command.lower().strip()


    for wake in wake_words:
        wake = wake.lower().strip()
        if command.startswith(wake):
            return True
        if fuzz.ratio(command, wake) >= threshold:  # Optional: only if entire matches

            return True
    return False


# Bootup visuals
show_banner()

# 🧠 Main Gitly session memory
gitly = GitlySession()

# Load recent repo paths and their files from JSON cache
cache_path = "cache_data/repo_cache.JSON"
if os.path.exists(cache_path):
    with open(cache_path, "r") as f:
        gitly.recent_paths = json.load(f)

# Define your custom wake words
wake_words = ["launch my assistant", "activate voice assistant", "open command centre", "run quickly"]
EXIT_COMMANDS = [
    "exit", "terminate", "shutdown", "stop", "quit", 
    "kill switch", "go offline", "deactivate", "close assistant"
]

show_info("Listening...")

while True:
    command = recognize_speech()

    if not command:
        continue

    if not gitly.is_awake:
        print("[DEBUG]")
        if is_wake_word_spoken(command, wake_words):
            gitly.activate()
            show_success("Gitly is now Active!")
            speak("Gitly is now Active!")
            speak("Hello, how can I help you today?")
        continue

    # Exit voice command
    if any(keyword in command.lower() for keyword in EXIT_COMMANDS):
        show_info("Saving your session data...")
        safe_dump_cache(gitly.recent_paths, cache_path)
        show_success("Session saved successfully.")
        speak("Shutting down Gitly. See you next time.")
        break

    # Normal processing
    process_command(command, gitly)
    safe_dump_cache(gitly.recent_paths, cache_path)

    # Sleep again
    gitly.deactivate()
    log_step("Gitly Sleeping....")
    
