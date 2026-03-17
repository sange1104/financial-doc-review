---
name: git-commit
description: Create structured git commits with consistent style and project-aware rules
---

# Git Commit Skill

You are responsible for creating clean, meaningful git commits for this project.

## Step 1. Inspect changes
- Run `git status`
- Run `git diff` (staged + unstaged)
- Run `git log --oneline -5` to follow style

## Step 2. Understand change type

Classify changes into one of:

- feat: new functionality
- fix: bug fix
- refactor: structure change without behavior change
- docs: documentation only
- analysis: experiment / failure case / evaluation insight (IMPORTANT)
- chore: setup or config

## Step 3. Generate commit message

- Format: `type(scope): description`
- Keep under 72 characters
- Use English only
- Be specific (avoid "update", "fix bug")

Examples:
- feat(ocr): add field extraction for id documents
- fix(validation): handle missing id_number edge case
- analysis(ocr): identify failures under glare conditions
- docs(rules): define pass/retake/review criteria

If `$ARGUMENTS` is provided, use it directly.

## Step 4. Smart staging

- Stage only relevant files
- NEVER stage:
  - `.env`
  - secrets
  - large raw data
- Group logically related changes into one commit

## Step 5. Consistency check (IMPORTANT)

Before committing, check:
- If decision logic changed → should docs also change?
- If rules updated → should README/docs be updated?
- If new feature → is it reflected in structure/docs?

Warn if mismatch exists.

## Step 6. Commit
git commit -m "$(cat <<'EOF'
type(scope): description

Co-Authored-By: Claude noreply@anthropic.com

EOF
)"


## Step 7. Output

Show:
- commit hash
- commit message
- staged files summary