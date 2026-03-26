from core.session import GitlySession
from recognizers.intent import parse_command
from recognizers.path import parse_path_command
from recognizers.target_resolver import correct_targets_with_fuzzy,extract_number_from_speech,extract_clean_entity
from Speech.recognizer import recognize_speech
from Speech.text_to_speech import speak
from helpers.cache_maintainer import find_file_in_cache, generate_file_dict
from helpers.helpers import confirm_action,get_best_match
from helpers.cli_ui import log_error,log_step,log_success,log_warning,show_final_plan,live_waiting_feedback,animate,show_info
from executor.exexutor import execute_command
from rapidfuzz import process
import os

def handle_path_guidance_typed(text: str):
    result = parse_path_command(text)

    if result["is_crashed"] or not result.get("path_joined"):
        log_error("❌ Still couldn't resolve the typed path.")
        return None

    path = result["path_joined"]
    log_success(f"✅ Path resolved from typed input: [bold]{path}[/bold]")
    return path


def handle_path_guidance():
    animate("📁 [Gitly] Listening for repo path guidance...")

    user_input = recognize_speech()

    if not user_input:
        speak("Sorry i was not able to get that.....")
        
    result = parse_path_command(user_input)

    # if result["is_crashed"] or not result.get("path_joined"):
    #     log_error("❌ I couldn't resolve the path. Try rephrasing.")
    #     print("[BACKEND][Layer 2]: Path Parse Failed\n")
    #     return None

    path = result
    # is_soft = result.get("is_soft", False)
    # unmatched = result.get("unmatched_tokens", [])

    # # 🔸 If unmatched tokens exist, ask user to type manually
    # if unmatched:
    #     log_warning(f"⚠️ I couldn't understand these parts: {', '.join(unmatched)}")
    #     if confirm_action("🔁 Can you type path guidance manually?"):
    #         response = input("[USER]: ").strip()
    #         return handle_path_guidance_typed(response)
    #     else:
    #         show_info("🛑 Path guidance cancelled.")
    #         return None

    # # 🔸 If it's a soft match, ask user to confirm
    # if is_soft:
    #     if not confirm_action(f"🤔 Did you mean this path: {path}?"):
    #         if confirm_action("🔁 Can you type path guidance manually?"):
    #             response = input("[USER]: ").strip()
    #             return handle_path_guidance_typed(response)
    #         else:
    #             show_info("🛑 Path guidance cancelled.")
    #             return None

    # ✅ All good
    log_success(f"✅ Path resolved: [bold]{path}[/bold]")

    # # 🧠 Ask for optional caching name
    # if confirm_action("📛 Do you want to give this repo a name to remember it later?"):
    #     repo_name = input("🔤 Repo Name: ").strip()
    # else:
    #     repo_name = None

    return path


def validate_targets(raw_targets: list[str], gitly_obj: GitlySession) -> list[str]:
    """
    Resolves and disambiguates targets using cached file mappings.
    """
    repo_path = gitly_obj.curr_path

    # Ensure file cache exists
    if repo_path not in gitly_obj.recent_paths:
        gitly_obj.recent_paths[repo_path] = generate_file_dict(repo_path)

    inner_dict = gitly_obj.recent_paths[repo_path]
    return resolve_disambiguated_targets(raw_targets, inner_dict, repo_path)


def resolve_disambiguated_targets(raw_targets: list[str], inner_dict: dict[str, list[str]], repo_path: str) -> list[str]:
    """
    Converts raw filenames into relative paths based on matches in cache.
    Handles disambiguation for duplicate filenames across directories.
    """
    final_paths = []

    for target in raw_targets:
        possible_paths = inner_dict.get(target, [])

        # === Single match - auto-resolve
        if len(possible_paths) == 1:
            rel_path = os.path.relpath(possible_paths[0], repo_path)
            final_paths.append(rel_path)

        # === Multiple matches - ask user
        elif len(possible_paths) > 1:
            speak(f"[Gitly]: I found multiple matches for '{target}':")
            for i, path in enumerate(possible_paths):
                rel = os.path.relpath(path, repo_path)
                print(f"  {i+1}. {rel}")

            speak("Please say the number of the file you meant.")
            for attempt in range(2):  # Give two chances
                reply = recognize_speech()
                chosen_idx = extract_number_from_speech(reply)

                if chosen_idx and 1 <= chosen_idx <= len(possible_paths):
                    rel = os.path.relpath(possible_paths[chosen_idx - 1], repo_path)
                    show_info(f"📂 Selected file: {rel}")
                    final_paths.append(rel)
                    break
                elif attempt == 0:
                    speak("Hmm, I didn't get that. Please try once more.")
                else:
                    log_warning(f"⚠️ Skipping '{target}' due to invalid response.")

        else:
            log_warning(f"⚠️ No matches found for '{target}'")

    if final_paths:
        log_success(f"📦 Final resolved paths: {final_paths}")
    else:
        log_error("❌ No valid file targets resolved.")

    return final_paths


