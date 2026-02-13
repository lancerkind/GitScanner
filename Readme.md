# SpringBoot Controller Counter

Two approaches to count SpringBoot controllers across GitHub repositories using a file list:

## Option 1: GitHub Code Search API (Recommended)
**File:** `count_spring_controllers.py`

✅ Fast - no cloning needed
✅ Works well for public repos
⚠️ Rate limited (10 searches/minute)
⚠️ May miss some results in very large repos

## Option 2: Clone and Search
**File:** `count_spring_controllers_clone.py`

✅ More accurate
✅ Works with private repos
⚠️ Slower - clones each repo
⚠️ Requires disk space

## Setup

1. **Install dependencies:**
```bash
pip install requests
```

2. **Create a GitHub Personal Access Token:**
   - Go to: https://github.com/settings/tokens
   - Generate new token (classic)
   - Select scopes:
     - `repo` (for private repos)
     - `read:org` (to list organization repos)
   - Copy the token

3. **Configure the script:**
   Edit the script and replace:
   - `GITHUB_TOKEN = "your_github_token_here"` with your token

4. **Create a repos list file:**
   Create a text file (e.g., `repos.txt`) with one repository per line:
   ```
   # Comments are allowed
   mycompany/user-service
   mycompany/payment-service
   mycompany/order-service
   
   # You can organize with blank lines
   mycompany/inventory-service
   ```
   
   See `repos.txt` for an example template.

## Usage

```bash
# Option 1: API search (faster)
python count_spring_controllers.py repos.txt

# Option 2: Clone and search (more accurate)
python count_spring_controllers_clone.py repos.txt
```

## What it counts

- **@RestController** - REST API controllers
- **@Controller** - Traditional MVC controllers
- Avoids double-counting files with both annotations

## Output Example

```
Loaded 15 repositories from repos.txt

Searching 15 repositories for SpringBoot controllers...

[1/15] Searching mycompany/user-service...
  ✓ Found 8 controllers (@RestController: 6, @Controller: 2)
[2/15] Searching mycompany/payment-service...
  ✓ Found 12 controllers (@RestController: 12, @Controller: 0)
[3/15] Searching mycompany/order-service...
  - No controllers found
...

======================================================================
SUMMARY
======================================================================

Repositories with controllers: 12/15

Total @RestController: 134
Total @Controller: 23
Total Controllers: 157

----------------------------------------------------------------------
Breakdown by repository:
----------------------------------------------------------------------
mycompany/order-service                            34 controllers
mycompany/payment-service                          12 controllers
mycompany/user-service                              8 controllers
...
```

## Managing Your Repository List

**Add comments for organization:**
```
# User Services
mycompany/user-service
mycompany/auth-service

# Payment Services  
mycompany/payment-service
```

**Temporarily exclude a repo:**
```
# mycompany/legacy-service  # Comment out to skip
mycompany/new-service
```

**Scan repos from multiple organizations:**
```
mycompany/service-a
othercompany/service-b
personal-account/project-c
```

## Troubleshooting

**Rate limit errors:**
- The script automatically waits when rate limited
- For many repos, Option 2 (cloning) may be faster

**Authentication errors:**
- Verify your token has correct permissions
- For private repos, ensure `repo` scope is enabled

**No results found:**
- Check that repos contain Java/SpringBoot code
- Verify annotation format (some projects use fully qualified names)