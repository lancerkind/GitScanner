WITH latest_scan AS (
    SELECT id
    FROM scan_runs
    ORDER BY scanned_at DESC, id DESC
    LIMIT 1
)
SELECT DISTINCT
    r.name AS repo,
    c.name AS controller,
    dc.dependency_type AS dependency
FROM repos r
JOIN latest_scan ls ON r.scan_run_id = ls.id
JOIN controllers c ON c.repo_id = r.id
JOIN controller_services cs ON cs.controller_id = c.id
JOIN service_dependency_markers sdm ON sdm.controller_service_id = cs.id
JOIN dependency_classifications dc ON dc.marker = sdm.marker
ORDER BY r.name, c.name, dc.dependency_type;