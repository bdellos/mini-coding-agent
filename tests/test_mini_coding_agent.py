import json
import pytest
from unittest.mock import patch

from mini_coding_agent import (
    FakeModelClient,
    MiniAgent,
    OllamaModelClient,
    SessionStore,
    SkillLogger,
    SkillRegistry,
    WorkspaceContext,
    build_welcome,
    normalize_word,
    tokenize,
)


def build_workspace(tmp_path):
    (tmp_path / "README.md").write_text("demo\n", encoding="utf-8")
    return WorkspaceContext.build(tmp_path)


def build_agent(tmp_path, outputs, **kwargs):
    workspace = build_workspace(tmp_path)
    store = SessionStore(tmp_path / ".mini-coding-agent" / "sessions")
    approval_policy = kwargs.pop("approval_policy", "auto")
    return MiniAgent(
        model_client=FakeModelClient(outputs),
        workspace=workspace,
        session_store=store,
        approval_policy=approval_policy,
        **kwargs,
    )


def test_agent_runs_tool_then_final(tmp_path):
    (tmp_path / "hello.txt").write_text("alpha\nbeta\n", encoding="utf-8")
    agent = build_agent(
        tmp_path,
        [
            '<tool>{"name":"read_file","args":{"path":"hello.txt","start":1,"end":2}}</tool>',
            "<final>Read the file successfully.</final>",
        ],
    )

    answer = agent.ask("Inspect hello.txt")

    assert answer == "Read the file successfully."
    assert any(item["role"] == "tool" and item["name"] == "read_file" for item in agent.session["history"])
    assert "hello.txt" in agent.session["memory"]["files"]


def test_agent_retries_after_empty_model_output(tmp_path):
    agent = build_agent(
        tmp_path,
        [
            "",
            "<final>Recovered after retry.</final>",
        ],
    )

    answer = agent.ask("Do the task")

    assert answer == "Recovered after retry."
    notices = [item["content"] for item in agent.session["history"] if item["role"] == "assistant"]
    assert any("empty response" in item for item in notices)


def test_agent_retries_after_malformed_tool_payload(tmp_path):
    (tmp_path / "hello.txt").write_text("alpha\n", encoding="utf-8")
    agent = build_agent(
        tmp_path,
        [
            '<tool>{"name":"read_file","args":"bad"}</tool>',
            '<tool>{"name":"read_file","args":{"path":"hello.txt","start":1,"end":1}}</tool>',
            "<final>Recovered after malformed tool output.</final>",
        ],
    )

    answer = agent.ask("Inspect hello.txt")

    assert answer == "Recovered after malformed tool output."
    assert any(item["role"] == "tool" and item["name"] == "read_file" for item in agent.session["history"])
    notices = [item["content"] for item in agent.session["history"] if item["role"] == "assistant"]
    assert any("valid <tool> call" in item for item in notices)


def test_agent_accepts_xml_write_file_tool(tmp_path):
    agent = build_agent(
        tmp_path,
        [
            '<tool name="write_file" path="hello.py"><content>print("hi")\n</content></tool>',
            "<final>Done.</final>",
        ],
    )

    answer = agent.ask("Create hello.py")

    assert answer == "Done."
    assert (tmp_path / "hello.py").read_text(encoding="utf-8") == 'print("hi")\n'


def test_retries_do_not_consume_the_whole_budget(tmp_path):
    agent = build_agent(
        tmp_path,
        [
            "",
            "",
            "<final>Recovered after several retries.</final>",
        ],
        max_steps=1,
    )

    answer = agent.ask("Do the task")

    assert answer == "Recovered after several retries."


def test_agent_saves_and_resumes_session(tmp_path):
    agent = build_agent(tmp_path, ["<final>First pass.</final>"])
    assert agent.ask("Start a session") == "First pass."

    resumed = MiniAgent.from_session(
        model_client=FakeModelClient(["<final>Resumed.</final>"]),
        workspace=agent.workspace,
        session_store=agent.session_store,
        session_id=agent.session["id"],
        approval_policy="auto",
    )

    assert resumed.session["history"][0]["content"] == "Start a session"
    assert resumed.ask("Continue") == "Resumed."


def test_delegate_uses_child_agent(tmp_path):
    agent = build_agent(
        tmp_path,
        [
            '<tool>{"name":"delegate","args":{"task":"inspect README","max_steps":2}}</tool>',
            "<final>Child result.</final>",
            "<final>Parent incorporated the child result.</final>",
        ],
    )

    answer = agent.ask("Use delegation")

    assert answer == "Parent incorporated the child result."
    tool_events = [item for item in agent.session["history"] if item["role"] == "tool"]
    assert tool_events[0]["name"] == "delegate"
    assert "delegate_result" in tool_events[0]["content"]


