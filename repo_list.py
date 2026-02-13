import os
import sys
import requests
import argparse

def main():
    parser = argparse.ArgumentParser(
        description="List repositories for a GitHub organization.",
        usage="python repo_list.py <API_BASE_URL> <ORG> [--filter <substring>]"
    )
    parser.add_argument("API_BASE_URL", help="Base GitHub REST API URL (e.g., https://api.github.com)")
    parser.add_argument("ORG", help="Organization name (login)")
    parser.add_argument("--filter", dest="filter_substring", help="Only include repos whose name contains this substring (case-insensitive)")

    # If no arguments are provided, show usage and exit
    if len(sys.argv) == 1:
        print(f"Usage:\n  python repo_list.py <API_BASE_URL> <ORG> [--filter <substring>]\n\nRequired Arguments:\n  API_BASE_URL: Base GitHub REST API URL\n  ORG: Organization name\n\nEnvironment Variables:\n  GITHUB_TOKEN: Recommended to avoid rate limits and access private repos.")
        sys.exit(1)

    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    headers = {}
    if token:
        headers["Authorization"] = f"token {token}"
    
    # Ensure API_BASE_URL doesn't end with a slash for consistency
    api_base_url = args.API_BASE_URL.rstrip('/')
    # Try orgs first, then users if orgs fails with 404
    url = f"{api_base_url}/orgs/{args.ORG}/repos"
    
    repos = []
    params = {"per_page": 100, "page": 1}

    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 404:
            # Fallback to users endpoint
            url = f"{api_base_url}/users/{args.ORG}/repos"
            response = requests.get(url, headers=headers, params=params)

        while True:
            if response.status_code == 401 or response.status_code == 403:
                error_msg = "Error: Authentication failed or rate limit exceeded. "
                error_msg += "Check if GITHUB_TOKEN is missing, invalid, or has insufficient permissions."
                print(error_msg, file=sys.stderr)
                sys.exit(1)
            elif not response.ok:
                print(f"Error: Received HTTP {response.status_code} from {url}", file=sys.stderr)
                sys.exit(1)
            
            page_repos = response.json()
            if not page_repos:
                break
                
            repos.extend(page_repos)
            
            if "next" in response.links:
                params["page"] += 1
                response = requests.get(url, headers=headers, params=params)
            else:
                break
                
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    filter_sub = args.filter_substring.lower() if args.filter_substring else None

    for repo in repos:
        repo_name = repo.get("name", "")
        full_name = repo.get("full_name", "")
        
        if filter_sub:
            if filter_sub in repo_name.lower():
                print(full_name)
        else:
            print(full_name)

if __name__ == "__main__":
    main()
