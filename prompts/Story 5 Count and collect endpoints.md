# Count and collect endpoint information

I'm describing changes I want made to count_spring_controllers.py

In SpringBoot, there are Controllers (@Controller) and each controller has a base path defined by @RequestMapping or 
@GetMapping or @PostMapping.
Within each controller, endpoints are declared with annotations named as @*Mapping, where 
the * can be @GetMapping, @PostMapping, @PutMapping, @DeleteMapping, @PatchMapping, @RequestMapping.

# Reporting
This scanner finds all the controllers.  Now we will find all the endpoints and adjust the report so it looks like:
```text
======================================================================
SUMMARY
======================================================================

Repositories with controllers: 2/2

Total @RestController files: 2
Total @Controller files: 0
Total Controller files: 2

----------------------------------------------------------------------
Breakdown by repository:
----------------------------------------------------------------------
coding_examples/spring-boot-app                      1 controllers  8 endpoints 
gitlab-ci-examples1/gitlab-runner-spring-boot-demo   1 controllers  1 endpoints 
```

If I pass in `--verbose`
```text
======================================================================
SUMMARY
======================================================================

Repositories with controllers: 2/2

Total @RestController files: 2
Total @Controller files: 0
Total Controller files: 2

----------------------------------------------------------------------
Breakdown by repository:
----------------------------------------------------------------------
coding_examples/spring-boot-app                        
  CatController "/api/cats"
    Get "/"
    Post "/"
    Delete "/{id}"
    Put "/{id}"
    
  BillingController "/billing"
    Get "/invoice"
    Get "/invoice/{invoice_number}"
```
# Edge cases
- if the controller doesn't have a @RequestMapping, use "/" 
- for cases where a Controller method has @RequestMapping, use the method attribute to get the HTTP verb.  If the method
attribute is absent, then use ANY for the HTTP verb.

# Design
Keep scanning code decoupled from reporting.  During the scanning, use data classes to information for reporting.
Use this model:
```python
@dataclass
class Endpoint:
    method: str      # GET, POST, etc.
    path: str        # "/cats/{id}"

@dataclass
class Controller:
    name: str
    base_path: str
    endpoints: list[Endpoint] = field(default_factory=list)

@dataclass
class RepoResult:
    repo_name: str
    controllers: list[Controller] = field(default_factory=list)
```

This dictionary should contain each repo scanned.  And for each repo, store in the dictionary the characteristics which 
are being used in reporting: Controller name, mapping, and endpoint information (<method>, <path>).