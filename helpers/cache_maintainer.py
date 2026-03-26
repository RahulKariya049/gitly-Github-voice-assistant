import os
from helpers.helpers import get_best_match, confirm_action
from Speech.recognizer import recognize_speech

#Example Cache
{
  "D:/GitDemo": {
    "README.md": [
      "D:/GitDemo/README.md",
      "D:/GitDemo/docs/README.md"
    ],
    "main.py": ["D:/GitDemo/main.py"]
  },
  "D:/AnotherRepo": {
    "app.py": ["D:/AnotherRepo/app.py"]
  }
}

def generate_file_dict(repo_path: str) -> dict[str, list[str]]:
    """
    Walks through a repo and maps each file to a list of its absolute paths (excluding .git, __pycache__, etc.).
    """
    file_map = {}
    ignored_dirs = {".git", "__pycache__", ".venv"}

    for root, dirs, files in os.walk(repo_path):
        # Extract directory name and ignore if theyare .git or pycache and other
        root_dir = os.path.basename(root)
        # Skip invalid or junk dirs
        if any(skip in root.lower() for skip in ("__pycache__", ".git", ".venv", "site-packages", "$recycle.bin")):
          continue


        for fname in files:
            abs_path = os.path.normpath(os.path.join(root, fname))
            if(fname in file_map):
              file_map[fname].append(abs_path)
            else:
                file_map[fname] = [abs_path]

    return file_map



def find_file_in_cache(filename: str, repo_cache: dict) -> list[tuple[str, list[str]]]:
    """
    Returns a list of (repo_path, list of full_file_paths) tuples where the filename was found.
    """
    matches = []

    #Repo path is like location to git repo
    # files actually is a inner dict where filename is key and list of full paths as value
    for repo_path, files in repo_cache.items():
        match, is_soft = get_best_match(filename, list(files.keys()))

        if match:
            if not is_soft:
                matches.append((repo_path, files[match]))
            else:
                if confirm_action("[Gitly]: Did you mean this: {match} instead of {filename}?"):
                    matches.append((repo_path, files[match]))
                else:
                    print("[Gitly]: Let's try again.")
                # Either way, continue searching other repos
        # else: skip this repo silently

    return matches

import json

def safe_dump_cache(cache_data: dict, path: str):
    try:
        with open(path, "w") as f:
            json.dump(cache_data, f, indent=4)
    except Exception as e:
        print("[Gitly]: Failed to save cache:", str(e))

# if(__name__ == "__main__"):
#     path = "D:\Python\GitHub Voice Assistant"
#     generate_file_dict(path)