def test_patch_file_replaces_exact_match(tmp_path):
    file_path = tmp_path / "sample.txt"
    file_path.write_text("hello world\n", encoding="utf-8")
    agent = build_agent(tmp_path, [])

    result = agent.run_tool(
        "patch_file",
        {
            "path": "sample.txt",
            "old_text": "world",
            "new_text": "agent",
        },
    )

    assert result == "patched sample.txt"
    assert file_path.read_text(encoding="utf-8") == "hello agent\n"


def test_invalid_risky_tool_does_not_prompt_for_approval(tmp_path):
    agent = build_agent(tmp_path, [], approval_policy="ask")

    with patch("builtins.input") as mock_input:
        result = agent.run_tool("write_file", {})

    assert result.startswith("error: invalid arguments for write_file: 'path'")
    assert 'example: <tool name="write_file"' in result
    mock_input.assert_not_called()


def test_list_files_hides_internal_agent_state(tmp_path):
    agent = build_agent(tmp_path, [])
    (tmp_path / ".mini-coding-agent").mkdir(exist_ok=True)
    (tmp_path / ".git").mkdir(exist_ok=True)
    (tmp_path / "hello.txt").write_text("hi\n", encoding="utf-8")

    result = agent.run_tool("list_files", {})

    assert ".mini-coding-agent" not in result
    assert ".git" not in result
    assert "[F] hello.txt" in result


def test_path_rejects_parent_escape(tmp_path):
    agent = build_agent(tmp_path, [])

    with pytest.raises(ValueError, match="path escapes workspace"):
        agent.path("../outside.txt")


def test_path_rejects_symlink_escape(tmp_path):
    agent = build_agent(tmp_path, [])
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    link = tmp_path / "outside-link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is not available in this environment")

    with pytest.raises(ValueError, match="path escapes workspace"):
        agent.path("outside-link/secret.txt")


def test_path_accepts_case_variant_on_case_insensitive_filesystems(tmp_path):
    project_root = tmp_path / "Proj"
    project_root.mkdir()
    agent = build_agent(project_root, [])
    variant = project_root.parent / project_root.name.lower() / "README.md"

    if not variant.exists():
        pytest.skip("case-sensitive filesystem")

    resolved = agent.path(str(variant))

    assert resolved.samefile(project_root / "README.md")


def test_repeated_identical_tool_call_is_rejected(tmp_path):
    agent = build_agent(tmp_path, [])
    agent.record({"role": "tool", "name": "list_files", "args": {}, "content": "(empty)", "created_at": "1"})
    agent.record({"role": "tool", "name": "list_files", "args": {}, "content": "(empty)", "created_at": "2"})

    result = agent.run_tool("list_files", {})

    assert result == "error: repeated identical tool call for list_files; choose a different tool or return a final answer"


def test_welcome_screen_keeps_box_shape_for_long_paths(tmp_path):
    deep = tmp_path / "very" / "long" / "path" / "for" / "the" / "mini" / "agent" / "welcome" / "screen"
    deep.mkdir(parents=True)
    agent = build_agent(deep, [])

    welcome = build_welcome(agent, model="qwen3.5:4b", host="http://127.0.0.1:11434")
    lines = welcome.splitlines()

    assert len(lines) >= 5
    assert len({len(line) for line in lines}) == 1
    assert "..." in welcome
    assert "O   O" in welcome
    assert "MINI-CODING-AGENT" not in welcome
    assert "MINI CODING AGENT" in welcome
    assert "// READY" not in welcome
    assert "SLASH" not in welcome
    assert "READY      " not in welcome
    assert "commands: Commands:" not in welcome


def test_prompt_top_level_sections_stay_flush_left_with_multiline_content(tmp_path):
    workspace = WorkspaceContext(
        cwd=str(tmp_path),
        repo_root=str(tmp_path),
        branch="fix/prompt-indentation",
        default_branch="main",
        status=" M mini_coding_agent.py\n?? tests/test_prompt.py",
        recent_commits=["abc123 first commit", "def456 second commit"],
        project_docs={"README.md": "line1\nline2"},
    )
    store = SessionStore(tmp_path / ".mini-coding-agent" / "sessions")
    agent = MiniAgent(
        model_client=FakeModelClient([]),
        workspace=workspace,
        session_store=store,
        approval_policy="auto",
    )
    agent.session["memory"] = {
        "task": "verify prompt formatting",
        "files": ["mini_coding_agent.py"],
        "notes": ["saw inconsistent indentation", "need regression coverage"],
    }
    agent.record({"role": "user", "content": "inspect prompt()", "created_at": "1"})
    agent.record(
        {
            "role": "tool",
            "name": "read_file",
            "args": {"path": "mini_coding_agent.py"},
            "content": "    def prompt(self, user_message):\n        ...",
            "created_at": "2",
        }
    )

    prompt = agent.prompt("is this issue legit?")
    lines = prompt.splitlines()

    for label in ["Rules:", "Tools:", "Valid response examples:", "Workspace:", "Memory:", "Transcript:", "Current user request:"]:
        assert label in lines
        assert f"            {label}" not in prompt


