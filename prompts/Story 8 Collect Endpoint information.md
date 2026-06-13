# Story 8: Collect Controller Endpoint information
As a transformation leader,
I want a list of all the endpoints paths 
so that I can understand the API surface area of the application.

SpringBoot controllers handle requests.  Those requests are mapped to a method to service the call. Methods are 
annotated with HTTP methods such as `@GetMapping`,`@PostMapping`, etc. These methods define the endpoints and their 
corresponding HTTP methods. I want to scan and store the endpoints paths and HTTP methods in the database.  
The schema used by count_spring_controllers needs to be changed to support this.

Keep the summary report sparse as details can be mined from the database.  

# Request Mappings
Request Mapping Annotations are Applied to methods to define the route and HTTP method: 
@GetMapping("/path") GET 
@PostMapping("/path") POST
@PutMapping("/path") PUT
@DeleteMapping("/path") DELETE
@PatchMapping("/path") PATCH
@RequestMapping("/path") Any (specified in 'method=' attribute parameter)

# Schema additions

CREATE TABLE controllers (
    id          INTEGER PRIMARY KEY,
    repo_id     INTEGER REFERENCES repos(id),
    name        TEXT,      -- "CatController"
    base_path   TEXT,      -- "/api/cats"
    type        TEXT       -- "RestController" or "Controller"
);

Add the following table:
CREATE TABLE endpoints (
    id             INTEGER PRIMARY KEY,
    controller_id  INTEGER REFERENCES controllers(id),
    http_method    TEXT,   -- "GET", "POST", etc.
    path           TEXT    -- "/cats/{id}" 
);


# Details
- keep the code in module count_spring_controllers maintainable. Refactor code into seperate modules if necessary.
- keep the code in module count_spring_controllers testable.  Add automated tests for the schema additions and new functions.
- update the report summary to report on the number of endpoints at the end of the report.
- controllers.base_path should be the base path argument used in the Mapping annotation: @RequestMapping("/api/cats")
 or @RequestMapping(path = "/api/cats") or @RequestMapping(value = "/api/cats")
- endpoints.path should be the path argument used in the Mapping annotation. For example: @*Mapping("/path"), @GetMapping("/{id}"), @GetMapping(value = "/{id}"), @GetMapping(path = "/{id}")
,  @RequestMapping(value = "/x", method = RequestMethod.GET), @RequestMapping(path = "/x", method = RequestMethod.POST)
- Regarding endpoints.http_method, if the a request mapping is for ANY, then store "ANY" as the http_method.
- For Controller methods that have multiple request mappings, create one endpoint row for each path/method combination.
- The existing schema can be adjusted if need be (controllers table). We don't need to maintain schema rigidity.  The reporting funcionality will need 
to be updated to accomodate schema changes.
- when scanning a repo:
  - each detected controller is inserted into controllers
  - each detected endpoint for that controller is inserted into endpoints
  - endpoints.controller_id references the inserted controller row
 
# Acceptance Criteria
- The schema additions should be tested with automated tests.
- The new functions should be tested with automated tests.
- The code should be maintainable.
- The code should be testable.
- The code should have at least 80% code coverage.
- The code should not break existing functionality.
- The tests should pass.
