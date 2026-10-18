-- Run once as ADMIN in Oracle SQL Worksheet. Idempotent, no new tables.
INSERT INTO NN_SCENARIOS (
 SCENARIO_ID, WORLD_ID, TITLE, LOCATION_NAME,
 HISTORICAL_YEAR, MODE_NAME, DURATION_SECONDS, SCENARIO_DATA
)
SELECT 'berlin_wall_1989', WORLD_ID, 'The Wall Opens',
       'Berlin, Germany', 1989, MODE_NAME, 60,
       '{"location":"East Berlin","date":"1989-11-09","checkpoint":"Bornholmer Strasse"}'
FROM NN_SCENARIOS
WHERE SCENARIO_ID='boston_tea_party_1773'
  AND NOT EXISTS (SELECT 1 FROM NN_SCENARIOS WHERE SCENARIO_ID='berlin_wall_1989');
COMMIT;
SELECT SCENARIO_ID,TITLE FROM NN_SCENARIOS WHERE SCENARIO_ID='berlin_wall_1989';