def _make_filler(i):
    return {"role": "tool", "name": "list_files", "args": {}, "content": "", "created_at": str(i)}


def test_history_text_deduplicates_reads_but_not_after_write(tmp_path):
    """read_file deduplication must not skip a read that follows a write.

    Realistic prior-turn history (non-recent window):
        user: "update config"
        assistant: <tool>read_file config</tool>
        tool:   config v1 (content: setting=true)
        assistant: <tool>write_file config</tool>
        tool:   wrote
        assistant: <tool>read_file config</tool>
        tool:   config v2 (content: setting=false)   <- MUST NOT be skipped

    Without fix: seen_reads={"config"} after first read; write does NOT clear it;
                 second read is wrongly skipped (LLM sees stale content).
    With fix: write clears seen_reads, second read is correctly shown.
    """
    agent = build_agent(tmp_path, [])

    # Simulate a prior turn with read->write->read on the same file
    # history_length=13, recent_start=7 (indices 0-6 non-recent, 7-12 recent)
    agent.record({"role": "user", "content": "update config", "created_at": "0"})        # index 0
    agent.record({"role": "assistant", "content": '<tool>{"name":"read_file","args":{"path":"config.txt"}}</tool>', "created_at": "1"})
    agent.record({"role": "tool", "name": "read_file", "args": {"path": "config.txt"}, "content": "# config.txt\n   1: setting=true\n", "created_at": "2"})  # index 2, non-recent, ADDED
    agent.record({"role": "assistant", "content": '<tool>{"name":"write_file","args":{"path":"config.txt","content":"setting=false\n"}}</tool>', "created_at": "3"})
    agent.record({"role": "tool", "name": "write_file", "args": {"path": "config.txt", "content": "setting=false\n"}, "content": "wrote config.txt", "created_at": "4"})  # index 4, non-recent
    agent.record({"role": "assistant", "content": '<tool>{"name":"read_file","args":{"path":"config.txt"}}</tool>', "created_at": "5"})
    agent.record({"role": "tool", "name": "read_file", "args": {"path": "config.txt"}, "content": "# config.txt\n   1: setting=false\n", "created_at": "6"})  # index 6, non-recent, ADDED (write cleared dedup)
    # recent entries
    for i in range(7, 13):
        agent.record(_make_filler(i))

    history = agent.history_text()

    # Both read contents appear exactly once (check full line to avoid JSON false positives)
    assert "# config.txt\n   1: setting=true\n" in history
    assert "# config.txt\n   1: setting=false\n" in history
    # Also verify duplicate read (setting=true, same path) does NOT appear twice
    assert history.count("setting=true") == 1


def test_history_text_deduplicates_unchanged_repeated_reads(tmp_path):
    """read_file deduplication should still skip repeated reads with no write in between."""
    agent = build_agent(tmp_path, [])

    # Realistic: two identical reads with no write between them
    # history_length=10, recent_start=4 (indices 0-3 non-recent, 4-9 recent)
    agent.record({"role": "user", "content": "check logs", "created_at": "0"})  # index 0
    agent.record({"role": "assistant", "content": '<tool>{"name":"read_file","args":{"path":"log.txt"}}</tool>', "created_at": "1"})
    agent.record({"role": "tool", "name": "read_file", "args": {"path": "log.txt"}, "content": "# log.txt\n   1: stable\n", "created_at": "2"})  # index 2, non-recent, ADDED
    agent.record({"role": "assistant", "content": '<tool>{"name":"read_file","args":{"path":"log.txt"}}</tool>', "created_at": "3"})  # index 3, non-recent, SKIPPED (dup)
    for i in range(4, 10):
        agent.record(_make_filler(i))  # indices 4-9, recent

    history = agent.history_text()

    # Only first read should appear; duplicates must be skipped
    assert history.count("stable") == 1


