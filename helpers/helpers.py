from enum import Enum
from rapidfuzz import fuzz, process
from Speech.recognizer import recognize_speech
from Speech.text_to_speech import speak

def get_best_match(spoken: str, candidates: list[str], hard_threshold=80, soft_threshold=60) -> tuple[str | None, bool]:
    """
    Returns: (best_match or None, is_soft_match: bool)
    this function returns a flag for soft guesses like if we don't find any best match as fallback flag
    """
    spoken_clean = spoken.lower().strip()
    if not spoken_clean or len(spoken_clean) < 2:
        return None, False

    normalized_candidates = {c.lower().strip(): c for c in candidates}
    match = process.extractOne(spoken_clean, normalized_candidates.keys())

    if match:
        name, score, _ = match
        best = normalized_candidates[name]

        if score >= hard_threshold:
            return best, False  # confident
        elif score >= soft_threshold:
            return best, True  # soft guess

    return None, False  # nothing matched


class ConfirmationIntent(Enum):
    CONFIRM = "confirm"
    DENY = "deny"
    UNCERTAIN = "uncertain"

CONFIRM_PHRASES = {
    "yes", "yeah", "yup", "sure", "go ahead", "absolutely", "please do",
    "of course", "totally", "i want that", "fine", "do it", "why not",
    "definitely", "sounds good", "alright", "yessir", "make it so", "okay", "yea sure"
}
  
DENY_PHRASES = {
    "no", "nope", "nah", "don't", "stop", "cancel", "not now",
    "leave it", "skip", "not this", "never", "i don’t think so", "forget it",
    "i said no", "abort", "nah man", "not required", "don’t do it"
}   

NOISE_WORDS = {
    "uh", "um", "like", "you know", "i think", "maybe", "actually", "literally", 
    "honestly", "kinda", "sort of", "probably", "yeah maybe", "you see", "i guess"
}


def clean_reply(raw_text: str) -> str:
    cleaned = raw_text.lower()
    for word in NOISE_WORDS:
        cleaned = cleaned.replace(word, "")
    return cleaned.strip()


def detect_confirmation_intent(reply: str) -> ConfirmationIntent:
    cleaned = clean_reply(reply)
    for phrase in CONFIRM_PHRASES:
        if fuzz.ratio(cleaned, phrase) >= 85:
            return ConfirmationIntent.CONFIRM
    for phrase in DENY_PHRASES:
        if fuzz.ratio(cleaned, phrase) >= 85:
            return ConfirmationIntent.DENY
    return ConfirmationIntent.UNCERTAIN


def confirm_action(prompt="Should I continue?") -> bool:
    speak(prompt)
    for _ in range(2):
        reply = recognize_speech()

        intent = detect_confirmation_intent(reply)
        if intent == ConfirmationIntent.CONFIRM:
            return True
        elif intent == ConfirmationIntent.DENY:
            speak("Okay, action canceled.")
            return False
        else:
            speak("Sorry, I couldn't understand what you have said..can you say it again")
            
    return False
