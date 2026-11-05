# How we work on credence

The purpose of this repository is twofold: a finished project that hiring
managers will read, and a place where the developer gets back into writing
code by hand. The protocol below serves both. It overrides any habit the
assistant has of doing a whole checkpoint in one go.

## Commits: small, one concern, reviewable in five minutes

- A commit is one concern: one module, one endpoint, one test file, one
  config change. Never "checkpoint 2". If the diff needs more than one
  paragraph to describe, it is two commits.
- Soft limit 150 lines changed, hard limit 250, generated files excluded.
  A step that would exceed it is split before it starts, not after.
- Every commit leaves the repository green: `uv run ruff check .`,
  `uv run ruff format --check .`, `uv run mypy .`, `uv run pytest`.
  No commit depends on a later one to pass.
- The developer commits. The assistant never runs `git commit`, `add`,
  `stash`, `reset` or `tag`.

## The loop for every step

1. **Propose.** Before writing anything, the assistant states the step in
   three lines: what it adds, which files it touches, which test proves it.
   It waits for "go".
2. **Build.** The assistant makes the change and runs the four checks.
3. **Stop.** It reports: files changed with a one-line reason each, the
   check results (exit codes, not summaries), and the commit message
   (one-line title, then a body of plain paragraphs). It does not start
   the next step.
4. **Review.** The developer reads the diff in full. Questions are asked
   and answered before the commit, not after. If the developer can't
   explain a line, the step isn't done.
5. **Commit.** The developer commits. Then "continue".

## Practice steps: the developer writes the second one

Most of this codebase follows patterns: an endpoint, a test, a metric, a
generator case, a Pydantic model, a migration. The rule:

- The assistant writes the **first** instance of each pattern, with
  comments that name the pattern's parts.
- The **second** instance of the same pattern is a **practice step**: the
  assistant writes a spec and the developer writes the code.
- A practice spec is short: the file to create or change, the function
  signatures, the behaviour in plain words, the test that must pass, and
  the first instance to copy from. No code.
- The developer writes it by hand, runs the four checks, and says "review".
- The assistant reviews the diff the way a colleague would: what's right,
  what's wrong, what's merely different from how it would have done it,
  each labelled as such. It does not rewrite the developer's code. If
  something must change, it says what and why and the developer changes it.
- Third and later instances: the developer's choice each time. "Mine" or
  "yours". The default after two practice steps of a pattern is "mine".

The assistant keeps a list in `PRACTICE.md`: each pattern, who wrote each
instance, and one line of feedback from each review. The list is for the
developer; it never goes in the README.

## Pairing on the hard parts

Some steps have no pattern yet: the extraction call, the eval runner, the
cost accounting. For those the assistant may propose a **pairing step**:
it writes the skeleton (signatures, docstrings, `raise NotImplementedError`)
and the test, and the developer fills in the bodies with the assistant
answering questions. Same review afterwards.

## What the assistant does not do

- Batch several steps because they're small.
- Fix the developer's practice code instead of reviewing it.
- Add scope the plan doesn't ask for, however tempting.
- Write README sentences the code doesn't yet make true.
- Add attribution lines or session links to commits or pull requests.

## Checkpoints still exist

The plan's checkpoints (PLAN.md section 7) are milestones, not commits. A
checkpoint is reached when its steps are all committed and its "done when"
holds. The assistant marks it in PLAN.md with what was built and what was
learned, in its own small commit.
