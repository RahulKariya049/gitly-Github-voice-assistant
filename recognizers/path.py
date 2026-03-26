import os
import re
# from helpers.helpers import get_best_match
import subprocess
# def filter_folder_tokens(chunks: list[str]) -> list[str]:
#     """
#     Cleans junk words from within each chunk like:
#     'that project' → 'project'
#     'some emt folder' → 'emt folder'
#     """
#     noise_words = {
#         "this", "that", "some", "one", "a", "an", "any", "another", 
#         "folder", "directory", "file", "again", "you", "will"
#     }

#     cleaned = []
#     for chunk in chunks:
#         # Remove noise words within chunk
#         words = chunk.split()
#         filtered = [w for w in words if w.lower() not in noise_words]
#         new_chunk = " ".join(filtered).strip()
#         if new_chunk:
#             cleaned.append(new_chunk)
    
#     return cleaned


# def normalize_text(text: str) -> str:
#     text = text.lower().replace(",", "").strip()
    
#     noise_words = [
#         "uh", "umm", "um", "like", "please", "can you", 
#         "you know", "i mean", "actually", "basically", "so"
#     ]
    
#     for noise in noise_words:
#         pattern = r"\b" + re.escape(noise) + r"\b"
#         text = re.sub(pattern, "", text)
    
#     # Also remove extra spaces
#     text = re.sub(r"\s+", " ", text)
#     return text.strip()


# def segment_and_extract(text_cmd: str):
#     """
#     Break down user's natural path command into drive and folder segments.
#     Handles cases like 'D drive', 'cd into downloads', 'go to D gitly', etc.
#     """

#     connector_words = ['then', 'and then', 'after that', 'inside', 'in', 'into', 
#                        'open', 'find', 'go to', 'cd', 'enter', 'explore', 'navigate to']

#     # Normalize
#     text_cmd = normalize_text(text_cmd)

#     # Detect drive in a smarter way
#     drive_match = re.search(r'\b([a-z])\s*(?:drive|:)\b', text_cmd, re.IGNORECASE)
#     drive = f"{drive_match.group(1).upper()}:" if drive_match else ""

#     # Split using connectors
#     pattern = r"\b(?:{})\b".format("|".join(re.escape(w) for w in connector_words))
#     raw_chunks = re.split(pattern, text_cmd, flags=re.IGNORECASE)
#     folder_tokens = [chunk.strip().lower() for chunk in raw_chunks if chunk.strip()]

#     return drive, folder_tokens


# def fuzzy_correct_chunks(drive: str, folder_tokens: list[str]) -> dict:
#     """
#     Returns:
#     {
#         "partial_path": str,  # joined matched folders (even if soft matched)
#         "unmatched_tokens": list[str],  # tokens with no match
#         "suggestions": dict[str, list[str]],  # {token: [close_suggestions]}
#         "is_soft": bool,  # any soft match happened
#         "is_crashed": bool,  # true if we couldn't traverse further
#     }
#     """

#     current_path = drive + os.sep
#     matched_folders = []
#     unmatched_tokens = []
#     suggestions = {}

#     is_crashed = False
#     any_soft = False

#     for token in folder_tokens:
#         try:
#             dir_contents = os.listdir(current_path)
#         except FileNotFoundError:
#             # Directory is broken, stop path advancement
#             is_crashed = True
#             dir_contents = []  # simulate crash: still attempt suggestions in same dir

#         if is_crashed:
#             unmatched_tokens.append(token)
#             continue

#         best_match, is_soft = get_best_match(token, dir_contents)

#         if best_match:
#             matched_folders.append(best_match)
#             if is_soft:
#                 suggestions[token] = best_match
#                 any_soft = True

#             if not is_crashed:
#                 current_path = os.path.join(current_path, best_match)

#         else:
#             unmatched_tokens.append(token)

#             # NOTE: current_path is not advanced in this case

#     return {
#         "path_joined": os.path.join(drive, *matched_folders),
#         "unmatched_tokens": unmatched_tokens,
#         "suggestions": suggestions,
#         "is_soft": any_soft,
#         "is_crashed": is_crashed,
#     }



# Basic pipeline controller
def parse_path_command(cmd: str) -> str | None:
    # print(f"Raw Input: {cmd}")

    # # Step 1: Normalize
    # cmd = normalize_text(cmd)

    # # Step 2: Segment
    # drive, folder_chunks = segment_and_extract(cmd)

    # # Step 3: Fallback if no drive detected
    # if not drive:
    #     drive = 'C:'

    # #Step 4:Clear Folder tokens
    # dict1 = fuzzy_correct_chunks(drive, folder_chunks)
    result = subprocess.run(
        ['git', 'rev-parse', '--show-toplevel'],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print("You're not inside a git repository. Please navigate to one first.")
        return
    
    repo_path = result.stdout.strip()
    return repo_path


# testing some commands
if( __name__ == "__main__"):
    print("Resolved Path: ", parse_path_command("123"))