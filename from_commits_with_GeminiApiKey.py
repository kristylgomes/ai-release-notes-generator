import os
from github import Github
from dotenv import load_dotenv
import google.generativeai as genai
from datetime import datetime

# Load environment variables
load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GITHUB_TOKEN:
    print("Missing GITHUB_TOKEN in .env file.")
    exit(1)
if not GEMINI_API_KEY:
    print("Missing GEMINI_API_KEY in .env file.")
    exit(1)

genai.configure(api_key=GEMINI_API_KEY)

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

def get_release_notes(commit_messages):
    if not commit_messages:
        return "No commits found in the selected period."

    prompt = (
        "You are a professional technical writer. Given these commit messages, generate a concise, categorized release note in Markdown for end-users. "
        "Use headings like Features, Fixes, and Improvements. Ignore internal-only or trivial changes. Use clear, non-technical language.\n\n"
        "Commit messages:\n" +
        "\n".join(f"- {msg}" for msg in commit_messages)
    )

    # Use Gemini 1.5 Flash (cheap/fast) or 1.5 Pro (higher quality)
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content(prompt)
    return response.text.strip()

if __name__ == "__main__":
    print("=== AI Release Note Generator (Phase 1 - Gemini Version) ===\n")

    repo = input("Enter repo full name (e.g. nvm-sh/nvm): ").strip()
    since = input("Enter start date (YYYY-MM-DD): ").strip()
    until = input("Enter end date (YYYY-MM-DD): ").strip()

    print("\nFetching commits from GitHub...")
    commit_messages = get_commits(repo, since, until)

    print(f"Found {len(commit_messages)} commits.")

    if not commit_messages:
        print("No commits found for this date range. Exiting.")
        exit(0)

    print("Sending commit messages to Gemini for summarization...\n")
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