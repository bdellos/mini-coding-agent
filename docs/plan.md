# Plan

## Phase 0: Baseline
### Step 1: Pull the model
- **What:** Pull the model (`ollama pull qwen3.5:4b`) and run the existing tests before any changes.
- **Where:** Terminal, in the `mini-coding-agent` folder.
- **Done when:** `ollama list` shows `qwen3.5:4b` and all current tests pass.

## Phase 1: Building blocks
### Step 2: Skill loading
- **What:** Read `SKILL.md` files and discover skills in `skills/` and `.claude/skills`.
- **Where:** New `Skills` section in `mini_coding_agent.py`.
- **Done when:** Tests confirm both folders are found, invalid files are skipped, and `skills/` wins on duplicate names.
### Step 3: Similarity check
- **What:** Split user text into words, drop common words, strip word endings, compute the score, then pick the best skill if the threshold is reached.
- **Where:** The new `Skills` section in `mini_coding_agent.py` (same place as Step 2).
- **Done when:** Tests show a grid-validation prompt picks `validate-environment` and "Write a hello world script" picks no skill.
### Step 4: Skill logger
- **What:** Write one JSON line per decision to `.mini-coding-agent/skills.log.jsonl` and print the one-line summary.
- **Where:** The `Skills` section of `mini_coding_agent.py` (writes to `.mini-coding-agent/skills.log.jsonl`)
- **Done when:** A test reads the log file back and finds every required field.

## Phase 2: Connect to the agent
### Step 5: Load skills on startup
- **What:** Discover all available skills when the agent starts.
- **Where:** `MiniAgent.__init__`
- **Done when:** A test shows the agent finds the skills in a test workspace and starts normally when there are no skill folders.
### Step 6: Prompt trigger
- **What:** Run the similarity check at the start of each request. Log the result and add the chosen skill's instructions under "Active skill".
- **Where:** `ask()` and `prompt()`
- **Done when:** A test using the existing fake model shows the skill text in the prompt sent to the model.
### Step 7: The `use_skill` tool
- **What:** Add `use_skill` to the tool list, its argument check and its example, and list the available skills in the agent's instructions.
- **Where:** `build_tools()`, `validate_tool()`, `tool_example()`, `build_prefix()`
- **Done when:** Tests show a known name returns the instructions. An unknown name returns an error and the call is logged as `tool`. 
### Step 8: Regression check
- **What:** Rerun all tests.
- **Where:** `tests/test_mini_coding_agent.py`, run with `uv run python -m pytest -q` (or `python -m pytest -q` without uv). This is the same command the repo's CI uses.
- **Done when:** All of the old tests and all of the new tests pass.

## Phase 3: Demo on Lab 4
### Step 9: Improve the Lab 5 skills
- **What:** Inspect the `validate-environment` and `analyze_episode` skills under the Lab 5 repository. Give them a richer description and numbered, concrete steps that a 4B model can follow. Copy the skill into Lab 4's repository under `.claude/skills`.
- **Where:** repositories for Lab 4 and Lab 5.
- **Done when:** The relevant skills have been copied to the Lab 4 repository under `.claude/skills` and each skill has a clear description and numbered steps.
### Step 10: Run the agent in the Lab 4 folder
- **What:** Run the agent in the Lab 4 folder using a matching prompt and an unrelated one. Save the log and the terminal output.
- **Where:** Lab 4 repository.
- **Done when:** The log shows the prompt, the scores, and the skills being executed.
### Step 11: Tune the threshold (if needed)
- **What:** Check that the matching prompt scores at or above the threshold and the unrelated prompt scores below it. If not, pick a threshold between the two scores and record the new value and the reason in `spec.md`.
- **Where:** `spec.md`
- **Done when:** Both demo prompts behave as expected with the recorded threshold.

## Phase 4: Wrap-up
### Step 12: Fill in `tests.md`
- **What:** Fill in `tests.md` with the results. Add a short "Skills" to the readme that links the appropriate documentation.
- **Where:** `tests.md`, `README.md`
- **Done when:** Results and skills have been logged to their appropriate locations.