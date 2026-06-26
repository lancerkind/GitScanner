# Story 17: Kafka Discovery for Spring Cloud Stream

## Title
Detect Spring Cloud Stream Kafka Dependencies in Spring Boot Applications

---

## Scope

This story covers **Spring Cloud Stream only** — where Kafka is configured declaratively
in YAML and wired via functional beans (`Consumer`, `Function`, `Supplier`).

Other patterns (`@KafkaListener`, `KafkaTemplate`) are out of scope and will be addressed
in future stories. The design here is intentionally extensible to accommodate them.

---

## Background

The scanner already identifies controllers, services, and datasources and marks service
dependencies via `service_dependency_markers`. This story extends that pipeline to detect
the Spring Cloud Stream pattern, where business code contains **no Kafka-specific imports**
and Kafka is entirely configured in YAML:

```yaml
spring:
  cloud:
    stream:
      kafka:
        binder:
          brokers: ${broker}
      bindings:
        subscriptionInput-in-0:
          destination: ${subscriptionTopic}
          group: my-springboot-app
```

```java
@Bean
public Consumer<SubscriptionEvent> subscriptionInput(CopsBundledEventsListener listener) {
    return listener::handle;
}
```

---

## User Story

As an architect or application analyst,
I want the scanner to detect Spring Cloud Stream Kafka bindings and mark dependent services,
So that I can identify Kafka-driven integration points alongside existing HTTP dependencies.

---

## Acceptance Criteria

### AC1: Detect Spring Cloud Stream Configuration

**Given** a YAML file (`application.yml`, `application.yaml`, `bootstrap.yml`, `bootstrap.yaml`)
containing either:

- `spring.cloud.stream.kafka`
- `spring.cloud.stream.bindings`

**Then** the scanner shall write one row to `repo_datasources`:

| column      | value                                                                              |
|-------------|------------------------------------------------------------------------------------|
| `repo_id`   | current repo                                                                       |
| `source_file` | path to the YAML file (e.g. `src/main/resources/application.yml`)               |
| `url`       | broker URL from `spring.cloud.stream.kafka.binder.brokers`, else `kafka://stream-binder` |

**No duplicate rows** — if a row for this `repo_id` + `source_file` already exists, skip.

---

### AC2: Extract Bindings into `repo_kafka_bindings`

**Given** a repo with a detected Spring Cloud Stream configuration,

**Then** the scanner shall parse all keys under `spring.cloud.stream.bindings` and insert
rows into a new `repo_kafka_bindings` table.

#### New Table

```sql
CREATE TABLE IF NOT EXISTS repo_kafka_bindings (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id       INTEGER NOT NULL REFERENCES repos(id),
    binding_name  TEXT    NOT NULL,
    direction     TEXT    NOT NULL CHECK(direction IN ('input', 'output')),
    bean_name     TEXT    NULL
);
```

#### Parsing Rules

| YAML binding key            | `binding_name`      | `direction` |
|-----------------------------|---------------------|-------------|
| `subscriptionInput-in-0`    | `subscriptionInput` | `input`     |
| `orderOutput-out-0`         | `orderOutput`       | `output`    |
| `processor-in-0`            | `processor`         | `input`     |
| `processor-out-0`           | `processor`         | `output`    |

The suffix `-in-N` maps to `input`; `-out-N` maps to `output`.
The index `N` is ignored (multi-binding support is not in scope).

---

### AC3: Match Functional Beans to Bindings

**Given** bindings stored in `repo_kafka_bindings`,

**Then** the scanner shall scan all `.java` files for `@Bean` methods that:

- return `Consumer<T>`, `Function<T, R>`, or `Supplier<T>`
- whose **method name** matches a `binding_name` in `repo_kafka_bindings` for this repo

**When matched**, update `repo_kafka_bindings.bean_name` with the method name.

#### Example

```java
@Bean
public Consumer<SubscriptionEvent> subscriptionInput(CopsBundledEventsListener listener) {
    return listener::handle;
}
```

Updates `repo_kafka_bindings` where `binding_name = 'subscriptionInput'`:

| id | repo_id | binding_name        | direction | bean_name           |
|----|---------|---------------------|-----------|---------------------|
| 1  | 5       | subscriptionInput   | input     | subscriptionInput   |

---

### AC4: Mark Services as Kafka-Dependent

**Given** a functional bean matched to a binding (i.e., `bean_name` is populated),

**Then** the scanner shall inspect that `@Bean` method's **parameters** to identify injected
service class names.

For each injected service name that exists as a `service_name` in `controller_services`
for this repo, the scanner shall insert a marker:

```sql
INSERT INTO service_dependency_markers (controller_service_id, marker)
VALUES (<id>, 'kafka');
```

Do not insert duplicates if the marker already exists for that `controller_service_id`.

#### Example

```java
@Bean
public Consumer<SubscriptionEvent> subscriptionInput(CopsBundledEventsListener listener) {
    return listener::handle;
}
```

If `CopsBundledEventsListener` exists in `controller_services` for this repo,
it receives `marker = 'kafka'` in `service_dependency_markers`.

> **Note:** Only services that appear in `controller_services` can receive a marker,
> since `service_dependency_markers` requires a `controller_service_id` foreign key.
> Services exclusive to the Kafka path (not referenced by any controller) are visible
> in `repo_kafka_bindings` and are candidates for a future schema extension.

---

### AC5: Register Kafka Classification

**Given** the scanner adds `kafka` markers for Spring Cloud Stream services,

**Then** `get_default_classifications()` shall include:

```python
("kafka", "Kafka"),
```

This ensures the reporting layer classifies Spring Cloud Stream markers alongside
future Kafka patterns without any additional schema changes.

---

## Schema Impact Summary

| Change                        | Details                                                      |
|-------------------------------|--------------------------------------------------------------|
| **New table**                 | `repo_kafka_bindings`                                        |
| **New classification row**    | `("kafka", "Kafka")` in `dependency_classifications`         |
| **Existing table** (reused)   | `repo_datasources` — kafka source file + broker URL          |
| **Existing table** (reused)   | `service_dependency_markers` — marker = `kafka`              |
| **No other tables modified**  |                                                              |

---

## Extensibility Notes

Future stories adding new Kafka patterns can extend this foundation cleanly:

| Future Pattern           | Extension Point                                                  |
|--------------------------|------------------------------------------------------------------|
| `@KafkaListener`         | New detection module; populates `repo_kafka_bindings` with `direction = 'input'` |
| `KafkaTemplate` producer | New detection module; populates `repo_kafka_bindings` with `direction = 'output'` |
| New classification       | Add row to `dependency_classifications` — no schema change needed |
| Kafka-only services      | Add nullable `repo_kafka_binding_id` FK to `service_dependency_markers`, or a new join table |

The `repo_kafka_bindings` table and `dependency_classifications` pattern are deliberately
designed to absorb these additions without breaking existing functionality.

---

## Definition of Done

- [ ] Scanner detects `spring.cloud.stream.bindings` in YAML and writes to `repo_datasources`
- [ ] Scanner extracts binding names and directions into `repo_kafka_bindings`
- [ ] Scanner matches `@Bean Consumer<T>` / `Function<T,R>` / `Supplier<T>` method names to bindings and updates `bean_name`
- [ ] Services injected into matched beans receive `kafka` marker in `service_dependency_markers` (where they appear in `controller_services`)
- [ ] `dependency_classifications` includes `("kafka", "Kafka")`
- [ ] No duplicate rows inserted into any table on re-scan
- [ ] All existing scanner behavior is unchanged
- [ ] `repo_kafka_bindings` table is created in the migration without breaking existing schema