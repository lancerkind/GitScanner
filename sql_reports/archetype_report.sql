WITH
  latest_run AS (
    SELECT id AS scan_run_id
    FROM scan_runs
    ORDER BY id DESC
    LIMIT 1
  ),
  run_repos AS (
    SELECT r.id AS repo_id, r.name AS repo_name
    FROM repos r
    JOIN latest_run lr ON lr.scan_run_id = r.scan_run_id
  ),
  repo_marker_types AS (
    SELECT rr.repo_id, dc.dependency_type
    FROM run_repos rr
    JOIN controllers c ON c.repo_id = rr.repo_id
    JOIN controller_services cs ON cs.controller_id = c.id
    JOIN service_dependency_markers sdm ON sdm.controller_service_id = cs.id
    JOIN dependency_classifications dc ON dc.marker = sdm.marker
  ),
  repo_datasource_types AS (
    SELECT rr.repo_id, dc.dependency_type
    FROM run_repos rr
    JOIN repo_datasources rd ON rd.repo_id = rr.repo_id
    JOIN dependency_classifications dc ON lower(rd.url) LIKE '%' || lower(dc.marker) || '%'
  ),
  repo_all_types AS (
    SELECT repo_id, dependency_type FROM repo_marker_types
    UNION
    SELECT repo_id, dependency_type FROM repo_datasource_types
  ),
  repo_type_list AS (
    SELECT
      repo_id,
      group_concat(dependency_type, ', ') AS dependency_types
    FROM (
      SELECT DISTINCT repo_id, dependency_type
      FROM repo_all_types
      ORDER BY dependency_type
    )
    GROUP BY repo_id
  ),
  repo_type_flags AS (
    SELECT
      rr.repo_id,
      COALESCE(SUM(CASE WHEN rat.dependency_type IS NOT NULL THEN 1 ELSE 0 END), 0) AS resolved_type_count,
      COALESCE(SUM(CASE WHEN rat.dependency_type IS NOT NULL AND rat.dependency_type <> 'H2' THEN 1 ELSE 0 END), 0) AS resolved_non_h2_type_count,
      COUNT(DISTINCT CASE WHEN rat.dependency_type <> 'H2' THEN rat.dependency_type END) AS distinct_non_h2_type_count,
      MAX(CASE WHEN rat.dependency_type = 'Kafka' THEN 1 ELSE 0 END) AS has_kafka,
      MAX(CASE WHEN rat.dependency_type = 'Oracle' THEN 1 ELSE 0 END) AS has_oracle,
      MAX(CASE WHEN rat.dependency_type = 'Spanner' THEN 1 ELSE 0 END) AS has_spanner,
      MAX(CASE WHEN rat.dependency_type = 'PostgreSQL' THEN 1 ELSE 0 END) AS has_postgresql,
      MAX(CASE WHEN rat.dependency_type IN ('SQL Database', 'CloudSQL', 'SQL Server') THEN 1 ELSE 0 END) AS has_other_sql,
      MAX(CASE WHEN rat.dependency_type = 'API' THEN 1 ELSE 0 END) AS has_api,
      COALESCE(COUNT(DISTINCT cs.id), 0) AS service_count
    FROM run_repos rr
    LEFT JOIN repo_all_types rat ON rat.repo_id = rr.repo_id
    LEFT JOIN controllers c ON c.repo_id = rr.repo_id
    LEFT JOIN controller_services cs ON cs.controller_id = c.id
    GROUP BY rr.repo_id
  ),
  repo_counts AS (
    SELECT
      rr.repo_id,
      COUNT(DISTINCT c.id) AS controller_count,
      COUNT(e.id) AS endpoint_count
    FROM run_repos rr
    LEFT JOIN controllers c ON c.repo_id = rr.repo_id
    LEFT JOIN endpoints e ON e.controller_id = c.id
    GROUP BY rr.repo_id
  )
SELECT
  rr.repo_name,
  CASE
    WHEN rtf.distinct_non_h2_type_count >= 3 THEN 'MIXED'
    WHEN rtf.has_kafka = 1 THEN 'KAFKA'
    WHEN rtf.has_oracle = 1 THEN 'ORACLE'
    WHEN rtf.has_spanner = 1 THEN 'SPANNER'
    WHEN rtf.has_postgresql = 1 THEN 'POSTGRES'
    WHEN rtf.has_other_sql = 1 THEN 'OTHER_SQL'
    WHEN rtf.has_api = 1 THEN 'UPSTREAM_REST_API'
    WHEN rtf.resolved_non_h2_type_count = 0 AND rtf.service_count = 0 THEN 'NO_DEPENDENCIES_DETECTED'
    ELSE 'UNCLASSIFIED'
  END AS archetype,
  COALESCE(rtl.dependency_types, '') AS dependency_types,
  COALESCE(rc.controller_count, 0) AS controller_count,
  COALESCE(rc.endpoint_count, 0) AS endpoint_count
FROM run_repos rr
LEFT JOIN repo_type_flags rtf ON rtf.repo_id = rr.repo_id
LEFT JOIN repo_type_list rtl ON rtl.repo_id = rr.repo_id
LEFT JOIN repo_counts rc ON rc.repo_id = rr.repo_id
ORDER BY archetype ASC, rr.repo_name ASC;