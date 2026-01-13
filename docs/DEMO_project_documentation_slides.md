---
marp: true
theme: default
paginate: true
---

# DEMO Project Documentation
### Control Panel Command Station
- Retro military console → multi-app launcher
- Personas: `admin` vs `scientist`
- Goal: publish a teachable, hosted knowledge base

---

## Why Move Beyond README?
- README is linear + hard to search
- Ops teams need tabs, nav, and permalinks
- MkDocs builds static HTML with instant preview
- GitHub Pages hosts it for free

---

## Build Flow (MkDocs)
1. `pip install mkdocs mkdocs-material`
2. `mkdocs serve` → live preview
3. `mkdocs gh-deploy` → push to `gh-pages`
4. Enable Pages (`Settings → Pages`)

*Key idea: every push to `main` refreshes docs automatically.*

---

## Structuring Content
- `docs/DEMO_project_documentation.md` holds primary guide
- Break chapters: Personas, Launch Recipes, Proxies, Onboarding
- Use callouts for persona-specific guidance
- Keep env var tables reusable via snippets

---

## Docusaurus vs MkDocs
- MkDocs = fastest path, Markdown-only
- Docusaurus = MDX + React widgets + versioning
- Start MkDocs, graduate to Docusaurus when you need i18n/blog/API playgrounds

---

## Teaching Plan
- Demo live edit in MkDocs
- Assign learners to document a new reactor card
- Use uploaded quizzes to check understanding
- Share slide deck or export via Marp → PDF
