WITH latest_run AS (
  SELECT id AS scan_run_id, date(scanned_at) AS scan_date
  FROM scan_runs
  ORDER BY id DESC
  LIMIT 1
),
run_repos AS (
  SELECT r.id AS repo_id, r.name AS repo_name, lr.scan_date
  FROM repos r
  JOIN latest_run lr ON lr.scan_run_id = r.scan_run_id
)
SELECT
  rr.scan_date AS "scan date",
  rr.repo_name AS "repository name",
  c.name AS "controller name",
  cs.service_name AS "service name",
  sdm.marker AS "service dependency marker"
FROM run_repos rr
JOIN controllers c ON c.repo_id = rr.repo_id
JOIN controller_services cs ON cs.controller_id = c.id
LEFT JOIN service_dependency_markers sdm ON sdm.controller_service_id = cs.id
WHERE cs.service_name = 'UnknownService' OR sdm.marker = 'NoDependency'
ORDER BY rr.repo_name ASC, c.name ASC, cs.service_name ASC;