def resolve_repo_from_user(matches: list[tuple]) -> tuple | None:
    """
    Prompts user to choose the correct repository using fuzzy voice input.
    Returns the selected (repo_path, file_path) tuple from matches, or None if unclear.
    """
    log_step("Resolving Repo from user...")
    repo_names = [os.path.basename(os.path.normpath(repo_path)) for repo_path, _ in matches]

    speak("[Gitly]: Multiple repositories found with similar files.")
    speak("[Gitly]: Which repository do you mean?")
    def ask_and_match():
        for i, name in enumerate(repo_names, 1):
            print(f"{i}. {name}")

        reply = recognize_speech()
        match = process.extractOne(reply, repo_names)
        if match and match[1] >= 80:
            index = repo_names.index(match[0])
            log_success(f"[Gitly]: Got it! Git Repo named: '{repo_names[index]}'.")
            return matches[index]
        return None

    # First attempt
    chosen = ask_and_match()
    if chosen:
        return chosen

    # Fallback second attempt
    speak("[Gitly]: Didn't catch that clearly. Could you repeat the repo name once more?")
    chosen = ask_and_match()
    if chosen:
        return chosen

    speak("[Gitly]: Still unclear. Cancelling this request.")
    return None


def finalize_targets(gitly_obj: GitlySession):
    raw_targets = gitly_obj.entities.get("files")
    
    clean = correct_targets_with_fuzzy(gitly_obj, raw_targets)
    
    gitly_obj.entities["files"] = validate_targets(clean, gitly_obj)
    return 


def guide_and_set_path(gitly_obj: GitlySession) -> bool:
    """
    Handles user guidance to a repo path, sets path if successful.
    Returns True if path is set, False if cancelled or failed.
    """
    path = handle_path_guidance()
    if path:
        gitly_obj.curr_path = path
        gitly_obj.update_cache()
        show_info(f"[Gitly]: Repo path set to: {path}")
        return True
    
    return False


def handle_matches_from_cache(matches: list[tuple[str,list[str]]], gitly_obj : GitlySession):
    first_target = gitly_obj.entities.get("files")[0]
    if len(matches) > 1:
        result = resolve_repo_from_user(matches)
        if result:
            repo_path, file_path = result
            gitly_obj.curr_path = repo_path
            return
                
        else:
            print("[DEBUG]: REPO RESOLVER FAILED..")
            return

    elif len(matches) == 0:
        log_warning(f"[Gitly]: I couldn't find '{first_target}' in cached repos.")
        speak(f"[Gitly]: Would you like to guide me to the repo for your files?")
        guide_and_set_path(gitly_obj)

        return
    
    else:
        repo_path, file_path = matches[0]
        repo_name = os.path.basename(os.path.normpath(repo_path))
        if confirm_action(f"[Gitly]: I found your files in the repository: '{repo_name}'. Should I proceed?"):
            gitly_obj.curr_path = repo_path
            return
        else:
            guide_and_set_path(gitly_obj)


