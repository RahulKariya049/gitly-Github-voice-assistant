import subprocess
import os
from core.session import GitlySession
from Speech.recognizer import recognize_speech
from Speech.text_to_speech import speak
from helpers.helpers import confirm_action
from executor.error_handler import handle_git_error
from recognizers.target_resolver import extract_clean_entity
from helpers.cli_ui import log_success,log_warning

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


def ask_commit_message(default_msg):
    print("[Gitly]: What message should I use for the commit?")
    reply = recognize_speech()
    if reply and len(reply.strip()) > 4:
        return reply.strip()
    return default_msg


def parse_status_lines(repo_path):
    output = run_git_command(["git", "status", "--porcelain"], cwd=repo_path)
    file_statuses = []

    for line in output.splitlines():
        if len(line) < 4:
            continue  # malformed line
        staged = line[0]
        unstaged = line[1]
        path = line[3:].strip()

        file_statuses.append({
            "path": path,
            "staged": staged,
            "unstaged": unstaged,
        })

    return file_statuses


def check_unstaged(repo_path, targets):
    statuses = parse_status_lines(repo_path)
    unstaged = []

    for item in statuses:
        if item["path"] in targets and item["unstaged"] in {"M", "A", "?"}:
            unstaged.append(item["path"])

    return unstaged


def get_current_branch(repo_path: str) -> str | None:
    result = run_git_command(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_path)
    return result.strip() if result else None


def handle_branch(gitly_obj: GitlySession):
    if gitly_obj.entities.get("target_branch"):
        return  # Already extracted

    # Get current branch as fallback
    curr_branch = get_current_branch(gitly_obj.curr_path)
    if not curr_branch:
        print("[Gitly]: Could not determine current branch.")
        return
    
    # Ask for confirmation
    if confirm_action(f"[Gitly]: You're currently on the '{curr_branch}' branch. Do you want to use this?"):
        gitly_obj.entities["target_branch"] = curr_branch
    else:
        speak("[Gitly]: Which branch do you want to use?")
        reply = recognize_speech()
        branch = extract_clean_entity(reply, "branch", gitly_obj)
        gitly_obj.entities["target_branch"] = branch


def handle_remote(gitly_obj: GitlySession):
    if gitly_obj.entities.get("remote"):
        return  # Already captured

    remotes = gitly_obj.get_remotes()

    if not remotes:
        speak("[Gitly]: No remote repositories are configured.")
        return

    if len(remotes) == 1:
        gitly_obj.entities["remote"] = remotes[0]
        return

    # Multiple remotes, ask user
    speak("[Gitly]: Multiple remotes found. Which one should I use?")
    for i, r in enumerate(remotes):
        print(f"{i+1}. {r}")
    
    reply = recognize_speech()
    chosen = extract_clean_entity(reply, "remote", gitly_obj)
    if chosen in remotes:
        gitly_obj.entities["remote"] = chosen
    else:
        speak("[Gitly]: I couldn't match your response to a remote. Please try again.")


def execute_add(gitly_obj: GitlySession):
    repo_path = gitly_obj.curr_path
    targets = gitly_obj.entities.get("files", [])

    if not targets:
        speak("[Gitly]: No files specified to add. Cannot proceed.")
        return

    speak(f"[Gitly]: Adding {len(targets)} file(s) to staging area.")
    
    for file in targets:
        result = run_git_command(["git", "add", file], cwd=repo_path)
        if result is not None:
            print(f"[Gitly]: Staged {file}.")
        else:
            speak(f"[Gitly]: Couldn't add {file}. Please check the filename.")


def execute_commit(gitly_obj: GitlySession):
    corrected_targets = gitly_obj.entities.get("files", [])
    repo_path = gitly_obj.curr_path

    if not corrected_targets:
        speak("You haven't specified which files to commit.")
        return

    # Step 1: Check if unstaged
    unstaged = check_unstaged(repo_path, corrected_targets)
    log_warning(f"Unstaged Files: {unstaged}")
    if unstaged:
            if confirm_action("[Gitly]: Should I stage them for you?"):
                for file in unstaged:
                    run_git_command(["git", "add", file], cwd=repo_path)
            else:
                print("[Gitly]: Skipping staging.")

    # Step 2: Ask or generate commit message
    if not gitly_obj.entities["message"]:
        commit_msg = ask_commit_message(f"Gitly Commit: {', '.join(corrected_targets)}")
    else:
        commit_msg = gitly_obj.entities["message"]
        
    # Step 3: Run commit
    result = run_git_command(["git", "commit", "-m", commit_msg], cwd=repo_path)

    # Step 4: Post-check
    if not result:
        speak("Hmm. Looks like there was nothing to commit or an error occurred.")
    else:
        speak("Commit completed.")


