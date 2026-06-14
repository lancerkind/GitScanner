# Add Endpoint Parameter Collection to Spring Boot Scanner

## Context
This builds on an existing scanner (`count_spring_controllers.py`) that already scans GitLab repositories and stores
discovered Spring Boot controllers and endpoints in a SQLite database (`scanner.db`). We are extending it to also
collect parameter information for each endpoint.

## User Story
As an API initiative analyst, I want the scanner to collect the parameter names, types, and sources for each scanned
endpoint, so that I can understand what data each API requires and use this information to assess Karate test
coverage in the future.

---

## Database Changes

Add the following table to the existing schema initialization:

```sql
CREATE TABLE IF NOT EXISTS parameters (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    endpoint_id   INTEGER NOT NULL REFERENCES endpoints(id),
    name          TEXT NOT NULL,
    java_type     TEXT NOT NULL,
    source        TEXT NOT NULL,
    required      BOOLEAN NOT NULL
);
```

### Source Values
The `source` column must be one of these exact strings:

| Value | Spring Annotation |
|---|---|
| `PATH` | `@PathVariable` |
| `QUERY` | `@RequestParam` |
| `HEADER` | `@RequestHeader` |
| `BODY` | `@RequestBody` |
| `COOKIE` | `@CookieValue` |

### Required Rules

| Source | Default if not specified |
|---|---|
| `PATH` | Always `true` |
| `QUERY` | `false` unless `required=true` is explicit |
| `HEADER` | `false` unless `required=true` is explicit |
| `BODY` | `true` |
| `COOKIE` | `false` unless `required=true` is explicit |

---

## Scanning Logic

### What to Parse
For each endpoint method already being scanned, parse its parameter list. Each parameter in the method signature may have one of the following annotations:

- `@PathVariable`
- `@RequestParam`
- `@RequestHeader`
- `@RequestBody`
- `@CookieValue`

Parameters without any of these annotations (e.g. `HttpServletRequest`, `Model`) should be **silently skipped** — do not store them.

### Annotation Parsing Rules

**Simple form — name inferred from the Java parameter name:**
```java
@PathVariable Long id
@RequestBody OrderRequest body
```

**Explicit value attribute — use this as the name:**
```java
@RequestParam(value="status") String status
@RequestParam("status") String status   // shorthand
```

**With required and defaultValue attributes — extract required:**
```java
@RequestParam(value="status", required=false, defaultValue="active") String status
```

**Type extraction:**
- Use the Java type as written in the source — `Long`, `String`, `OrderRequest`, `List<String>`
- Do not resolve or simplify generic types — store `List<String>` as-is

### Example

Given this Java method:
```java
@GetMapping("/orders/{id}")
public Order getOrder(
    @PathVariable                                        Long       id,
    @RequestParam(value="status", required=false)        String     status,
    @RequestHeader("Authorization")                      String     authorization,
    @RequestBody                                         OrderRequest body
)
```

The scanner should insert these rows into `parameters`:

| endpoint_id | name | java_type | source | required |
|---|---|---|---|---|
| (id of this endpoint) | `id` | `Long` | `PATH` | `true` |
| (id of this endpoint) | `status` | `String` | `QUERY` | `false` |
| (id of this endpoint) | `authorization` | `String` | `HEADER` | `false` |
| (id of this endpoint) | `body` | `OrderRequest` | `BODY` | `true` |

---

## Report Changes

### Default Report (no flags)
No change to the existing default output. Parameter data is stored but not shown.

### Verbose Report (`--verbose`)
Extend the existing verbose endpoint output to show parameters beneath each endpoint:

```text
  CatController
    GET    /cats
    POST   /cats
      BODY    CreateCatRequest  cat          required
    DELETE /cats/{id}
      PATH    Long              id           required
    PUT    /cats/{id}
      PATH    Long              id           required
      BODY    UpdateCatRequest  cat          required

  OrderController
    GET    /orders/{id}
      PATH    Long              id           required
      QUERY   String            status       optional
      HEADER  String            authorization optional
      BODY    OrderRequest      body         required
```

---

## Edge Cases the Scanner Must Handle

1. **No parameters** — endpoint has no annotated parameters; insert nothing, do not error
2. **`@RequestParam` shorthand** — `@RequestParam("status")` is equivalent to `@RequestParam(value="status")`
3. **Unannotated parameters** — skip silently (e.g. `HttpServletRequest request`)
4. **Generic types** — store as-is: `List<String>`, `Map<String, Object>`
5. **Multi-line method signatures** — parameter list may span multiple lines; the parser must handle this
6. **Existing data** — on re-scan, existing `parameters` rows for re-scanned endpoints should be deleted and re-inserted, consistent with how the scanner handles controllers and endpoints today

---

## Acceptance Criteria

- [ ] `parameters` table is created on startup if it does not exist
- [ ] All 5 annotation types are recognized and mapped to the correct `source` value
- [ ] `required` defaults are applied correctly per source type without explicit attribute
- [ ] Explicit `required=true/false` on `@RequestParam`, `@RequestHeader`, `@CookieValue` overrides the default
- [ ] Unannotated parameters are skipped without error
- [ ] Verbose report shows parameters under each endpoint with correct formatting
- [ ] Default report output is unchanged
- [ ] Re-scanning a repo replaces existing parameter data cleanly