def test_ollama_client_posts_expected_payload():
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps({"response": "<final>ok</final>"}).encode("utf-8")

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    client = OllamaModelClient(
        model="qwen3.5:4b",
        host="http://127.0.0.1:11434",
        temperature=0.2,
        top_p=0.9,
        timeout=30,
    )

    with patch("urllib.request.urlopen", fake_urlopen):
        result = client.complete("hello", 42)

    assert result == "<final>ok</final>"
    assert captured["url"] == "http://127.0.0.1:11434/api/generate"
    assert captured["timeout"] == 30
    assert captured["body"]["model"] == "qwen3.5:4b"
    assert captured["body"]["prompt"] == "hello"
    assert captured["body"]["stream"] is False
    assert captured["body"]["raw"] is False
    assert captured["body"]["think"] is False
    assert captured["body"]["options"]["num_predict"] == 42


# ---------------------------------------------------------------------------
# 7) Agent Skills: discovery (plan.md Step 2, tests.md T1-T3)
# ---------------------------------------------------------------------------
def write_skill(base, folder, name="demo", description="A demo skill.", body="1. Do the thing."):
    skill_dir = base / folder
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n{body}\n",
        encoding="utf-8",
    )
    return skill_dir / "SKILL.md"


def test_discover_finds_skills_in_both_folders(tmp_path):
    write_skill(tmp_path / "skills", "pr-review", name="pr-review", description="Review a pull request.")
    write_skill(tmp_path / ".claude" / "skills", "validate-environment", name="validate-environment", description="Validate the grid.")

    registry = SkillRegistry.discover(tmp_path)

    assert sorted(registry.names()) == ["pr-review", "validate-environment"]
    assert registry.get("validate-environment").description == "Validate the grid."


def test_discover_skips_invalid_skill_files(tmp_path):
    skills = tmp_path / "skills"
    write_skill(skills, "good", name="good")
    (skills / "no-skill-file").mkdir()
    (skills / "no-frontmatter").mkdir()
    (skills / "no-frontmatter" / "SKILL.md").write_text("Just instructions.\n", encoding="utf-8")
    (skills / "no-description").mkdir()
    (skills / "no-description" / "SKILL.md").write_text("---\nname: no-description\n---\nBody\n", encoding="utf-8")
    (skills / "unclosed").mkdir()
    (skills / "unclosed" / "SKILL.md").write_text("---\nname: unclosed\ndescription: Never closed.\n", encoding="utf-8")

    registry = SkillRegistry.discover(tmp_path)

    assert registry.names() == ["good"]


def test_skills_folder_wins_on_duplicate_name(tmp_path):
    write_skill(tmp_path / "skills", "dup", name="dup", description="From skills folder.")
    write_skill(tmp_path / ".claude" / "skills", "dup", name="dup", description="From .claude folder.")

    registry = SkillRegistry.discover(tmp_path)

    assert len(registry) == 1
    assert registry.get("dup").description == "From skills folder."


def test_discover_with_no_skill_folders_is_empty(tmp_path):
    registry = SkillRegistry.discover(tmp_path)

    assert len(registry) == 0
    assert registry.get("anything") is None


def test_skill_instructions_are_loaded_on_demand(tmp_path):
    path = write_skill(tmp_path / "skills", "demo", body="1. Read src/environment.py\n2. Report boundaries")
    registry = SkillRegistry.discover(tmp_path)
    skill = registry.get("demo")

    # The registry only holds name/description; instructions come from disk when asked.
    assert not hasattr(skill, "body")
    assert skill.instructions() == "1. Read src/environment.py\n2. Report boundaries"

    path.write_text("---\nname: demo\ndescription: A demo skill.\n---\nUpdated steps\n", encoding="utf-8")
    assert skill.instructions() == "Updated steps"


# ---------------------------------------------------------------------------
# 7) Agent Skills: similarity check (plan.md Step 3, tests.md T5-T7)
# ---------------------------------------------------------------------------
# Descriptions copied from the Lab 5 skills so matching is tested on real data.
LAB5_VALIDATE = "This skill validates the environment for things like boundaries and terminal states."
LAB5_ANALYZE = (
    "Check the sequence of states, actions, and rewards. Identify any loops, dead ends, "
    "or other issues in the episode. Return a summary of the episode analysis."
)


def build_lab5_registry(tmp_path):
    skills = tmp_path / ".claude" / "skills"
    write_skill(skills, "validate-environment", name="validate-environment", description=LAB5_VALIDATE)
    write_skill(skills, "analyze-episode", name="analyze-episode", description=LAB5_ANALYZE)
    return SkillRegistry.discover(tmp_path)


