import os
from github import Github
from dotenv import load_dotenv
from datetime import datetime
import requests

# Load environment variables
load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

if not GITHUB_TOKEN:
    print("Missing GITHUB_TOKEN in .env file.")
    exit(1)

def get_commits(repo_full_name, since, until):
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(repo_full_name)
    since_dt = datetime.strptime(since, "%Y-%m-%d")
    until_dt = datetime.strptime(until, "%Y-%m-%d")
    commits = repo.get_commits(since=since_dt, until=until_dt)
    messages = []
    for commit in commits:
        msg = commit.commit.message.strip()
        if msg and not msg.lower().startswith('merge'):
            messages.append(msg)
    return messages

# This function allows the user to use a locally running Ollama server which avoides the need for cloud hosted LLMs.
# In the implementation below, commit messages are sent to Ollama's gemma3:12b model for summarization but can adjust the model parameter to use different Ollama models based on your needs
def get_release_notes(commit_messages, model="gemma3:12b"):
    if not commit_messages:
        return "No commits found in the selected period."
    prompt = (
        "You are a professional technical writer. Given these commit messages, generate a concise, categorized release note in Markdown for end-users. "
        "Use headings like Features, Fixes, and Improvements. Ignore internal-only or trivial changes. Use clear, non-technical language.\n\n"
        "Commit messages:\n" +
        "\n".join(f"- {msg}" for msg in commit_messages)
    )
    # Ollama REST API call
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False
        },
        timeout=120  # Increase if your model is slow to respond
    )
    data = response.json()
    return data.get("response", "").strip()

if __name__ == "__main__":
    print("=== AI Release Note Generator (Phase 1 - Ollama gemma3:12b) ===\n")

    repo = input("Enter repo full name (e.g. nvm-sh/nvm): ").strip()
    since = input("Enter start date (YYYY-MM-DD): ").strip()
    until = input("Enter end date (YYYY-MM-DD): ").strip()

    print("\nFetching commits from GitHub...")
    commit_messages = get_commits(repo, since, until)

    print(f"Found {len(commit_messages)} commits.")

    if not commit_messages:
        print("No commits found for this date range. Exiting.")
        exit(0)

    print(f"Sending commit messages to Ollama (model: gemma3:12b) for summarization...\n")
    release_notes = get_release_notes(commit_messages)

    print("\n--- Release Notes ---\n")
    print(release_notes)
    print("\n---------------------\n")

    # Create a unique filename based on repo name and timestamp
    repo_name_safe = repo.replace('/', '_')  # Replace '/' to avoid path issues
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"RELEASE_NOTES_{repo_name_safe}_{timestamp}.md"
    with open(filename, "w") as f:
        f.write(release_notes)
    print(f"Release notes written to {filename}")