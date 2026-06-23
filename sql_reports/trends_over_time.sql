-- Table of repositories and the number of controllers, endpoints, and feature files found in each repository.
-- Organized by scan date so that trends can be seen over time.
-- example:
-- repository                      date      controllers,endpoints,feature_files
-- coding_examples/spring-boot-app,2026-06-23,1,3,0
-- coding_examples/spring-boot-app,2026-06-19,1,3,0

SELECT
  r.name AS repository,
  strftime('%Y-%m-%d', sr.scanned_at) AS date,
  COUNT(DISTINCT c.id) AS controllers,
  COUNT(DISTINCT e.id) AS endpoints,
  COUNT(DISTINCT kff.id) AS feature_files
FROM repos r
JOIN scan_runs sr ON sr.id = r.scan_run_id
LEFT JOIN controllers c ON c.repo_id = r.id
LEFT JOIN endpoints e ON e.controller_id = c.id
LEFT JOIN karate_feature_files kff ON kff.repo_id = r.id
GROUP BY r.id, r.name, sr.scanned_at
ORDER BY r.name ASC, sr.scanned_at DESC;