def test_word_endings_are_treated_as_the_same_word():
    variants = {normalize_word(word) for word in ["validate", "validates", "validated", "validating"]}
    assert len(variants) == 1
    assert normalize_word("boundaries") == normalize_word("boundary")
    assert normalize_word("states") == normalize_word("state")


def test_tokenize_splits_hyphens_and_drops_common_words():
    words = tokenize("The validate-environment skill checks the grid's boundaries")
    assert normalize_word("validate") in words
    assert normalize_word("environment") in words
    assert normalize_word("grid") in words
    assert "the" not in words
    assert "skill" not in words
    assert "s" not in words  # leftover from "grid's"


def test_grid_validation_prompt_picks_validate_environment(tmp_path):
    registry = build_lab5_registry(tmp_path)

    result = registry.match("Validate the grid environment boundaries")

    assert result["chosen"] == "validate-environment"
    assert result["scores"]["validate-environment"] >= result["threshold"]
    assert result["scores"]["validate-environment"] > result["scores"]["analyze-episode"]


def test_episode_prompt_picks_analyze_episode(tmp_path):
    registry = build_lab5_registry(tmp_path)

    result = registry.match("Analyze this episode for loops and dead ends")

    assert result["chosen"] == "analyze-episode"


def test_unrelated_prompt_picks_no_skill(tmp_path):
    registry = build_lab5_registry(tmp_path)

    result = registry.match("Write a hello world script")

    assert result["chosen"] is None
    assert all(score < result["threshold"] for score in result["scores"].values())


def test_match_reports_every_skill_score_and_threshold(tmp_path):
    registry = build_lab5_registry(tmp_path)

    result = registry.match("Validate the grid environment boundaries")

    assert set(result["scores"]) == {"validate-environment", "analyze-episode"}
    assert result["threshold"] == 0.2
    assert all(0.0 <= score <= 1.0 for score in result["scores"].values())


def test_score_exactly_at_threshold_triggers_skill(tmp_path):
    # Five keywords in the skill; the prompt shares one of them -> 1/5 = 0.2.
    write_skill(tmp_path / "skills", "five", name="alpha", description="bravo charlie delta echo")
    registry = SkillRegistry.discover(tmp_path)

    result = registry.match("alpha")

    assert result["scores"]["alpha"] == 0.2
    assert result["chosen"] == "alpha"


def test_match_with_no_skills_chooses_nothing(tmp_path):
    result = SkillRegistry.discover(tmp_path).match("Validate the grid environment boundaries")

    assert result == {"scores": {}, "threshold": 0.2, "chosen": None, "best_score": 0.0}


