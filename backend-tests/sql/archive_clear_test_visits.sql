-- ONE-TIME DESTRUCTIVE RESET, MANUAL ADMIN ACTION ONLY.
-- Removes ALL saved game sessions and event history for the three Archive scenarios.
-- Keeps NN_SCENARIOS and NN_WORLDS; does not touch other games.
-- BACK UP NN_SESSIONS and NN_EVENTS before using this script if you need the history.
-- Run in SQL Worksheet as ADMIN only when you deliberately want to erase all prior runs.
--
-- Preview BEFORE executing the delete section:
SELECT SCENARIO_ID, COUNT(*) AS VISITS_TO_REMOVE
FROM ADMIN.NN_SESSIONS
WHERE SCENARIO_ID IN (
  'boston_tea_party_1773',
  'storming_bastille_1789',
  'berlin_wall_1989'
)
GROUP BY SCENARIO_ID;

-- DELETE SECTION: intentionally commented out to avoid accidental erasure.
-- Remove the leading "-- " from each statement below only when ready.
-- DELETE FROM ADMIN.NN_EVENTS
-- WHERE SESSION_ID IN (
--   SELECT SESSION_ID FROM ADMIN.NN_SESSIONS
--   WHERE SCENARIO_ID IN (
--     'boston_tea_party_1773',
--     'storming_bastille_1789',
--     'berlin_wall_1989'
--   )
-- );
--
-- DELETE FROM ADMIN.NN_SESSIONS
-- WHERE SCENARIO_ID IN (
--   'boston_tea_party_1773',
--   'storming_bastille_1789',
--   'berlin_wall_1989'
-- );
--
-- COMMIT;
--
-- Verify with the preview SELECT above; it should return no rows.
