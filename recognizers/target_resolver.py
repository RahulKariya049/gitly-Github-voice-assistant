import re
import os
from rapidfuzz import process
from Speech.recognizer import recognize_speech
from Speech.text_to_speech import speak
from helpers.helpers import confirm_action, get_best_match
from helpers.cli_ui import log_error,animate,log_warning,show_info
from core.session import GitlySession


def correct_targets_with_fuzzy(gitly_obj: GitlySession, raw_targets: list[str]) -> list[str]:
    """
    Resolves file targets using fuzzy matching. 
    Only shows crucial messages to keep UI minimal.
    """
    repo_path = gitly_obj.curr_path
    if not os.path.exists(repo_path):
        log_error("❌ The current repo path does not exist.")
        return []

    all_files = gitly_obj.get_all_files()
    corrected = []

    animate("📂 Resolving your file targets...")

    for target in raw_targets:
        if target in all_files:
            corrected.append(target)
            continue

        match, is_soft_guess = get_best_match(target, all_files)

        if match:
            if not is_soft_guess:
                corrected.append(match)
            else:
                if confirm_action(f"❓ Did you mean '{match}' instead of '{target}'?"):
                    corrected.append(match)
        else:
            log_warning(f"❌ Couldn't find any match for '{target}'")

    if corrected:
        show_info(f"📦 Resolved files: {corrected}")
    else:
        log_error("❌ No valid targets resolved.")

    return corrected


def extract_number_from_speech(text: str) -> int | None:
    text = text.lower()

    # Layer 1: Match direct digits like "3", "7"
    digit_match = re.search(r"\b(\d+)\b", text)
    if digit_match:
        return int(digit_match.group(1))

    # Layer 2: Match words like "three", "third"
    word_to_number = {
        "one": 1, "first": 1,
        "two": 2, "second": 2,
        "three": 3, "third": 3,
        "four": 4, "fourth": 4,
        "five": 5, "fifth": 5,
        "six": 6, "sixth": 6,
        "seven": 7, "seventh": 7,
        "eight": 8, "eighth": 8,
        "nine": 9, "ninth": 9,
        "ten": 10, "tenth": 10
    }

    for word, num in word_to_number.items():
        if word in text:
            return num

    return None


def normalize_text(text: str) -> str:
    """
    Removes filler/junk words and lowercases the text.
    """
    JUNK_WORDS = set([
    "please", "can", "you", "just", "want", "to", "the", "a", "an", "of", "it", "uh", "umm", "like",
    "run", "do", "does", "perform", "execute", "file", "files", "this", "that", "these", "those",
    "one", "ones", "thing", "stuff", "my", "in", "on", "with", "and", "also",
    "add", "push", "pull", "switch", "commit", "checkout", "create", "make", "set", "open",
    "new", "old", "latest", "earlier", "again", "back", "for", "me", "from"
    ])


    words = text.lower().strip().split()
    return " ".join(word for word in words if word not in JUNK_WORDS)


def extract_clean_entity(response: str, entity_type: str, gitly_obj: GitlySession):
    """
    Extract missing entity (branch, file, remote, etc.) from user fallback response.
    Uses basic patterns + fuzzy match from GitlySession candidates.
    """
    response = response.lower().strip()
    n_response = normalize_text(response)

    # === BRANCH ENTITIES ===
    if entity_type in ["branch", "target_branch", "source_branch"]:
        candidates = gitly_obj.get_all_branches()
        if not candidates:
            speak("No branches found in this repo.")
            return None
        
        match, is_soft = get_best_match(n_response, candidates)
        if match:
            return match
        
        speak("I couldn't understand the branch name you meant.")
        return None

    # === REMOTE ENTITY ===
    if entity_type == "remote":
        candidates = gitly_obj.get_remotes()
        if not candidates:
            speak("No remotes found in this repo.")
            return None
        
        match, is_soft = get_best_match(n_response, candidates)
        if match:
            return match
        
        speak("Couldn’t resolve the remote from your response.")
        return None

    # === FILES ENTITY ===
    if entity_type == "files":
        if not gitly_obj.curr_path:
            speak("Set the working repo path first.")
            return []

        repo_path = gitly_obj.curr_path
        candidates = list(gitly_obj.recent_paths.get(repo_path, {}).keys())

        if not candidates:
            speak("No tracked files found in this repo.")
            return []

        clean = []
        file_list = n_response.split()

        for token in file_list:
            match, _ = get_best_match(token, candidates)
            if match:
                clean.append(match)
            else:
                speak(f"⚠️ Couldn't find file similar to: '{token}'")

        if not clean:
            speak("No valid files matched from your response.")
        return clean

    return None