def resolve_path(gitly_obj: GitlySession):
    """
    Resolves the repo path using cache or path guidance.
    Now includes [+] Add New Repo option in cached list.
    """

    if gitly_obj.curr_path:
        return

    animate("🗂️ Checking cached repositories...")

    recent = list(gitly_obj.recent_paths.keys())

    if recent:
        repo_names = [os.path.basename(os.path.normpath(p)) for p in recent]
        repo_names.append("Add new repository")

        show_info("I found these recent repositories:")
        for i, name in enumerate(repo_names, 1):
            print(f"{i}. {name}")

        speak(f"Which repository do you want to use? You can also say 'add new'.")
        reply = recognize_speech()

        # Match user input to option
        match, is_soft = get_best_match(reply, repo_names)

        if match == "Add new repository":
            guide_and_set_path(gitly_obj)
            return

        # Regular match from cache
        if match:
            # Get the first match, or None if no match
            matching_paths = [p for p in recent if os.path.basename(p) == match]
            resolved_path = matching_paths[0] if matching_paths else None

            if resolved_path:
                if is_soft:
                    if not confirm_action(f"Did you mean {match}?"):
                        log_warning("Okay. Cancelling.")
                        return
                gitly_obj.curr_path = resolved_path
                gitly_obj.update_cache()
                show_info(f"Repo selected: {match}")
                return

    # No cache or user rejected all options —> ask for manual path
    speak("Please guide me to your Git repository.")
    guide_and_set_path(gitly_obj)
    return


def handle_branch_logic(intent: str, gitly_obj: GitlySession):
    if not gitly_obj.curr_path:
        resolve_path(gitly_obj)
        if not gitly_obj.curr_path:
            show_info("🛑 No repository selected.")
            return

    if intent == "checkout":
        if not gitly_obj.entities.get("target_branch"):
            speak("Which branch do you want to switch to?")
            reply = recognize_speech()  # already retried inside
            branch = extract_clean_entity(reply, "branch", gitly_obj)
            if not branch:
                speak("Couldn't understand the branch. Please try again later.")
                return
            gitly_obj.entities["target_branch"] = branch

    elif intent == "merge_branch":
        if not gitly_obj.entities.get("source_branch"):
            speak("Which branch should I merge into the current one?")
            reply = recognize_speech()
            source_branch = extract_clean_entity(reply, "branch", gitly_obj)
            if not source_branch:
                speak("Sorry, I couldn't catch the branch to merge.")
                return
            gitly_obj.entities["source_branch"] = source_branch


    show_final_plan(
        intent=gitly_obj.entities.get("intent"),
        branch=gitly_obj.entities.get("target_branch") or gitly_obj.entities.get("source_branch"),
        repo=gitly_obj.curr_path
    )
    execute_command(gitly_obj)


def handle_commit_flow(gitly_obj: GitlySession):
    intent = gitly_obj.curr_intent
    targets = gitly_obj.entities.get("files")
    path_set = bool(gitly_obj.curr_path)
    cache_set = bool(gitly_obj.recent_paths)

    # === Case 1: No targets at all ===
    if not targets:
        resolve_path(gitly_obj)  # sets curr_path using cache or guidance
        path_set = True
        speak(f"Which file(s) do you want to {intent}?")
        response = recognize_speech()
        targets = extract_clean_entity(response, "files", gitly_obj)
        if not targets:
            log_error("No files were identified. Canceling operation.")
            return
        gitly_obj.entities["files"] = targets

    # === Case 2: Targets exist but path unknown ===
    if targets and not path_set:
        # See which cached repo has those file(s)
        log_step("Finding file in cache.....")
        first_target = targets[0]
        matches = find_file_in_cache(first_target, gitly_obj.recent_paths)
        handle_matches_from_cache(matches, gitly_obj)  # sets curr_path

    # === Final Step: We have both
    log_step("Validating Files.....")
    finalize_targets(gitly_obj)

    print()
    show_final_plan(
    intent=gitly_obj.curr_intent,
    files=gitly_obj.entities.get("files"),
    msg=gitly_obj.entities.get("message"),
    repo=gitly_obj.curr_path
    )
    print()
    
    execute_command(gitly_obj)


def handle_init_intent(gitly_obj : GitlySession):
    speak("Which repository do you want to initialize?")
    
    resolve_path(gitly_obj)

    show_final_plan(
        intent=gitly_obj.entities["intent"],
        repo=gitly_obj.curr_path
    )

    execute_command(gitly_obj)
    return


