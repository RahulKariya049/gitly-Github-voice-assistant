import subprocess
from helpers.cache_maintainer import generate_file_dict

class GitlySession:
    def __init__(self):
        self.recent_paths = {}
        self.curr_path = ""
        self.is_awake = False
        self.entities = {}
        self.branches = []

    def activate(self):
        self.is_awake = True

    def deactivate(self):
        self.is_awake = False

    def get_all_branches(self) -> list:
        """Fetches all branches in current repo and caches them."""
        if not self.curr_path:
            return []

        if self.branches:
            return self.branches
        
        try:
            result = subprocess.run(
                ["git", "branch", "--list"],
                cwd=self.curr_path,
                capture_output=True,
                text=True
            )
            raw = result.stdout.strip().split('\n')
            cleaned = [line.replace("*", "").strip() for line in raw]
            self.branches = cleaned
            return cleaned
        except Exception as e:
            return []
        
    def get_remotes(self):
        """Fetches all remote names in current repo and caches them."""
        if not self.curr_path:
            return []

        if self.remotes:
            return self.remotes
        
        try:
            result = subprocess.run(
                ["git", "remote"],
                cwd=self.curr_path,
                capture_output=True,
                text=True
            )
            remotes_raw = result.stdout.strip().split('\n')
            self.branches = remotes_raw
            return remotes_raw.splitlines() if remotes_raw else []
        except Exception as e:
            return []
        
    def update_cache(self):
        repo_path = self.curr_path
        inner_dict = generate_file_dict(repo_path)

        self.recent_paths[repo_path] = inner_dict
        print("UPDATED CACHE")

    def get_all_files(self):
        return self.recent_paths[self.curr_path]
    
    def flush_state(self):
        self.curr_path = None
        self.entities.clear()
        self.branches = None
        # self.recent_paths remains

