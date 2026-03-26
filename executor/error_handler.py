import subprocess
from Speech.recognizer import recognize_speech
from Speech.text_to_speech import speak
from helpers.helpers import confirm_action
import os

def handle_git_error(args, error_msg, cwd):
    err = error_msg.lower()

    # 1. Not a Git repository
    if "not a git repository" in err:
        return handle_not_a_git_repo(args, cwd)

    # 2. Working tree clean
    if "nothing to commit" in err and "working tree clean" in err:
        speak("[Gitly]: Looks like there's nothing to commit. Everything’s clean.")
        speak("Try `git status` to double-check your staging area.")
        return None

    # 3. Upstream missing
    if "no upstream branch" in err or "no configured push destination" in err:
        return resolve_missing_upstream(args, cwd)

    # 4. Non-fast-forward push
    if "updates were rejected because the tip of your current branch is behind" in err:
        return handle_non_fast_forward(args, error_msg, cwd)

    # 5. Permission/SSH/Auth problems
    if "permission denied" in err or "could not read from remote" in err:
        speak("Permission denied. Check your SSH key or Git credentials.")
        return

    if "authentication failed" in err or "permission denied (publickey)" in err:
        speak("Authentication failed. You may need to configure your SSH keys or use a token.")
        return

    # 6. Merge conflict
    if "automatic merge failed" in err or "fix conflicts and then commit" in err:
        return handle_conflict(args, error_msg, cwd)

    # 7. Pathspec: file or branch doesn't exist
    if "pathspec" in err and "did not match any" in err:
        speak("Git couldn't find the file or branch you mentioned.")
        speak("Check the name for typos or make sure it exists.")
        return

    # # 8. Detached HEAD
    # if "you are in 'detached head' state" in err:
    #     speak("You're in a detached HEAD state — not on any branch.")
    #     speak("To save your changes, consider creating a new branch before committing.")
    #     return

    # 9. Unknown
    speak("An unknown Git error occurred.")
    speak("Try running the command manually for more insights.")
    return


def check_unresolved_conflicts(cwd: str) -> list[str] | None:
    result = run_git_command(["git", "diff", "--name-only", "--diff-filter=U"], cwd)

    return result.strip().splitlines() if result else []


def get_current_branch(repo_path: str) -> str | None:
    """
    Gets the name of the currently checked-out branch.
    """
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=repo_path,
        capture_output=True,
        text=True
    )
    return result.stdout.strip() if result.returncode == 0 else None


def run_git_command(args, cwd, capture=True):
    try:
        result = subprocess.run(
            args,
            cwd=cwd,
            capture_output=capture,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        stderr_or_stdout = (e.stderr or e.stdout or "").strip()
        print("[Gitly]: Git command failed.")
        print(f"[Git Error]: {stderr_or_stdout}")

        #intelligent handling
        handled = handle_git_error(args, stderr_or_stdout, cwd)
        return handled  # Could be string or None
    except FileNotFoundError:
        print("[Gitly]: This path doesn't seem like a Git repository.")
        return None


def resolve_missing_upstream(args, cwd):
    branch = run_git_command(["git", "branch", "--show-current"], cwd)
    if confirm_action(f"Looks like the branch '{branch}' has no upstream. Should I set origin and push?"):
        return run_git_command(["git", "push", "--set-upstream", "origin", branch], cwd)
    return None


def handle_non_fast_forward(args, error_msg, cwd):
    speak("[Gitly]: Your local branch is behind the remote branch.")
    if confirm_action("Should I pull the latest changes and then try pushing again?"):
        # Extract branch name
        current_branch = get_current_branch(cwd)
        remote = "origin"  # You can improve this by reading from args if needed

        pull_result = run_git_command(["git", "pull", remote, current_branch], cwd=cwd)
        if not pull_result:
            speak("[Gitly]: Pull failed. Merge conflicts or other issues might be there.")
            return None

        push_result = run_git_command(args, cwd=cwd)
        if push_result:
            speak("[Gitly]: Pulled latest changes and pushed successfully.")
        return push_result
    else:
        speak("[Gitly]: Okay, push cancelled.")
        return None


def handle_conflict(args, cwd):
    # 1. Detect merge conflict from 'args' or message
    if "merge" in args or "pull" in args:
        # 2. Inform the user
        speak("Looks like a merge conflict happened.")
        
        # 3. Get list of conflicting files
        conflict_files = check_unresolved_conflicts(cwd)

        if conflict_files:
            speak(f"The following files are in conflict: {', '.join(conflict_files)}")
            
            # 4. Offer to open VS Code
            if confirm_action("Would you like me to open these in VS Code to resolve manually?"):
                for file in conflict_files:
                    run_git_command(["code", "--diff", file, file], cwd)  # fallback: just open the file
                speak("VS Code opened. After resolving, run `git add` and `git commit`.")
                return True
            
            # 5. Optional: automate git mergetool
            elif confirm_action("Want me to launch Git's built-in merge tool?"):
                run_git_command(["git", "mergetool"], cwd)
                speak("Merge tool launched.")
                return True

            else:
                speak("Alright. Resolve manually and run `git add` and `git commit`.")
                return True
        else:
            speak("Conflict occurred, but couldn't detect specific files.")
            return True

    return False


def handle_not_a_git_repo(args, cwd):
    speak("Hmm... this directory is not a Git repository.")

    if confirm_action("Should I initialize a new Git repo here for you?"):
        result = run_git_command(["git", "init"], cwd)
        if result:
            speak("Git repository initialized successfully.")

            handle_remote(args, cwd)

            # ⚠️ Optional: create a default .gitignore file (user-confirmed)
            if confirm_action("Would you like me to add a basic README and .gitignore?"):
                ignore_path = os.path.join(cwd, ".gitignore")
                with open(ignore_path, "w") as f:
                    f.write("__pycache__/\n*.log\n.env\n*.pyc\n.DS_Store\n")

                readme_path = os.path.join(cwd, "README.md")
                with open(readme_path, "w") as f:
                    f.write("# Project Title\n\nThis is a newly initialized Git repository.")

                
                run_git_command(["git", "add", "."], cwd)
                speak(".gitignore file created and staged.")
        else:
            speak("Something went wrong while initializing the Git repository.")
    else:
        speak("Okay. Not initializing anything.")


def handle_remote(args,cwd):
    if confirm_action("Would you like to link a remote repository too?"):
        speak("can you paste your remote URL below")
        remote_url = input("Paste URL here:")

        if remote_url and (remote_url.startswith("http") or remote_url.startswith("git@")):
            run_git_command(["git", "remote", "add", "origin", remote_url], cwd)
            speak("Remote 'origin' added.")
        else:
            speak("Hmm, the URL didn't seem valid. Skipping remote setup.")


def handle_conflict_not_resolved(args, error_msg, cwd):
    conflicted_files = check_unresolved_conflicts(cwd)

    if conflicted_files:
        speak("Merge conflicts detected in the following files:")
        for f in conflicted_files:
            print(" -", f)

        if confirm_action("Would you like me to open these in VS Code?"):
            run_git_command(["code", "."], cwd)

        speak("Please resolve the conflicts manually. I’ll wait here.")
        return None  # Assistant sleeps until next command
    else:
        # No conflicts found — user resolved manually
        if confirm_action("All conflicts seem resolved. Should I stage and commit the changes for you?"):
            run_git_command(["git", "add", "."], cwd)
            run_git_command(["git", "commit", "-m", "Resolved merge conflicts"], cwd)
            speak("Great! I’ve committed the resolved changes.")
        else:
            speak("Alright. You can commit them yourself whenever you're ready.")

        return None
