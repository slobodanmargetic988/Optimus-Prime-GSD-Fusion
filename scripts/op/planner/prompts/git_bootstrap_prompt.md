You are preparing a repository for Optimus initialization.

Hard requirements:
1. Work only inside repo_root: {{REPO_ROOT}}
2. Initialize git if missing.
3. Configure git user identity if missing, then create first commit.
4. Ensure `README.md` exists with placeholder text for project "{{PROJECT_NAME}}".
5. Ensure local branch `{{REQUIRED_BRANCH}}` exists.
6. Attempt to push to `origin` if a remote is configured.
7. Run this exact deterministic validator command (same verifier OP will run after your execution):
   {{VALIDATOR_COMMAND}}
8. If validator fails, fix the repository and rerun the same validator command until it passes.

Execution notes:
- If no remote is configured, keep local repo valid and continue.
- Do not modify OP planning artifacts under `reports/optimus-prime/planning/`.
- Keep output concise.
