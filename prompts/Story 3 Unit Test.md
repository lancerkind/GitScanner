# Add unit tests for the code in repo_list.py

In preparation for a future refactoring to supporting GitLab in addition to GitHub, it is crucial to ensure that existing functionality remains intact and that new features are thoroughly tested. 
This will help maintain the reliability and stability of the repository listing functionality across different platforms.

# Refactor the code in repo_list.py to make it unit testable.
- CLI parsing should be separated from the main function so its functionality can be easily tested.
- elements specific to GitHub should be seperated from the main function.
- refactor main into other classes or functions as necessary to support unit tests and modularity.

# Create unit tests for the refactored code in repo_list.py
- use pytest to create unit tests for the refactored code.
- test the CLI parsing functionality separately from the main function.
- test the GitHub specific functionality separately from the main function.
- ensure that the refactored code can be easily extended to support GitLab in the future.

# Acceptance criteria
- the code be executable
  - For repo_list.py: uv run list_repos <API_BASE_URL> <ORG> [--filter <substring>], python repo_list.py http://api.github.com anthropics 
  - For count_spring_controllers.py: uv run count_spring_controllers <API_BASE_URL> <ORG> [--filter <substring>], python count_spring_controllers.py repos.txt
- the unit tests should pass
- the code coverage should be at least 80%