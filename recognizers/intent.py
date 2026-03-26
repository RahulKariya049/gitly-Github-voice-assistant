from rapidfuzz import process, fuzz
import re
# [Raw Voice Command]
#         ↓
# [Normalize Text]
#         ↓
# [Run Rewrite Patterns ONLY for that intent]
#         ↓
# [Flagged Structure with --branch etc.]
#         ↓
# [Detect Intent via Keywords/Synonyms]
#         ↓
# [Extract Entities via Regex or Parsing]
#         ↓
# [Validated Command or Follow-up Request]

# | Role                                          | What it is    | Variable Name     |
# | --------------------------------------------- | ------------- | ----------------- |
# | Branch you are on (receiving changes)         | Target branch |  `target_branch` |
# | Branch being merged in (contains new changes) | Source branch |  `source_branch` |

def normalize_text(text: str) -> str:
    text = text.lower().replace(",", "").strip()

    noise_words = [
        # Compound fillers
        "i guess", "i think", "i feel", "i believe", "you know", "sort of", "kind of", "can you", "right now", "okay so", "so yeah",

        # Speech fillers
        "uh", "umm", "um", "uhh", "hmm", "huh", "yo", "bro", "dude", "buddy",
        
        # Polite or generic
        "like", "please", "just", "actually", "basically", "technically", "literally", "obviously", "maybe", "well", "now", "do", "too", "also",

        # Command fluff
        "then", "so", "it", "okay", "ok", "alright", "you", "my", "recent",

        # Ambiguous/meaningless
        "everything", "all", "this", "that", "these", "those", "changes", "code", "updates", "stuff", "things", "file", "files"
    ]

    # Sort by length so multi-word ones match before small ones
    noise_words = sorted(noise_words, key=len, reverse=True)

    for noise in noise_words:
        text = re.sub(r"\b" + re.escape(noise) + r"\b", "", text)

    text = re.sub(r"[?\.!]+(?=\s|$)", "", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()



def translate_synonyms(text: str) -> str:
    """
    Replace fuzzy verbs/phrases with canonical Git verbs like push, commit, etc.
    """
    FUZZY_TRIGGERS = {
    "switch_repo": [
        "switch to repo", "switch repository", "load repo", "load project",
        "change repo", "go to project", "open workspace", "jump to repo","change repository"
    ],

    "push": [
        "push code", "push changes", "send code", "upload everything",
        "upload this", "ship it", "deliver changes", "sync my code",
        "push the branch", "move it upstream","ship"
    ],
    "pull": [
        "get latest", "pull changes", "fetch repo", "sync with remote",
        "get the branch","download latest", "sync everything", "fetch upstream", "download"
    ],
    "checkout": [
        "switch to", "go to branch", "move into", "change branch",
        "checkout branch", "jump to", "open branch",
        "switch branch", "switch over to", "change to", "move to"
    ],
    "commit": [
        "save work", "record progress", "log changes", "commit this","mark this",
        "commit all", "make a commit","commit changes","stage all files"
    ],
    "add": [
        "stage files", "track this", "include these files", "add changes",
        "add current file", "track current", "mark these", "stage this",
        "prepare this", "keep this", "add it", "track the file"
    ],
    "delete": [
        "remove it", "untrack that", "discard those", "delete file",
        "unstage this", "revert changes", "remove this", "drop the file",
        "cancel those", "delete that file", "unstage file", "ignore it"
    ],
    "init": [
        "start project", "initialize repository", "create repository","start a new repo","create repo", "make a new repo","make new project"
    ],
    "remote": [
        "connect remote", "link to repo", "set remote url","add remote origin",
        "add remote","add origin","connect to github", "add repo link"
    ],
    "status": [
        "what changed", "check status", "see changes", "git status",
        "show changes", "diff check"
    ]
    }

    text = text.lower().strip()

    for canonical, triggers in FUZZY_TRIGGERS.items():
        best_match = None
        best_score = 0


        for phrase in triggers:
            score = fuzz.partial_ratio(text, phrase)
            if score > best_score:
                best_match = phrase
                best_score = score

        # Replace only if it's a confident match
        if best_score >= 85:
            text = re.sub(rf"\b{re.escape(best_match)}\b", canonical, text)
            break

    return text



def detect_intent(text: str) -> str | None:
    """
    Detects primary intent verb from a cleaned command.
    Returns one of the known intent keywords or None.
    """
    INTENT_KEYWORDS = [
        "init", "commit", "push", "pull", "checkout", "status",
        "add", "delete", "remote","merge","current_branch","switch_repo"
    ]
    pattern = r"\b(" + "|".join(re.escape(intent) for intent in INTENT_KEYWORDS) + r")\b"
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return match.group(1) if match else None



def rewrite_phrases(text: str) -> str:
    """
    Rewrites common fuzzy patterns into canonical imperative commands.
    """
    REWRITE_PATTERNS = {

    "switch_repo": [
    # Confident multi-word commands
    (r"switch_repo (?P<repo>\w[\w\-\/]*)", r"switch_repo --repo \g<repo>")
    ],

    # === STATUS Variations ===
    "status": [
    (r"(?:check|show|get|see|print|display) status", r"status"),
    (r"what(?:'s| is) (?:changed|the status)", r"status"),
    (r"(?:view|show) (?:current )(?:state|changes|status)", r"status"),
    (r"(?:status)", r"status")
    ],

    # ===  ADD Variations ===
    "add": [
    (r"(?:add|stage|track)\s+(?:file|files|these)(?P<files>[\w\.\-\/\s]+)", r"add --files \g<files>"),
    (r"(?:add|stage|track)\s+(?P<files>[\w\.\-\/\s]+)", r"add --files \g<files>"),
    (r"(?:add|stage|track) all(?: files)?", r"add --files '.'"),
    (r"(?:track|stage) (?:these|those)? (?:changes|files)?", r"add --files ."),
    (r"(?:add|stage|track)(?: all)(?: the)? (?:files|changes)", r"add --files '.'"),
    (r"(?:add|stage) (?:this|current) file", r"add --files current"),
    ],

    # === COMMIT Variations ===
   "commit": [
    (r"(?:commit|save|record) all(?: files|changes)? with (?:message|msg) (?P<msg>.+)", r"commit --files '.' with --message \g<msg>"),
    (r"(?:commit|save|record) all(?: files)? with (?:message|msg) (?P<msg>.+)", r"commit --files . with --message \g<msg>"),
    (r"(?:commit|save|record) (?P<files>[\w\.\-\/\s]+) with (?:message|msg) (?P<msg>.+)", r"commit --files \g<files> with --message \g<msg>"),
    (r"(?:commit|save|record) message (?P<msg>.+)", r"commit --message \g<msg>"),
    (r"(?:message|msg) (?P<msg>.+) for (?P<files>[\w\.\-\/\s]+)", r"commit --files \g<files> with --message \g<msg>"),
    (r"(?:commit|save|record) with (?:message|msg) (?P<msg>.+)", r"commit with --message \g<msg>"),
    (r"(?:save|record) with (?:message|msg) (?P<msg>.+)", r"commit with --message \g<msg>"),
    (r"(?:commit|save|record) with (?:message|msg) (?P<msg>.+)", r"commit --files . with --message \g<msg>"),
    (r"(?:commit|save|record) message (?P<msg>.+)", r"commit --files . with --message \g<msg>"),

    (r"(?:commit|save|record) (?P<files>[\w\.\-\/\s]+)", r"commit --files \g<files>"),
    (r"(?:commit|save|record)", r"commit")
    ],


    # === PUSH Variations ===
    "push": [
    (r"(?:push|upload|send|sync) branch (?P<branch>[\w\-\/]+) to remote (?P<remote>\w+)", r"push --branch \g<branch> to --remote \g<remote>"),
    (r"(?:push|upload|send|sync) (?P<branch>[\w\-\/]+) to remote (?P<remote>\w+)", r"push --branch \g<branch> to --remote \g<remote>"),
    (r"(?:push|upload|send|sync) branch (?P<branch>[\w\-\/]+) to (?P<remote>\w+)", r"push --branch \g<branch> to --remote \g<remote>"),
    (r"(?:push|upload|send|sync) branch (?P<branch>[\w\-\/]+)", r"push --branch \g<branch>"),
    (r"(?:push|upload|send|sync) to remote (?P<remote>\w+)", r"push to --remote \g<remote>"),
    (r"(?:push|upload|send|sync) (?P<branch>[\w\-\/]+)", r"push --branch \g<branch>"),
    (r"(?:push|upload|send|sync) to (?P<remote>\w+)", r"push to --remote \g<remote>"),
    (r"(?:push|upload|send|sync) (?P<branch>[\w\-\/]+) to (?P<remote>\w+)", r"push --branch \g<branch> to --remote \g<remote>"),

    # === Fallback & general ===
    (r"(?:push|upload|ship|sync|send) (everything|all)", r"push"),
    (r"(?:push|upload|ship|sync|send)", r"push")
    ],

    # ===  PULL Variations ===    
    "pull": [
    (r"(?:pull|fetch|get|sync|download) (?P<branch>[\w\-\/]+) from remote (?P<remote>\w+)", r"pull --branch \g<branch> from --remote \g<remote>"),
    (r"(?:pull|fetch|get|sync|download) branch (?P<branch>[\w\-\/]+) from (?P<remote>\w+)", r"pull --branch \g<branch> from --remote \g<remote>"),
    (r"(?:pull|fetch|get|sync|download) (?P<branch>[\w\-\/]+) from (?P<remote>\w+)", r"pull --branch \g<branch> from --remote \g<remote>"),
    (r"(?:pull|fetch|get|sync|download) from remote (?P<remote>\w+)", r"pull from --remote \g<remote>"),
    (r"(?:pull|fetch|get|sync|download) from (?P<remote>\w+)", r"pull from --remote \g<remote>"),
    (r"(?:pull|fetch|get|sync|download) branch (?P<branch>[\w\-\/]+)", r"pull --branch \g<branch>"),
    (r"(?:pull|fetch|get|sync|download) (latest|changes|code)", r"pull"),
    (r"(?:pull|fetch|get|sync|download)", r"pull")
    ],


    # === CHECKOUT Variations ===
    "checkout": [
    # Most common natural ways
    (r"(?:checkout|switch|move|go|change)(?: to)?(?: branch)?(?: named)? (?P<branch>\w[\w\-\/]*)", r"checkout --branch \g<branch>"),
    (r"(?:switch|move) (?:into|onto) (?P<branch>\w[\w\-\/]*)", r"checkout --branch \g<branch>"),
    (r"(?:change|go) (?:to )?branch (?P<branch>\w[\w\-\/]*)", r"checkout --branch \g<branch>"),
    (r"jump to (?P<branch>\w[\w\-\/]*)", r"checkout --branch \g<branch>"),
    (r"use (?P<branch>\w[\w\-\/]*) branch", r"checkout --branch \g<branch>"),
    ],

    "current_branch": [
    (r"\bwhich branch\b.*\b(am I on|is active|is checked out|right now|currently)\b", r"current_branch"),
    (r"\bwhat branch\b.*\b(current|active|checked out)\b", r"current_branch"),
    (r"\bshow\b.*\bcurrent branch\b", r"current_branch"),
    (r"\b(am I|I am)\b.*\bon\b.*branch", r"current_branch"),
    (r"\bcurrent branch\b", r"current_branch"),
    (r"\bactive branch\b", r"current_branch"),
    (r"\bbranch\s+(am I on|right now|currently)\b", r"current_branch"),
    (r"\bwhat is my branch\b", r"current_branch")
    ],

    "merge": [
    # Merge X into Y
    (r"merge\s+(?:branch\s+)?(?P<source>\w[\w\-\/]*)\s+(into|to|and)\s+(?:branch\s+)?(?P<target>\w[\w\-\/]*)", r"merge --source \g<source> --target \g<target>"),
    (r"combine\s+(?:branch\s+)?(?P<source>\w[\w\-\/]*)\s+(into|to|and)\s+(?:branch\s+)?(?P<target>\w[\w\-\/]*)", r"merge --source \g<source> --target \g<target>"),
    (r"bring\s+(?:branch\s+)?(?P<source>\w[\w\-\/]*)\s+(into|to|and)\s+(?:branch\s+)?(?P<target>\w[\w\-\/]*)", r"merge --source \g<source> --target \g<target>"),
    
    # Merge X (target inferred later)
    (r"merge\s+(?:branch\s+)?(?P<source>\w[\w\-\/]*)", r"merge --source \g<source>"),
    (r"combine\s+(?:branch\s+)?(?P<source>\w[\w\-\/]*)", r"merge --source \g<source>"),
    (r"pull\s+(?:branch\s+)?(?P<source>\w[\w\-\/]*)", r"merge --source \g<source>")
    ],


    # === INIT Variations ===
    "init": [
    (r"(?:start|initialize|initiate|begin|create|make) (?:a )?(?:new )?(?:project|repository|repo)", r"init"),
    (r"(?:create|make|start) (?:a )?(?:git )?repo", r"init"),
    (r"(?:init|initialize) project", r"init"),
    (r"create repo(?: here)?", r"init"),
    (r"(?:init|initialize|start)", r"init")
    ],

    # === ADD REMOTE Variations ===
    "remote": [
    (r"(connect|link|add) (?:a )?(?:remote|github)?(?: repo)?(?: at)? (?P<url>https?://\S+)", r"add remote --url \g<url>"),
    (r"(connect|link|add) (?:a )?(?:remote|github)?(?: repo)?", r"add remote "),
    ],

    }
    
    for intent, patterns in REWRITE_PATTERNS.items():
        for i, (pattern, rewrite) in enumerate(patterns, start=1):
            if re.search(pattern, text, flags=re.IGNORECASE):
                text = re.sub(pattern, rewrite, text, flags=re.IGNORECASE)
                print(f"Matched Pattern number {i} in intent [{intent}] for FILTER 2")
                return text


    return text



def clean_entity(text: str) -> str:
    text = text.lower().replace(",", "").strip()

    ENTITY_JUNK = [
    "everything", "all", "stuff", "things", "changes", "code", "work", "update", "updates",
    "this", "that", "it", "those", "these", "current", "my", "latest",
    "file", "files", "repo", "repository", "branch",
    "on", "to", "from", "with", "in", "into", "onto", "as"
    ]


    # Sort by length so multi-word ones match before small ones
    ENTITY_JUNK = sorted(ENTITY_JUNK, key=len, reverse=True)

    for noise in ENTITY_JUNK:
        text = re.sub(r"\b" + re.escape(noise) + r"\b", "", text)
        

    text = re.sub(r"[?\.!]+(?=\s|$)", "", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def extract_entities(text: str) -> dict:
    entities = {
        "files": [],
        "message": None,
        "remote": None,
        "repo": None,
        "source_branch": None,
        "target_branch": None
    }

    # ==== FILES ====
    if "--files" in text:
        files_match = re.search(r"--files\s+(.+?)(?=\s+--|$)", text)
        if files_match:
            files = clean_entity(files_match.group(1).strip())
            entities["files"] = files.split()

    # ==== TARGET BRANCH ====
    if "--target" in text:
        tgt_match = re.search(r"--target\s+(?P<target>[\w\-_\/]+)", text)
        if tgt_match:
            target = clean_entity(tgt_match.group("target").strip())
            if target:
                entities["target_branch"] = target

    # ==== SOURCE BRANCH ====
    if "--source" in text:
        src_match = re.search(r"--source\s+(?P<source>[\w\-_\/]+)", text)
        if src_match:
            source = normalize_text(src_match.group("source").strip())
            if source:
                entities["source_branch"] = source

    # ==== REMOTE ====
    if "--remote" in text:
        remote_match = re.search(r"--remote\s+(?P<remote>\w+)", text)
        if remote_match:
            entities["remote"] = remote_match.group("remote").strip()
    else:
        remote_match = re.search(r"remote\s+(?P<remote>\w+)", text)
        if remote_match:
            entities["remote"] = remote_match.group("remote").strip()

    # ==== MESSAGE ====
    if "--message" in text:
        msg_match = re.search(r"--message\s+(?P<msg>.+?)(?=\s*(?:--|$))", text)
        if msg_match:
            entities["message"] = msg_match.group("msg").strip()

    # ==== REPO SWITCH ====
    if "--repo" in text:
        repo_match = re.search(r"--repo\s+(?P<repo>\w[\w\-\/]*)", text)
        if repo_match:
            entities["repo"] = repo_match.group("repo").strip()

    return entities



#PIPELINE CONTROLLER
def parse_command(command: str) -> dict:
    # step 1: NORMALIZE
    normalize = normalize_text(command)

    # step 2:DETECT PATTERNS
    translate_phrase = translate_synonyms(normalize)

    #step 3:REWRITE PHRASES 
    phrase_with_flags = rewrite_phrases(translate_phrase)

    #STEP 4:DETECT INTENT
    intent = detect_intent(phrase_with_flags)

    #STEP 5:EXTRACT ENTITIES
    dict_entity = extract_entities(phrase_with_flags)

    dict_entity["intent"] = intent

    return dict_entity


if __name__ == "__main__":
    test_commands = [
    # STATUS
    "what changed",
    "check status",
    "show me current changes",
    "diff check",

    # ADD
    "add current file",
    "track auth.py",
    "add all files",
    "stage files auth.py utils.py",
    "keep this file",

    # COMMIT
    "commit auth.py with message added login",
    "save work on auth.py with message add validation",
    "record auth.py",
    "commit all with message update done",
    "message fixed bug for utils.py",

    # PUSH
    "push branch main to origin",
    "upload everything to origin",
    "sync my code with origin",
    "send branch develop",
    "push the branch login",
    "ship it",
    "move it upstream",
    "upload",

    # PULL
    "pull latest from origin",
    "fetch login from github",
    "sync everything",
    "get branch feature/auth",
    "download latest",

    # MERGE
    "merge feature/auth into develop",
    "combine login into staging",
    "bring feature/login to develop",
    "merge develop",  # target inferred
    "merge auth to dev",
    "combine feature/search and main",

    # CHECKOUT
    "switch to develop",
    "go to branch feature/login",
    "move into bugfix branch",
    "checkout login",
    "jump to hotfix/auth",

    # CURRENT BRANCH
    "what branch am I on",
    "current branch",
    "which branch is active",
    "what is my branch",
    "am I on main",

    # SWITCH REPO
    "switch to repo gitly-v2",
    "load project gitly-pro",
    "go to repository old-vault",
    "switch repository gitlab-helper",
    "change repo demo-repo",
    "switch_repo gitbase",  # canonical fallback test

    # INIT
    "create a new repo",
    "start git project",
    "init repository",
    "kickstart new repo",

    # REMOTE
    "connect to origin",
    "add remote origin",
    "set origin remote to https://github.com/user/repo.git",
    "link a github repo at https://github.com/example/test.git"
    ]


    for idx, cmd in enumerate(test_commands, 1):
        print(f"\n[TEST {idx}] Raw Command: {cmd}")
        norm = normalize_text(cmd)
        trans = translate_synonyms(norm)
        rewritten = rewrite_phrases(trans)
        print(f"→ Normalized: {norm}")
        print(f"→ Synonym-Replaced: {trans}")
        print(f"→ Rewritten Canonical: {rewritten}")

        


