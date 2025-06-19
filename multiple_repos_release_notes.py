import os
from github import Github
from dotenv import load_dotenv
import openai
from datetime import datetime, timezone
import yaml

# Load environment variables
load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not GITHUB_TOKEN:
    print("Missing GITHUB_TOKEN in .env file.")
    exit(1)
if not OPENAI_API_KEY:
    print("Missing OPENAI_API_KEY in .env file.")
    exit(1)

def load_config(config_file="config.yaml"):
    with open(config_file, "r") as f:
        return yaml.safe_load(f)

def get_commits(repo_full_name, since, until):
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(repo_full_name)
    since_dt = datetime.strptime(since, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    until_dt = datetime.strptime(until, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    commits = repo.get_commits(since=since_dt, until=until_dt)
    return list(commits)

def get_merged_prs(repo_full_name, since, until):
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(repo_full_name)
    since_dt = datetime.strptime(since, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    until_dt = datetime.strptime(until, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    pulls = repo.get_pulls(state="closed", sort="updated", direction="desc")
    prs = []
    for pr in pulls:
        if pr.merged_at is None:
            continue
        if not (since_dt <= pr.merged_at <= until_dt):
            continue
        commit_shas = [c.sha for c in pr.get_commits()]
        prs.append({
            "number": pr.number,
            "title": pr.title.strip(),
            "body": (pr.body or "").split("\n")[0].strip(),
            "author": pr.user.login,
            "merged_at": pr.merged_at,
            "commit_shas": set(commit_shas),
        })
    return prs

def filter_orphan_commits(commit_objs, pr_list):
    pr_commit_shas = set()
    for pr in pr_list:
        pr_commit_shas.update(pr["commit_shas"])
    return [c for c in commit_objs if c.sha not in pr_commit_shas]

def prep_llm_input(pr_list, orphan_commits):
    lines = []
    for pr in pr_list:
        summary = pr["title"]
        if pr["body"]:
            summary += " — " + pr["body"]
        lines.append(f"PR: {summary}")
    for commit in orphan_commits:
        summary = commit.commit.message.split("\n")[0].strip()
        lines.append(f"Commit: {summary}")
    return lines

def get_release_notes(items):
    if not items:
        return "No changes found in the selected period."
    prompt = (
        "You are a professional technical writer. Given these PRs and commits, generate a concise, categorized release note in Markdown for end-users. "
        "Group under Features, Fixes, and Improvements. Prefer the PR description if available. Omit trivial/internal changes.\n\n"
        "Changes:\n" +
        "\n".join(f"- {item}" for item in items)
    )
    openai.api_key = OPENAI_API_KEY
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "user", "content": prompt}
        ],
        max_tokens=500
    )
    return response.choices[0].message.content.strip()

def chunk_list(lst, chunk_size):
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]

def summarize_in_chunks(items, get_release_notes_func, chunk_size=30):
    summaries = []
    for chunk in chunk_list(items, chunk_size):
        summary = get_release_notes_func(chunk)
        summaries.append(summary)
    if len(summaries) == 1:
        return summaries[0]
    else:
        final_prompt = (
            "Here are several summaries of code changes for a release. "
            "Write a single, clear, categorized release note in Markdown for end-users, grouping by Features, Fixes, Improvements.\n\n" +
            "\n\n".join(f"Batch {i+1}:\n{summary}" for i, summary in enumerate(summaries))
        )
        return get_release_notes_func([final_prompt])

def need_chunking(items, max_items=40, max_chars=10000):
    if len(items) > max_items:
        return True
    total_chars = sum(len(m) for m in items)
    if total_chars > max_chars:
        return True
    return False

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

def prompt_for_list(prompt, default_list):
    default_str = ", ".join([f"{r['owner']}/{r['name']}" for r in default_list])
    user_input = input(f"{prompt} (comma-separated, default: {default_str}): ").strip()
    if not user_input:
        return default_list
    out = []
    for item in user_input.split(","):
        owner_repo = item.strip().split("/")
        if len(owner_repo) == 2:
            out.append({'owner': owner_repo[0], 'name': owner_repo[1]})
    return out if out else default_list

if __name__ == "__main__":
    print("=== AI Release Note Generator (Phase 3: Multi-Repo & Config) ===\n")

    config = load_config()
    repos = config.get("repos", [])
    date_start = config.get("date_range", {}).get("start", "")
    date_end = config.get("date_range", {}).get("end", "")
    output_dir = config.get("output_dir", "release_notes")

    # Prompt for overrides
    print(f"Repos in config: {[f'{r['owner']}/{r['name']}' for r in repos]}")
    repos = prompt_for_list("Enter repos to process", repos)

    user_start = input(f"Enter start date (YYYY-MM-DD, default: {date_start}): ").strip()
    since = user_start if user_start else date_start

    user_end = input(f"Enter end date (YYYY-MM-DD, default: {date_end}): ").strip()
    until = user_end if user_end else date_end

    user_out_dir = input(f"Enter output directory (default: {output_dir}): ").strip()
    output_dir = user_out_dir if user_out_dir else output_dir

    ensure_dir(output_dir)
    all_filenames = []

    for repo in repos:
        repo_full = f"{repo['owner']}/{repo['name']}"
        print(f"\n=== Processing {repo_full} ===")
        print("Fetching merged PRs...")
        pr_list = get_merged_prs(repo_full, since, until)
        print(f"Found {len(pr_list)} merged PRs.")

        print("Fetching all commits...")
        commit_objs = get_commits(repo_full, since, until)
        print(f"Found {len(commit_objs)} total commits.")

        orphan_commits = filter_orphan_commits(commit_objs, pr_list)
        print(f"Found {len(orphan_commits)} commits not in any merged PR.")

        items_for_llm = prep_llm_input(pr_list, orphan_commits)
        print(f"Preparing {len(items_for_llm)} total change items for LLM.")

        print("Sending items to OpenAI for summarization...\n")
        if need_chunking(items_for_llm):
            print("Large change set detected. Splitting into manageable chunks for LLM processing...")
            release_notes = summarize_in_chunks(items_for_llm, get_release_notes)
        else:
            release_notes = get_release_notes(items_for_llm)

        print("\n--- Release Notes ---\n")
        print(release_notes)
        print("\n---------------------\n")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{output_dir}/RELEASE_NOTES_{repo['owner']}_{repo['name']}_{timestamp}.md"
        with open(filename, "w") as f:
            f.write(release_notes)
        print(f"Release notes written to {filename}")
        all_filenames.append(filename)

    print("\nAll release notes generated:")
    for fname in all_filenames:
        print(f"- {fname}")