def execute_push(gitly_obj : GitlySession):
    handle_branch(gitly_obj)
    handle_remote(gitly_obj)

    branch = gitly_obj.entities.get("target_branch")
    remote = gitly_obj.entities.get("remote")

    result = run_git_command(["git", "push", remote, branch], cwd=gitly_obj.curr_path)
    print(result)


def execute_pull(gitly_obj : GitlySession):
    handle_branch(gitly_obj)
    handle_remote(gitly_obj)

    branch = gitly_obj.entities.get("target_branch")
    remote = gitly_obj.entities.get("remote")

    result = run_git_command(["git", "pull", remote, branch], cwd=gitly_obj.curr_path)
    print(result)


def execute_checkout(gitly_obj: GitlySession):
    handle_branch(gitly_obj)

    branch = gitly_obj.entities.get("target_branch")
    if not branch:
        speak("[Gitly]: I still couldn't figure out the branch you want to switch to.")
        return

    result = run_git_command(["git", "checkout", branch], cwd=gitly_obj.curr_path)
    if result:
        log_success(f"[Gitly]: Switched to branch '{branch}'.")
        speak(f"Successfully Switched to '{branch}'.")


def execute_status(gitly_obj: GitlySession):
    result = run_git_command(["git", "status"], cwd=gitly_obj.curr_path)
    if result:
        print(f"[Git Status]:\n{result}")


def execute_merge(gitly_obj:GitlySession):
    source_branch = gitly_obj.entities.get("source_branch")
    target_branch = gitly_obj.entities.get("target_branch")

    if not target_branch:
     # Determine current branch
        curr_branch = get_current_branch(gitly_obj.curr_path)

        # Ask user before assuming
        if confirm_action(f"[Gitly]: You are currently on '{curr_branch}'. Do you want to merge into this branch?"):
            gitly_obj.entities["target_branch"] = curr_branch
        else:
            speak("[Gitly]: Which branch should I merge into?")
            reply = recognize_speech()
            target = extract_clean_entity(reply, "branch", gitly_obj)
            gitly_obj.entities["target_branch"] = target


    if not source_branch:
        speak("[Gitly]: Which branch do you want to merge into this one?")
        reply = recognize_speech()
        source_branch = extract_clean_entity(reply, "branch", gitly_obj)
        gitly_obj.entities["source_branch"] = source_branch

    if not source_branch or not target_branch:
        speak("[Gitly]: I still couldn't identify the branches to merge.")
        return

    # Step 1: Checkout target branch
    result = run_git_command(["git", "checkout", target_branch], cwd=gitly_obj.curr_path)
    if not result:
        speak(f"[Gitly]: Couldn't switch to branch {target_branch}. Merge aborted.")
        return

    # Step 2: Merge source branch
    result = run_git_command(["git", "merge", source_branch], cwd=gitly_obj.curr_path)

    if result:
        speak(f"[Gitly]: Successfully merged '{source_branch}' into '{target_branch}'.")
    else:
        speak(f"[Gitly]: Merge failed or has conflicts. Please check manually.")


def execute_add_remote(gitly_obj : GitlySession):
    remote_url = gitly_obj.entities["url"]
    cwd=gitly_obj.curr_path

    if remote_url and (remote_url.startswith("http") or remote_url.startswith("git@")):
            run_git_command(["git", "remote", "add", "origin", remote_url], cwd)
            speak("Remote 'origin' added.")
    else:
            speak("Hmm, the URL didn't seem valid. Skipping remote setup.")


def execute_init(gitly_obj : GitlySession):
    cwd = gitly_obj.curr_path

    if os.path.exists(os.path.join(cwd, ".git")):
        speak("This folder is already a Git repository.")
        return


    result = run_git_command(["git", "init"], cwd)
    if result:
        speak("Git repository initialized successfully.")

        if(confirm_action("Do you wanna connect remote repo?")):
            speak("Please paste your url below..")
            url = input("Paste URL here: ")
            gitly_obj.entities["url"] = url
            execute_add_remote(gitly_obj)

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


def execute_command(gitly_obj: GitlySession):
    intent = gitly_obj.curr_intent
    
    if intent == "add":
        execute_add(gitly_obj)
    elif intent == "commit":
        execute_commit(gitly_obj)
    elif intent == "push":
        execute_push(gitly_obj)
    elif intent == "pull":
        execute_pull(gitly_obj)
    elif intent == "checkout":
        execute_checkout(gitly_obj)
    elif intent == "merge_branch":
        execute_merge(gitly_obj)
    elif intent == "init":
        execute_init(gitly_obj)
    elif intent == "remote":
        execute_add_remote(gitly_obj)
    elif intent == "current_branch":
        current_branch = get_current_branch(gitly_obj.curr_path)
        log_success(f"Current working branch is {current_branch}")
        speak(f"Current working branch is {current_branch}")
    else:
        speak(f"Intent '{intent}' not supported yet.")
