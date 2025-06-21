
# AI Release Note Generator — Multi-Use Utility

Generate clear, categorized release notes for one or more GitHub repositories using OpenAI’s LLMs.
Easily automate your workflow and adapt the tool to your needs—single repo or multi-repo, simple commit lists or full PR support.

---

# Model Provider Flexibility

This tool is designed to be model-agnostic — you can use it with OpenAI, Google Gemini, or swap in another LLM provider of your choice.

Simply update the LLM call in necessary functions like  `get_release_notes` to your preferred API, adjust your .env and requirements.txt, and you’re ready to go.

The scripts by default use OpenAI, but 2 examples illustrating the use with Gemini & Ollama are included in this repo:
* `from_commits_with_GeminiApiKey.py`
* `from_commits_with_Ollama.py`

---

## Project Structure & Scripts


| Script      | Phase   | What It Does                                                               |
| ----------- | ------- | -------------------------------------------------------------------------- |
| `from_commits_release_notes.py`   | Phase 1 | Single repo, **commit messages only** (basic use case)                             |
| `from_prs_release_notes.py` | Phase 2 | Single repo, **commits + PRs** with deduplication and richer context       |
| `multiple_repos_release_notes.py` | Phase 3 | **Multi-repo** support, YAML config, interactive/automated, combined notes |

---

## 1. Phase 1: Commits Only — `from_commits_release_notes.py`

**Purpose:**
Fetches commit messages for a single GitHub repo and summarizes them into categorized release notes using OpenAI.

**How to Use:**

```bash
python3 from_commits_release_notes.py
```

* **Prompts you** for repo (e.g., `nvm-sh/nvm`) and date range.
* Outputs: `RELEASE_NOTES.md` in your working directory.

**Use this script if:**
You want a minimal, simple tool for one repo and don’t care about PRs yet.

---

## 2. Phase 2: Commits + PRs (Deduplicated) — `from_prs_release_notes.py`

**Purpose:**
Improves release notes by fetching both merged PRs and direct commits.

* **Deduplicates:** Only includes PRs (with their title/desc) when present; commits only if not part of a PR.
* Generates a unique release notes file each run.

**How to Use:**

```bash
python3 from_prs_release_notes.py
```

* **Prompts you** for repo and date range.
* Outputs: `RELEASE_NOTES_<timestamp>.md` in your working directory.

**Use this script if:**
You want richer, more accurate release notes for a single repo that reflect both PR and commit activity.

---

## 3. Phase 3: Multi-Repo + Automation — `multiple_repos_release_notes.py`

**Purpose:**
Scales the tool for use with **multiple repos**.

* Loads config from `config.yaml` (repos, date range, output dir)
* Lets you override interactively, or run headless with `--auto`
* Generates per-repo release notes **and** a combined master file

**How to Use:**

### Interactive/manual mode

```bash
python3 multiple_repos_release_notes.py
```

* Prompts for repos, date range, output dir (or hit Enter to use config defaults)
* Outputs: Per-repo notes + master combined notes in your specified output dir

### Headless/automation mode

```bash
python3 multiple_repos_release_notes.py --auto
```

* Uses only values in `config.yaml`—no prompts, ready for cron/CI/CD
* Outputs: All notes in output dir from config

**Required config file: `config.yaml`**

```yaml
repos:
  - owner: github_org
    name: repo_name_1
  - owner: github_org
    name: repo_name_1
date_range:
  start: "2024-06-01"
  end: "2024-06-20"
output_dir: "release_notes"
```

**Use this script if:**
You want to process multiple repos at once, automate with a config file, and/or need combined master release notes.

---

## Setup (All Phases)

1. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

   where `requirements.txt` includes:

   ```
   PyGithub
   openai
   python-dotenv
   PyYAML
   ```

2. **Set up your `.env` file** with:

   ```
   GITHUB_TOKEN=ghp_xxxxxxx
   OPENAI_API_KEY=sk-xxxxxxx
   ```

   > Keep your `.env` out of version control!

3. *(Phase 3 only)*: Create or edit `config.yaml` as shown above.

---

## Notes

* **All scripts automatically handle large changesets** by chunking (to avoid LLM API token limits).
* **All scripts deduplicate PRs/commits** from Phase 2 onward.
* **You can use any script independently**; each phase is fully functional on its own.
* **Output filenames** are unique per run (Phase 2 and 3), easy to archive or review.

---

## Example Output (Phase 3)

```
release_notes/RELEASE_NOTES_github_org_repo_name_1_20240617_212300.md
release_notes/RELEASE_NOTES_github_org_repo_name_2_20240617_212300.md
release_notes/MASTER_RELEASE_NOTES_20240617_212301.md
```

---

## Troubleshooting

* For large or very active repos, restrict your date range.
* If you hit OpenAI token/rate limits, try smaller batches or a shorter date window.
* Scripts require Python 3.8+.

---

## License

Apache 2.0

---


