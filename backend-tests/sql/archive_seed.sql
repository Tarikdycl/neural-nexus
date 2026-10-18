-- Run in NeuralNexusDB SQL Worksheet while connected as ADMIN.
-- Re-runnable seed. Existing players/sessions are untouched.
MERGE INTO NN_WORLDS w USING
 (SELECT 'american_history' id, 'American History' title FROM dual) x
 ON (w.world_id=x.id)
WHEN NOT MATCHED THEN INSERT (world_id,title,world_type,description)
VALUES (x.id,x.title,'historical','Evidence-based American history experiences');

MERGE INTO NN_SCENARIOS s USING
 (SELECT 'boston_tea_party_1773' id FROM dual) x
 ON (s.scenario_id=x.id)
WHEN NOT MATCHED THEN INSERT
 (scenario_id,world_id,title,location_name,historical_year,mode_name,duration_seconds,scenario_data)
VALUES
 (x.id,'american_history','The Tea in the Harbor','Boston Harbor',1773,'chrono_crisis',60,
 '{"date":"1773-12-16","objective":"Recover evidence and explain the causes of the Boston Tea Party","historical_mode":"educational"}');

COMMIT;

SELECT scenario_id, title FROM NN_SCENARIOS WHERE scenario_id='boston_tea_party_1773';
