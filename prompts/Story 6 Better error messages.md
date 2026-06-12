# Better error messages for list_repos (repo_list.py)

Presently while using `uv run list_repos` I get error messages like the following which aren't helpful for discovering the problem.  I have to then
use the debugger to find out what the issue is.
```bash
uv run list_repos https://gitlab.gcp.davita.com physician-experience --provider gitlab
Error: Expecting value: line 1 column 1 (char 0)
```

Typical problems are bad command line inputs:
- api url is incorrect
- organization is wrong
- an access token is required

These errors should be handled for both GitLab and GitHub providers.

# Acceptance Criteria
The following are examples of error messages that should be improved:
- Error: Could not connect to API URL: https://api.github.invalid
Please verify that the API URL is correct and reachable.
- Error: Could not authenticate with API URL: https://api.github.invalid
Please verify that the access token is correct and has the necessary permissions.
- Error: Could not list repositories for organization: physician-experience
Please verify that the organization name is correct and that you have access to the organization.

## Invalid or unreachable API URL is clearly reported
Given the user runs a command with an invalid, malformed, or unreachable API URL
When the application attempts to contact the API
Then the application should display a clear error message explaining that the API URL could not be reached or is invalid
And the message should include the URL that was attempted
And the message should suggest checking the API URL format.

Example:
Error: Could not connect to API URL: https://api.github.invalid
Please verify that the API URL is correct and reachable.

## Incorrect organization, group, or namespace is clearly reported
Given the user provides an organization, group, user, or namespace that does not exist
When the API returns a not found response
Then the application should display a clear error message explaining that the organization/group/namespace was not found
And the message should include the value the user entered
And the message should suggest checking the spelling or permissions.

Example:
Error: Organization or namespace not found: my-wrong-org
Please check the spelling or verify that you have access to it.

## Missing or required access token is clearly reported
Given the API requires authentication for the requested resource
When the user has not configured the required access token
Then the application should display a clear error message explaining that authentication is required
And the message should identify the expected environment variable.
example: 
Error: Authentication is required to access this resource.
Please set GITHUB_TOKEN and try again.


## Invalid or insufficient access token is clearly reported
Given the user has configured an access token
When the token is invalid, expired, or lacks permissions
Then the application should display a clear error message explaining that authentication failed
And the message should suggest checking token validity and permissions.
Example: Error: Authentication failed. The configured token may be invalid, expired, or missing required permissions.
Please verify your access token and try again.

## Error messages should not expose secrets
Given an error occurs while using an access token
When the application displays the error
Then the access token value must not be printed in the console output
And request headers or sensitive environment variable values must not be shown.

## Unexpected API responses include useful context
Given the API returns an unexpected status code or response format
When the application cannot process the response
Then the application should display the HTTP status code
And the message should explain the likely category of problem.
example: 
Error: GitHub API returned HTTP 500 while listing repositories for my-org.
Please try again later.

## Network timeout errors are understandable
Given the API request times out
When the application fails to receive a response
Then the application should display a clear timeout message
And suggest retrying or checking network connectivity.
example:
Error: Request to https://api.github.com timed out.
Please check your network connection and try again.

## Repository clone failures identify the failing repository
Given the application is scanning multiple repositories
When cloning one repository fails
Then the error message should include the repository name
And explain whether the failure appears related to access, missing repository, or network issues
And scanning should continue for remaining repositories where possible.
example:
Error: Could not clone repository my-org/private-service.
The repository may not exist, or your token may not have access.

## Errors should be actionable
Given any handled error occurs
When the error message is displayed
Then the message should include enough information for the user to understand what failed
And should include at least one suggested next step whenever possible.

## Errors should be tested
Given the improved error handling is implemented
When automated tests are run
Then there should be tests covering common failure cases, including:
invalid API URL
nonexistent organization/group
missing token when authentication is required
invalid or insufficient token
repository clone failure
malformed command-line arguments

## Existing successful behavior is unchanged
Given the user provides valid inputs and authentication
When the commands are run
Then the application should continue to list repositories and count controllers as before
And the improved error handling should not change successful output except where necessary.
