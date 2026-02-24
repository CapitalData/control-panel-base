# Git Submodules Workflow — ACD Meta-Repo

> A practical demo book covering how the ACD meta-repo uses Git submodules to manage multiple service repositories as a single workspace.

---

## 1. What Are Git Submodules?

A **git submodule** is a pointer inside one repository (the *parent*) that references a specific commit in another repository (the *child*). The parent doesn't store the child's files — it stores a commit SHA and a URL.

```
acd-meta-repo/          ← parent (meta-repo)
├── finance_tracker/     ← submodule → CapitalData/finance_tracker_app
├── control_panel_dist/  ← submodule → CapitalData/control_panel_dist
├── phoenix_arize/       ← submodule → CapitalData/phoenix_arize
├── ollama_llm/          ← submodule → CapitalData/ollama_llm
└── local_llm/           ← submodule → CapitalData/local_llm
```

The `.gitmodules` file at the repo root maps each directory to its remote URL:

```ini
[submodule "finance_tracker"]
    path = finance_tracker
    url = git@github.com:CapitalData/finance_tracker_app.git

[submodule "control_panel_dist"]
    path = control_panel_dist
    url = git@github.com:CapitalData/control_panel_dist.git
```

---

## 2. Key Concepts

| Concept | What It Means |
|---|---|
| **Parent repo** | `acd-meta-repo` — orchestrates the workspace |
| **Submodule** | An independent repo checked out inside the parent |
| **Pinned commit** | The parent records which exact commit of the submodule to use |
| **Detached HEAD** | Submodules check out a specific commit, not a branch — you must checkout a branch before committing |

!!! note "Important Mental Model"
    Each submodule directory is a **fully independent git repo**. Running `git status` inside `finance_tracker/` shows that repo's status, not the parent's.

---

## 3. Cloning the Meta-Repo (First Time)

```bash
# Clone the parent AND all submodules in one step
git clone --recurse-submodules git@github.com:CapitalData/acd-meta-repo.git

# If you already cloned without --recurse-submodules:
cd acd-meta-repo
git submodule update --init --recursive
```

---

## 4. Daily Workflow — Making Changes in a Submodule

### Step 1: Enter the submodule and switch to a branch

```bash
cd finance_tracker
git checkout main          # submodules default to detached HEAD
```

### Step 2: Make your changes, stage, and commit

```bash
git add -A
git commit -m "add new invoice parser feature"
```

### Step 3: Push the submodule to its own remote

```bash
git push origin main
```

### Step 4: Go back to the parent and record the new commit

```bash
cd ..                      # back to acd-meta-repo root
git add finance_tracker    # stages the updated submodule pointer
git commit -m "update finance_tracker submodule ref"
git push origin main
```

> **Why both pushes?** The submodule push sends your code. The parent push updates the pointer so collaborators get the right version.

---

## 5. Pulling Updates From Collaborators

```bash
# From the meta-repo root
git pull origin main

# Update all submodules to the commits the parent now points to
git submodule update --init --recursive
```

Or pull the latest from each submodule's own remote:

```bash
git submodule foreach 'git checkout main && git pull origin main'
```

---

## 6. Bulk Operations — Push All Dirty Submodules

When you've edited multiple submodules and want to push everything:

```bash
# 1. Commit and push inside each submodule that has changes
git submodule foreach 'git add -A && git diff --cached --quiet || git commit -m "update" && git push origin main || true'

# 2. Then update the parent
git add -A
git commit -m "update submodule refs"
git push origin main
```

---

## 7. Checking Status Across Everything

```bash
# See which submodules have uncommitted changes or new commits
git status

# Detailed per-submodule status
git submodule status

# See a summary of submodule changes
git diff --submodule
```

Output example:
```
 +a1b2c3d finance_tracker (heads/main)   ← '+' means local is ahead of pinned commit
  e4f5g6h control_panel_dist (heads/main) ← no prefix means in sync
```

---

## 8. Common Pitfalls & Solutions

### "HEAD detached" warning when entering a submodule

**Cause:** Submodules check out a pinned commit, not a branch.
**Fix:** Always `git checkout main` (or your working branch) before making changes.

```bash
cd ollama_llm
git checkout main    # attach to a branch first
# now edit, commit, push as normal
```

### "Modified content" in parent but you didn't change anything

**Cause:** Running the app may generate files (`.pyc`, `__pycache__`, data files).
**Fix:** Ensure `.gitignore` covers generated files. If it's just a submodule pointer mismatch:

```bash
git submodule update --init    # reset to the pinned commit
```

### Forgetting to push the submodule before pushing the parent

**Cause:** The parent now points to a commit that only exists on your machine.
**Fix:** Always push the submodule first, then the parent. To check:

```bash
git push --recurse-submodules=check origin main
```

This will error if any submodule commits haven't been pushed yet.

---

## 9. ACD Meta-Repo Submodule Map

| Directory | Remote Repository | Purpose |
|---|---|---|
| `finance_tracker/` | `CapitalData/finance_tracker_app` | Financial dashboard & tools |
| `control_panel_dist/` | `CapitalData/control_panel_dist` | Control panel UI & docs |
| `phoenix_arize/` | `CapitalData/phoenix_arize` | OpenTelemetry trace viewer |
| `ollama_llm/` | `CapitalData/ollama_llm` | Local LLM chat interface |
| `local_llm/` | `CapitalData/local_llm` | LLM endpoint utilities |

---

## 10. Quick Reference Card

| Task | Command |
|---|---|
| Clone everything | `git clone --recurse-submodules <url>` |
| Init after plain clone | `git submodule update --init --recursive` |
| Enter & attach to branch | `cd <submodule> && git checkout main` |
| Commit in submodule | `git add -A && git commit -m "msg"` |
| Push submodule | `git push origin main` |
| Record in parent | `cd .. && git add <submodule> && git commit -m "update ref"` |
| Push parent | `git push origin main` |
| Pull all updates | `git pull && git submodule update --init --recursive` |
| Bulk push all | `git submodule foreach 'git add -A && git diff --cached --quiet \|\| git commit -m "update" && git push origin main \|\| true'` |
| Check before parent push | `git push --recurse-submodules=check origin main` |

---

*This sourcebook is part of the ACD Control Panel documentation suite.*
