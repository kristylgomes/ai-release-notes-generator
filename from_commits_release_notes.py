import os
from github import Github
from dotenv import load_dotenv
import openai
from datetime import datetime

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
    # Convert dates to datetime objects
    since_dt = datetime.strptime(since, "%Y-%m-%d")
    until_dt = datetime.strptime(until, "%Y-%m-%d")
    commits = repo.get_commits(since=since_dt, until=until_dt)
    messages = []
    for commit in commits:
        # Only use top-level commit messages (ignore merges from PRs if needed)
        msg = commit.commit.message.strip()
        if msg and not msg.lower().startswith('merge'):
            messages.append(msg)
    return messages

def get_release_notes(commit_messages):
    if not commit_messages:
        return "No commits found in the selected period."

    prompt = (
        "You are a professional technical writer. Given these commit messages, generate a concise, categorized release note in Markdown for end-users. "
        "Use headings like Features, Fixes, Improvements and General Updates. Ignore internal-only or trivial changes. Use clear, non-technical language.\n\n"
        "Commit messages:\n" +
        "\n".join(f"- {msg}" for msg in commit_messages)
    )

    openai.api_key = OPENAI_API_KEY
    response = openai.chat.completions.create(
        # model="gpt-4o",  # or "gpt-4o-mini" for lower cost
        model="gpt-4o-mini", # using the mini version for cost efficiency
        messages=[
            {"role": "user", "content": prompt}
        ],
        max_tokens=500
    )
    return response.choices[0].message.content.strip()

def chunk_list(lst, chunk_size):
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]

def summarize_in_chunks(commit_messages, get_release_notes_func, chunk_size=30):
    """Splits the commit messages into chunks, summarizes each chunk, and summarizes the summaries if needed."""
    summaries = []
    for chunk in chunk_list(commit_messages, chunk_size):
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

def need_chunking(commit_messages, max_commits=40, max_chars=10000):
    """Returns True if messages are too many or too long for a single LLM call."""
    if len(commit_messages) > max_commits:
        return True
    total_chars = sum(len(m) for m in commit_messages)
    if total_chars > max_chars:
        return True
    return False

if __name__ == "__main__":
    print("=== AI Release Note Generator (Phase 1, with Chunking) ===\n")

    repo = input("Enter repo full name (e.g. nvm-sh/nvm): ").strip()
    since = input("Enter start date (YYYY-MM-DD): ").strip()
    until = input("Enter end date (YYYY-MM-DD): ").strip()

    print("\nFetching commits from GitHub...")
    commit_messages = get_commits(repo, since, until)

    print(f"Found {len(commit_messages)} commits.")

    if not commit_messages:
        print("No commits found for this date range. Exiting.")
        exit(0)

    print("Sending commit messages to OpenAI for summarization...\n")

    # Automatically handle chunking if too many or too long
    if need_chunking(commit_messages):
        print("Large commit set detected. Splitting into manageable chunks for LLM processing...")
        release_notes = summarize_in_chunks(commit_messages, get_release_notes)
    else:
        release_notes = get_release_notes(commit_messages)

    print("\n--- Release Notes ---\n")
    print(release_notes)
    print("\n---------------------\n")

    # with open("RELEASE_NOTES.md", "w") as f:
    #     f.write(release_notes)
    # print("Release notes written to RELEASE_NOTES.md")
    
    # Create a unique filename based on repo name and timestamp
    repo_name_safe = repo.replace('/', '_')  # Replace '/' to avoid path issues
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"RELEASE_NOTES_{repo_name_safe}_{timestamp}.md"
    with open(filename, "w") as f:
        f.write(release_notes)
    print(f"Release notes written to {filename}")