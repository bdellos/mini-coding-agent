# Tests

## How to run
- Automated tests: `uv run python -m pytest -q` from the `mini-coding-agent` folder
- Demo: run the agent from the Lab 4 folder (see Demo tests below)

## Automated unit tests

| ID | Area | What it checks | Expected result | Result |
|----|------|----------------|-----------------|--------|
| T1 | Discovery | Skills in `skills/` and `.claude/skills/` are found | Both skills listed | PASS|
| T2 | Discovery | A `SKILL.md` missing name or description is skipped | Skipped, no crash | PASS|
| T3 | Discovery | Same skill name in both folders | `skills/` version wins | PASS|
| T4 | Discovery | Workspace with no skill folders | Agent starts normally, no skills | PASS|
| T5 | Similarity | "Validate the grid environment boundaries" | Picks `validate-environment` | PASS|
| T6 | Similarity | "Write a hello world script" | No skill chosen | PASS|
| T7 | Similarity | Word endings ("validating" vs "validates") | Treated as the same word | PASS|
| T8 | Prompt trigger | Matching prompt with the fake model | Skill text appears under "Active skill" in the prompt | PASS|
| T9 | Tool trigger | `use_skill` with a known name | Returns the skill's instructions | PASS|
| T10 | Tool trigger | `use_skill` with an unknown name | Error listing valid names | PASS|
| T11 | Logging | Prompt-triggered decision | Log line has time, prompt, all scores, threshold, chosen skill, trigger `prompt` | PASS|
| T12 | Logging | Tool-triggered decision | Log line has trigger `tool` and empty scores | PASS|

## Regression tests
| ID | What it checks | Expected result | Result |
|----|----------------|-----------------|--------|
| R1 | All original repo tests | All pass | PASS: 55 passed, 1 skipped on Python 3.15 and 3.10. The original `main` test file run unmodified against the new code gives 18 passed, 1 skipped, matching the Step 1 baseline. The skip is the symlink test (Windows permissions). Lint shows 13 issues, all pre-existing on `main`, none new.|

## Demo tests (Lab 4, qwen3.5:4b)

### D1: Matching prompt
- **Prompt:** "Validate the grid environment in this repo: check its boundaries and terminal states."
- **Expected:** `validate-environment` is triggered; the agent follows its steps on `src/environment.py`.
- **Actual:** Actual (attempt 1, 18:51): `validate-environment` triggered at 0.35, but the agent re-read` src/environment.py` until the 10-step limit and gave no answer. Cause: the Active skill section came after the transcript, so the model kept re-running step 1. Fix: commit 2b4d670 moved the skill before the transcript, added progress cues and made repeated `use_skill` calls return a short reminder.
Actual (attempts 2–3, 19:05 and 19:06): Pass. The skill triggered at 0.35 and the agent finished in 3 and 10 tool steps. Both runs reported the `START_POSITION = (1, 1)` bug and "terminal states not defined"; attempt 2 also caught the context.md contradiction. No files were modified.
- **Log excerpt:** 
```json
{"time": "2026-11-23T02:05:27.688531+00:00", "trigger": "prompt", "prompt": "Validate the grid environment in this repo: check its boundaries and terminal states.", "scores": {"analyze-episode": 0.059, "validate-environment": 0.35}, "threshold": 0.2, "chosen": "validate-environment", "skill_path": "C:\\Users\\thehe\\Documents\\CS440\\Lab4\\.claude\\skills\\validate-environment\\SKILL.md"}
```

### D2: Unrelated prompt
- **Prompt:** "Write a hello world script."
- **Expected:** No skill triggered; the log shows all scores below the threshold.
- **Actual:** Pass in all three sessions. Scores were 0.0 for both skills, so no skill was triggered, and `write_file` was denied. In attempt 1, the model also called `use_skill` for both skills after the denial; those calls were logged with trigger tool, which is real-model evidence of the agent-triggered path. A stray "n" input at 19:06 was logged with no skill chosen.
- **Log excerpt:** 
```json
{"time": "2026-11-23T02:05:42.193924+00:00", "trigger": "prompt", "prompt": "Write a hello world script.", "scores": {"analyze-episode": 0.0, "validate-environment": 0.0}, "threshold": 0.2, "chosen": null, "skill_path": null}
```


## Acceptance criteria checklist
| Criterion (from spec.md) | Verified by |
|--------------------------|-------------|
| Skills in both folders are discovered | T1 |
| A grid-validation prompt triggers `validate-environment` | T5, T8, D1 |
| An unrelated prompt triggers nothing | T6, D2 |
| `use_skill` returns instructions; unknown name returns error | T9, T10 |
| Each decision appears in the log with all fields | T11, T12 |
| Existing agent tests still pass | R1 |
| The agent uses the Lab 5 skill in the Lab 4 repo, and the log shows it | D1 |

## Results summary
_(fill in after testing: what passed, what failed, any threshold changes)_
