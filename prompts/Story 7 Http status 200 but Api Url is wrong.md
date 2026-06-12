# HTTP status 200 but API URL is wrong

This story applies to both GitHub and GitLab.
When `list_repos` receives HTTP 200 from an API URL, it should still validate that the response looks like a real provider API response before attempting to parse/list repositories.

1. Check the Content-Type Header
This is the fastest indicator.
- Expected: application/json (for APIs).

2. Inspect the Response Body
  A Generic Success Messages
- What to look for:
  - {"status": "ok"}
  - {"message": "Welcome"}
  - {"data": null}
  - Empty object {} or empty array [] (if the API usually returns data).
- Meaning: The server accepted the request but has no specific data to return, or it’s a fallback response.

 B Error Messages in JSON
- What to look for:
  - {"error": "Not Found"}
  - {"message": "Route not found"}
  - {"code": 404, "message": "..."} (even if the HTTP status is 200).
- Meaning: The server is handling errors internally and returning them in the body.

 C Redirect-like Content
- What to look for: HTML with <meta http-equiv="refresh" ...> or JavaScript with window.location.
- Meaning: The server is trying to redirect you, but it’s doing it via content instead of HTTP headers.

3. Check for Custom Headers
Some servers add headers to indicate fallback behavior:
- X-Catch-All: true
- X-Route: fallback
- X-Powered-By: Express (might indicate a generic Express error handler).

4. Check for Specific Keywords
Search the response body for:
- "404"
- "Not Found"
- "Page Not Found"
- "Route not found"
- "Welcome"
- "Index"
- "SPA"
- "React" or "Vue" (if you see framework-specific tags).

Example Detection Logic (Pseudocode):
def is_non_existent_endpoint(response):
    # Check Content-Type
    if 'text/html' in response.headers.get('Content-Type', ''):
        return True
    
    # Check Body for HTML
    if '<html' in response.text.lower():
        return True
    
    # Check Body for Generic Messages
    if response.json().get('status') == 'ok' and response.json().get('data') is None:
        return True
    
    # Check Body for Error Keywords
    error_keywords = ['not found', 'route not found', '404']
    if any(keyword in response.text.lower() for keyword in error_keywords):
        return True
    
    return False

# When to check
- this check should happen with the first API call to a provider.
- before parsing the response body.

## Tests

Add automated tests for:

- HTTP 200 with `Content-Type: text/html`.
- HTTP 200 with an HTML body.
- HTTP 200 with invalid JSON.
- HTTP 200 with a valid empty JSON array.
- HTTP 200 with a valid GitLab repository response.

# Acceptance Criteria
The following should detect a non-existent endpoint despite a 200 status:
`uv run list_repos https://gitla.com/api/v4 gnome --provider gitlab`
Should result in:
```bash
Error: API_BASE_URL does not appear to be a valid GitLab API endpoint: https://gitla.com/api/v4
The server returned HTTP 200, but the response did not look like a GitLab API response.
Please verify that the API URL is correct.
```