# ---------------------------------------------------------------------------
# 7) Agent Skills: logging (plan.md Step 4, tests.md T11-T12)
# ---------------------------------------------------------------------------
def read_log(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_prompt_match_is_logged_with_all_fields(tmp_path):
    registry = build_lab5_registry(tmp_path)
    log_path = tmp_path / ".mini-coding-agent" / "skills.log.jsonl"
    printed = []
    logger = SkillLogger(log_path, echo=printed.append)
    prompt = "Validate the grid environment boundaries"
    result = registry.match(prompt)

    logger.log_prompt_match(prompt, result, registry.get(result["chosen"]))

    [entry] = read_log(log_path)
    assert {"time", "prompt", "scores", "threshold", "chosen", "trigger"} <= set(entry)
    assert entry["trigger"] == "prompt"
    assert entry["prompt"] == prompt
    assert set(entry["scores"]) == {"validate-environment", "analyze-episode"}
    assert entry["threshold"] == 0.2
    assert entry["chosen"] == "validate-environment"
    assert entry["skill_path"].endswith("SKILL.md")
    assert printed == [f"[skill] validate-environment (score {result['best_score']}, prompt)"]


def test_prompt_with_no_match_is_still_logged(tmp_path):
    registry = build_lab5_registry(tmp_path)
    log_path = tmp_path / ".mini-coding-agent" / "skills.log.jsonl"
    printed = []
    logger = SkillLogger(log_path, echo=printed.append)
    result = registry.match("Write a hello world script")

    logger.log_prompt_match("Write a hello world script", result)

    [entry] = read_log(log_path)
    assert entry["chosen"] is None
    assert entry["skill_path"] is None
    assert set(entry["scores"]) == {"validate-environment", "analyze-episode"}
    assert printed[0].startswith("[skill] none")


def test_tool_use_is_logged_with_tool_trigger_and_empty_scores(tmp_path):
    registry = build_lab5_registry(tmp_path)
    log_path = tmp_path / ".mini-coding-agent" / "skills.log.jsonl"
    printed = []
    logger = SkillLogger(log_path, echo=printed.append)

    logger.log_tool_use("Inspect the environment", "validate-environment", registry.get("validate-environment"))
    logger.log_tool_use("Inspect the environment", "made-up-skill", None)

    found, missing = read_log(log_path)
    assert found["trigger"] == "tool"
    assert found["scores"] == {}
    assert found["chosen"] == "validate-environment"
    assert found["prompt"] == "Inspect the environment"
    assert missing["chosen"] is None
    assert missing["requested"] == "made-up-skill"
    assert printed == [
        "[skill] validate-environment (tool)",
        "[skill] none (tool requested unknown skill 'made-up-skill')",
    ]


def test_log_appends_one_line_per_decision(tmp_path):
    registry = build_lab5_registry(tmp_path)
    log_path = tmp_path / ".mini-coding-agent" / "skills.log.jsonl"
    logger = SkillLogger(log_path, echo=None)

    for prompt in ["Validate the grid environment boundaries", "Write a hello world script", "Analyze this episode"]:
        logger.log_prompt_match(prompt, registry.match(prompt))

    assert [entry["prompt"] for entry in read_log(log_path)] == [
        "Validate the grid environment boundaries",
        "Write a hello world script",
        "Analyze this episode",
    ]


def test_log_write_failure_does_not_crash(tmp_path):
    blocker = tmp_path / "not-a-folder"
    blocker.write_text("this is a file, so it cannot hold the log", encoding="utf-8")
    printed = []
    logger = SkillLogger(blocker / "skills.log.jsonl", echo=printed.append)

    logger.log_tool_use("anything", "missing", None)

    assert "could not write skill log" in printed[0]


# ---------------------------------------------------------------------------
# 7) Agent Skills: loading skills on agent startup (plan.md Step 5, tests.md T4)
# ---------------------------------------------------------------------------
def test_agent_starts_normally_with_no_skill_folders(tmp_path):
    agent = build_agent(tmp_path, ["<final>Done.</final>"])

    assert len(agent.skills) == 0
    assert agent.ask("Say hi") == "Done."


def test_agent_discovers_skills_on_startup(tmp_path):
    write_skill(tmp_path / ".claude" / "skills", "validate-environment", name="validate-environment", description=LAB5_VALIDATE)
    write_skill(tmp_path / "skills", "pr-review", name="pr-review", description="Review a pull request.")

    agent = build_agent(tmp_path, [])

    assert sorted(agent.skills.names()) == ["pr-review", "validate-environment"]
    assert agent.skill_logger.path == tmp_path / ".mini-coding-agent" / "skills.log.jsonl"


def test_delegate_child_reuses_parent_skills(tmp_path):
    write_skill(tmp_path / "skills", "demo", name="demo")
    agent = build_agent(tmp_path, ["<final>child done</final>"])

    with patch("mini_coding_agent.SkillRegistry.discover") as discover:
        agent.tool_delegate({"task": "inspect README.md", "max_steps": 1})

    discover.assert_not_called()


def test_welcome_screen_lists_discovered_skills(tmp_path):
    write_skill(tmp_path / "skills", "demo", name="demo")
    with_skills = build_welcome(build_agent(tmp_path, []), model="qwen3.5:4b", host="http://127.0.0.1:11434")
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    without_skills = build_welcome(build_agent(empty_dir, []), model="qwen3.5:4b", host="http://127.0.0.1:11434")

    assert "SKILLS     demo" in with_skills
    assert "SKILLS     none" in without_skills
    assert len({len(line) for line in with_skills.splitlines()}) == 1


# ---------------------------------------------------------------------------
# 7) Agent Skills: prompt-triggered skills (plan.md Step 6, tests.md T8)
# ---------------------------------------------------------------------------
VALIDATE_STEPS = "1. Read src/environment.py\n2. Check every cell for boundary moves\n3. Report terminal states"


def build_skill_agent(tmp_path, outputs):
    skills = tmp_path / ".claude" / "skills"
    write_skill(skills, "validate-environment", name="validate-environment", description=LAB5_VALIDATE, body=VALIDATE_STEPS)
    write_skill(skills, "analyze-episode", name="analyze-episode", description=LAB5_ANALYZE, body="1. Look for loops")
    return build_agent(tmp_path, outputs)


def test_matching_prompt_puts_skill_under_active_skill(tmp_path):
    agent = build_skill_agent(tmp_path, ["<final>Validated.</final>"])

    agent.ask("Validate the grid environment boundaries")

    sent = agent.model_client.prompts[0]
    assert "Active skill:" in sent.splitlines()
    assert "- name: validate-environment" in sent
    assert VALIDATE_STEPS in sent
    assert "1. Look for loops" not in sent  # only the chosen skill is loaded
    # Demo fix: skill goes before the transcript, so the latest tool results are read last.
    assert sent.index("Active skill:") < sent.index("Transcript:") < sent.index("Current user request:")


def test_unrelated_prompt_adds_no_active_skill(tmp_path):
    agent = build_skill_agent(tmp_path, ["<final>Hello.</final>"])

    agent.ask("Write a hello world script")

    assert "Active skill:" not in agent.model_client.prompts[0]
    assert agent.active_skill is None


def test_ask_logs_the_prompt_decision(tmp_path):
    agent = build_skill_agent(tmp_path, ["<final>Validated.</final>", "<final>Hello.</final>"])

    agent.ask("Validate the grid environment boundaries")
    agent.ask("Write a hello world script")

    first, second = read_log(tmp_path / ".mini-coding-agent" / "skills.log.jsonl")
    assert first["trigger"] == "prompt"
    assert first["chosen"] == "validate-environment"
    assert set(first["scores"]) == {"validate-environment", "analyze-episode"}
    assert second["chosen"] is None


def test_active_skill_stays_for_every_step_of_one_request(tmp_path):
    (tmp_path / "notes.txt").write_text("grid notes\n", encoding="utf-8")
    agent = build_skill_agent(
        tmp_path,
        [
            '<tool>{"name":"read_file","args":{"path":"notes.txt","start":1,"end":1}}</tool>',
            "<final>Validated.</final>",
        ],
    )

    agent.ask("Validate the grid environment boundaries")

    assert len(agent.model_client.prompts) == 2
    assert all(VALIDATE_STEPS in sent for sent in agent.model_client.prompts)


def test_active_skill_resets_on_next_request(tmp_path):
    agent = build_skill_agent(tmp_path, ["<final>Validated.</final>", "<final>Hello.</final>"])

    agent.ask("Validate the grid environment boundaries")
    agent.ask("Write a hello world script")

    assert "Active skill:" in agent.model_client.prompts[0]
    assert "Active skill:" not in agent.model_client.prompts[1]


def test_no_skills_means_no_skill_log(tmp_path):
    agent = build_agent(tmp_path, ["<final>Done.</final>"])

    agent.ask("Validate the grid environment boundaries")

    assert not (tmp_path / ".mini-coding-agent" / "skills.log.jsonl").exists()
    assert "Active skill:" not in agent.model_client.prompts[0]


def test_long_skill_instructions_are_clipped(tmp_path):
    write_skill(tmp_path / "skills", "big", name="validate-environment", description=LAB5_VALIDATE, body="x" * 5000)
    agent = build_agent(tmp_path, ["<final>Done.</final>"])

    agent.ask("Validate the grid environment boundaries")

    sent = agent.model_client.prompts[0]
    assert "x" * 2000 in sent
    assert "x" * 2001 not in sent
    assert "[truncated" in sent


# ---------------------------------------------------------------------------
# 7) Agent Skills: the use_skill tool (plan.md Step 7, tests.md T9-T10)
# ---------------------------------------------------------------------------
def test_use_skill_returns_instructions_for_known_name(tmp_path):
    agent = build_skill_agent(tmp_path, [])
    agent.current_request = "Check the grid"

    result = agent.run_tool("use_skill", {"name": "validate-environment"})

    assert VALIDATE_STEPS in result
    assert agent.active_skill["name"] == "validate-environment"


def test_use_skill_unknown_name_lists_valid_names(tmp_path):
    agent = build_skill_agent(tmp_path, [])

    result = agent.run_tool("use_skill", {"name": "made-up-skill"})

    assert result.startswith("error: unknown skill 'made-up-skill'")
    assert "analyze-episode" in result
    assert "validate-environment" in result
    assert agent.active_skill is None


def test_use_skill_ignores_capitalization(tmp_path):
    agent = build_skill_agent(tmp_path, [])

    result = agent.run_tool("use_skill", {"name": "Validate-Environment"})

    assert VALIDATE_STEPS in result


def test_use_skill_rejects_empty_name(tmp_path):
    agent = build_skill_agent(tmp_path, [])

    result = agent.run_tool("use_skill", {})

    assert result.startswith("error: invalid arguments for use_skill: name must not be empty")
    assert "use_skill" in result.split("example:")[1]


def test_use_skill_calls_are_logged_as_tool(tmp_path):
    agent = build_skill_agent(
        tmp_path,
        [
            '<tool>{"name":"use_skill","args":{"name":"analyze-episode"}}</tool>',
            '<tool>{"name":"use_skill","args":{"name":"nope"}}</tool>',
            "<final>Done.</final>",
        ],
    )

    agent.ask("Write a hello world script")

    entries = read_log(tmp_path / ".mini-coding-agent" / "skills.log.jsonl")
    prompt_entry, found, missing = entries
    assert prompt_entry["trigger"] == "prompt" and prompt_entry["chosen"] is None
    assert found["trigger"] == "tool"
    assert found["chosen"] == "analyze-episode"
    assert found["scores"] == {}
    assert found["prompt"] == "Write a hello world script"
    assert missing["chosen"] is None and missing["requested"] == "nope"


def test_skill_loaded_by_tool_shows_as_active_skill_on_later_steps(tmp_path):
    agent = build_skill_agent(
        tmp_path,
        [
            '<tool>{"name":"use_skill","args":{"name":"validate-environment"}}</tool>',
            "<final>Done.</final>",
        ],
    )

    agent.ask("Write a hello world script")

    first, second = agent.model_client.prompts
    assert "Active skill:" not in first
    assert "Active skill:" in second
    assert "- name: validate-environment" in second


def test_prompt_lists_skills_and_use_skill_tool(tmp_path):
    agent = build_skill_agent(tmp_path, [])

    assert "Skills:" in agent.prefix.splitlines()
    assert "- validate-environment: " + LAB5_VALIDATE in agent.prefix
    assert "- use_skill(name: str) [safe]" in agent.prefix
    assert '"name": "use_skill"' in agent.prefix


def test_no_skills_means_no_use_skill_tool(tmp_path):
    agent = build_agent(tmp_path, [])

    assert "use_skill" not in agent.tools
    assert "use_skill" not in agent.prefix
    assert "Skills:" not in agent.prefix.splitlines()


# ---------------------------------------------------------------------------
# 7) Agent Skills: fixes from the first Lab 4 demo run (tests.md D1, attempt 1)
# ---------------------------------------------------------------------------
def test_active_skill_tells_model_to_track_progress(tmp_path):
    agent = build_skill_agent(tmp_path, ["<final>Done.</final>"])

    agent.ask("Validate the grid environment boundaries")

    sent = agent.model_client.prompts[0]
    assert "already loaded; do not call use_skill again" in sent
    assert "Check the Transcript for steps already done and do the next one." in sent
    assert "When the steps are done, reply with <final>." in sent


def test_latest_tool_result_comes_after_skill_instructions(tmp_path):
    (tmp_path / "notes.txt").write_text("grid notes\n", encoding="utf-8")
    agent = build_skill_agent(
        tmp_path,
        [
            '<tool>{"name":"read_file","args":{"path":"notes.txt","start":1,"end":1}}</tool>',
            "<final>Done.</final>",
        ],
    )

    agent.ask("Validate the grid environment boundaries")

    second = agent.model_client.prompts[1]
    # rindex: the memory section (before the skill) also quotes the file in a
    # short note; the transcript copy is the last occurrence.
    assert second.index(VALIDATE_STEPS) < second.rindex("grid notes")
    assert second.rindex("grid notes") > second.index("Transcript:")


def test_use_skill_for_already_active_skill_returns_short_nudge(tmp_path):
    agent = build_skill_agent(
        tmp_path,
        [
            '<tool>{"name":"use_skill","args":{"name":"validate-environment"}}</tool>',
            "<final>Done.</final>",
        ],
    )

    agent.ask("Validate the grid environment boundaries")

    [tool_event] = [item for item in agent.session["history"] if item["role"] == "tool"]
    assert tool_event["content"].startswith("Skill 'validate-environment' is already active")
    assert VALIDATE_STEPS not in tool_event["content"]
    prompt_entry, tool_entry = read_log(tmp_path / ".mini-coding-agent" / "skills.log.jsonl")
    assert prompt_entry["trigger"] == "prompt"
    assert tool_entry["trigger"] == "tool" and tool_entry["chosen"] == "validate-environment"


def test_use_skill_for_a_different_skill_replaces_active_skill(tmp_path):
    agent = build_skill_agent(
        tmp_path,
        [
            '<tool>{"name":"use_skill","args":{"name":"analyze-episode"}}</tool>',
            "<final>Done.</final>",
        ],
    )

    agent.ask("Validate the grid environment boundaries")

    assert agent.active_skill["name"] == "analyze-episode"
    second = agent.model_client.prompts[1]
    assert "- name: analyze-episode" in second
    assert "- name: validate-environment" not in second