def process_command(cmd, gitly_obj : GitlySession):
    # === ENTRY VISUAL: User Input ===
    log_step("🎤 [Gitly] Received your command.")
    animate("🧠 [Gitly] Interpreting your command...")

    # === LAYER 1: INTENT PARSER ===
    dict_ = parse_command(cmd)
    intent = dict_.get("intent")
    targets = dict_.get("files")
    gitly_obj.entities = dict_
    gitly_obj.curr_intent = intent

    # Show what Gitly understood
    log_success(f"📘 Intent Detected: [bold magenta]{intent}[/bold magenta]" if intent else "⚠️ Could not detect intent.")
    if targets:
        log_success(f"📦 Files Mentioned: {targets}")

    # === INTENT VALIDATION ===
    if not intent:
        log_warning("I couldn't understand the intent. Asking user to clarify...")
        speak("I couldn't understand what you want me to do.")
        speak("Can you please rephrase or clarify your command?")
        
        response = recognize_speech()
        dict_ = parse_command(response)
        intent = dict_.get("intent")
        gitly_obj.entities = dict_
        gitly_obj.curr_intent = intent
        targets = dict_.get("files")

        if not intent:
            log_error("Intent still not clear. Aborting.")
            return
        else:
            log_success(f"🧠 Updated Intent Detected: {intent}")


    # === ADD / COMMIT (FILE-LEVEL ACTIONS) ===
    if intent in ("commit", "add"):
        handle_commit_flow(gitly_obj)
        return

    # === PUSH / PULL / STATUS ===
    elif intent in ("push", "pull", "status"):
        resolve_path(gitly_obj)
        show_final_plan(
        intent=gitly_obj.curr_intent,
        repo=gitly_obj.curr_path
        )
        execute_command(gitly_obj)
        return

    # === MERGE / CHECKOUT / CURRENT BRANCH ===
    elif intent in ("merge_branch", "current_branch", "checkout"):
        handle_branch_logic(intent, gitly_obj)
        return

    # === SWITCH REPO ===
    elif intent == "switch_repo":
        if not gitly_obj.recent_paths:
            speak("You haven't added any recent repositories yet.")
            return

        repo = dict_.get("repo")  # <- check if already captured

        if repo:
            path = gitly_obj.recent_paths.get(repo)
            if path:
                gitly_obj.curr_path = path
                speak(f"Switched to {repo} repository.")
                print(f"✅ Now working in: {repo} ({path})")
            else:
                speak(f"No path found for {repo}. Please add it.")
            return  # we're done!

        # Otherwise, ask interactively
        repo_paths = list(gitly_obj.recent_paths.keys())
        repo_names = [os.path.basename(os.path.normpath(p)) for p in repo_paths]
        speak("You have the following recent repositories:")
        for idx, name in enumerate(repo_names, start=1):
            show_info(f"[{idx}] {name}")

        speak("Which repository did you meant??")
        response = recognize_speech()

        # Try entity extraction
        match, is_confident = get_best_match(response, repo_names)
        if match:
            if is_confident:
                repo = match
            else:
                if confirm_action(f"Did you mean this {match} repo?"):
                    repo = match

        else:
            speak("Sorry i could not get that repository name..")
            return
        
        if repo:
            gitly_obj.flush_state()
            gitly_obj.curr_path = str([p for p in repo_paths if os.path.basename(os.path.normpath(p)) == repo])
        else:
            speak("Sorry i could not get that repository name..")
            return


    # === INIT NEW REPO ===
    elif intent == "init":
        handle_init_intent(gitly_obj)
        return

    # === ADD REMOTE ===
    elif intent == "remote":
        url = dict_.get("url", "")
        log_warning("Asking User for URL...")
        if not url:
            response = input("Can you paste your remote URL?")
            url = response.strip()

        if url:
            if url.startswith("http") or url.startswith("git@"):
                gitly_obj.entities["url"] = url
                execute_command(gitly_obj)
            else:
                speak("That doesn't look like a valid remote URL.")
        else:
            speak("Sorry, I think there is some problem in copy pasting url.")
        return

        
    else:
        speak("❌ Sorry, I don't support that intent yet.")
