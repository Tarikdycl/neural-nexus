-- Run once in the Oracle Autonomous Database SQL Worksheet as ADMIN.
-- Reuses Boston's world ID; safe to re-run without duplicates.
INSERT INTO NN_SCENARIOS (
    SCENARIO_ID, WORLD_ID, TITLE, LOCATION_NAME,
    HISTORICAL_YEAR, MODE_NAME, DURATION_SECONDS, SCENARIO_DATA
)
SELECT
    'storming_bastille_1789', WORLD_ID, 'Storming the Bastille',
    'Paris, France', 1789, MODE_NAME, 60,
    '{"location":"Paris","date":"1789-07-14","source":"curated historical scenario"}'
FROM NN_SCENARIOS
WHERE SCENARIO_ID='boston_tea_party_1773'
AND NOT EXISTS (
    SELECT 1 FROM NN_SCENARIOS
    WHERE SCENARIO_ID='storming_bastille_1789'
);

COMMIT;

SELECT SCENARIO_ID,TITLE FROM NN_SCENARIOS
WHERE SCENARIO_ID IN ('boston_tea_party_1773','storming_bastille_1789');
