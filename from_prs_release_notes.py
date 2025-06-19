import os
from github import Github
from dotenv import load_dotenv
import openai
from datetime import datetime, timezone
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
        # List of commit SHAs in this PR
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
    # Only keep commits not in any PR
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
        "Group under Features, Fixes, Improvements and General Updates. Prefer the PR description if available. Omit trivial/internal changes.\n\n"
        "Changes:\n" +
        "\n".join(f"- {item}" for item in items)
    )
    openai.api_key = OPENAI_API_KEY
    response = openai.chat.completions.create(
        model="gpt-4o-mini",  # or "gpt-4o-mini" for lower cost
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
            "Write a single, clear, categorized release note in Markdown for end-users, grouping by Features, Fixes, Improvements, General Updates.\n\n" +
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

if __name__ == "__main__":
    print("=== AI Release Note Generator (Phase 2: PR Support & Deduplication) ===\n")

    repo = input("Enter repo full name (e.g. nvm-sh/nvm): ").strip()
    since = input("Enter start date (YYYY-MM-DD): ").strip()
    until = input("Enter end date (YYYY-MM-DD): ").strip()

    print("\nFetching merged PRs...")
    pr_list = get_merged_prs(repo, since, until)
    print(f"Found {len(pr_list)} merged PRs.")

    print("Fetching all commits...")
    commit_objs = get_commits(repo, since, until)
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

    # Create a unique filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"RELEASE_NOTES_{timestamp}.md"
    with open(filename, "w") as f:
        f.write(release_notes)
    print(f"Release notes written to {filename}")