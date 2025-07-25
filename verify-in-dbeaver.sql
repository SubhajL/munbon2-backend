-- Run this in DBeaver while connected to munbon_dev database
SELECT 'gis.canal_network' as table_name, COUNT(*) as row_count FROM gis.canal_network
UNION ALL
SELECT 'gis.control_structures', COUNT(*) FROM gis.control_structures
UNION ALL
SELECT 'gis.agricultural_plots', COUNT(*) FROM gis.agricultural_plots
UNION ALL
SELECT 'ros.kc_weekly', COUNT(*) FROM ros.kc_weekly
UNION ALL
SELECT 'auth.roles', COUNT(*) FROM auth.roles
ORDER BY table_name;

-- To see sample data:
SELECT * FROM gis.canal_network LIMIT 5;
SELECT * FROM gis.control_structures LIMIT 5;