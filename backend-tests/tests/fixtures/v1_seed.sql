-- GENERATED FILE - do not edit by hand.
-- Edit content/story.json, then run: python scripts/build_seed.py
-- Load order (design doc section 8): variants -> realms -> pearls ->
-- pearl_signs -> duel_rounds -> hints. Safe to run more than once.

INSERT INTO variants (variant_id, culprit, culprit_words, ending_text) VALUES
  ('V1', 'Sun Wukong', 'wukong,monkey king', 'Wukong laughs and bows. "You caught me, little Seeker! I only wanted one more peach festival." He gives back the hours, and the hourglass is whole again. As a gift, he teaches the Seeker one of his 72 changes.'),
  ('V2', 'Jade Rabbit', 'jade rabbit,rabbit', 'The Jade Rabbit steps out, ears down. "I only wanted the Moon Festival to last." Wukong grins. "I hid her tracks to test you. You did not blame the obvious monkey!" The Rabbit returns the hours, and the village plans a festival together.'),
  ('V3', 'Dragon King', 'dragon king,dragon', 'The Dragon King rises from the sea, dripping. "My sea was thirsty." Wukong says, "I shook my own mountain to warn the village, and everyone blamed me. You looked at the evidence." The Dragon returns the hours, and the rain falls only in its season.')
AS new ON DUPLICATE KEY UPDATE culprit = new.culprit, culprit_words = new.culprit_words, ending_text = new.ending_text;

INSERT INTO realms (realm_id, name, display_order, image_url, look_text, listen_text) VALUES
  ('bamboo', 'Bamboo Forest', 1, '/static/img/bamboo.svg', 'The bamboo shadows are very long.', 'Wind chimes ring at the shrine.'),
  ('sea', 'East Sea Shore', 2, '/static/img/sea.svg', 'A dark wet line on the big stones shows how high the water can climb.', 'Waves whisper far away, then crash closer and closer.'),
  ('moon', 'Moon Palace Stairs', 3, '/static/img/moon.svg', 'Silver light falls on a long stone staircase that climbs into the sky.', 'Soft bells ring from the palace at the top of the stairs.')
AS new ON DUPLICATE KEY UPDATE name = new.name, display_order = new.display_order, image_url = new.image_url, look_text = new.look_text, listen_text = new.listen_text;

INSERT INTO pearls (pearl_id, realm_id, true_order, time_label, title, shared_text, predict_q, predict_ok, predict_no1, predict_no2) VALUES
  ('P1', 'bamboo', 1, 'Dawn', 'Pearl of Long Shadows', 'The sun is just rising. Long bamboo shadows stretch across the path. The Hourglass of Seasons glows, whole and bright, on the shrine.', 'The forest has long shadows. What time is it?', 'Early morning', 'Midday', 'Midnight'),
  ('P2', 'bamboo', 2, 'Midday', 'Pearl of the Cracked Glass', 'The bamboo has almost no shadow. A thin crack runs across the hourglass. [variant sign]', 'There is almost no shadow. What time is it?', 'Midday', 'Dawn', 'Sunset'),
  ('P3', 'sea', 3, 'Afternoon', 'Pearl of the Far Sea', 'The sea is far out. Wet sand and stranded shells cover the beach. Sharp, glowing glass sand sparkles by the rocks.', 'The sea is far out. What do you expect on the sand?', 'Wet sand and shells', 'Dry sand', 'Deep water'),
  ('P4', 'sea', 4, 'Sunset', 'Pearl of the High Tide', 'The water reaches the high stone line. The sun touches the sea. A trail of glowing glass sand leads up toward the sky stairs.', 'The sun touches the sea. What will the tide be?', 'Up at the stone line', 'Far out', 'No water'),
  ('P5', 'moon', 5, 'Moonrise', 'Pearl of the Low Moon', 'A huge full moon sits low on the edge of the sky. [variant sign]', 'A full moon sits low. What just happened?', 'The sun just set', 'It is noon', 'It is dawn'),
  ('P6', 'moon', 6, 'Midnight', 'Pearl of the Empty Hourglass', 'The full moon is straight overhead. The last grain of glowing time falls. The broken hourglass is empty.', 'The moon is straight overhead. What time is it?', 'About midnight', 'Sunset', 'Morning')
AS new ON DUPLICATE KEY UPDATE realm_id = new.realm_id, true_order = new.true_order, time_label = new.time_label, title = new.title, shared_text = new.shared_text, predict_q = new.predict_q, predict_ok = new.predict_ok, predict_no1 = new.predict_no1, predict_no2 = new.predict_no2;

INSERT INTO pearl_signs (pearl_id, variant_id, sign_text) VALUES
  ('P2', 'V1', 'A single golden hair lies by the shrine.'),
  ('P5', 'V1', 'Cloud tracks curl in a somersault shape on the stairs.'),
  ('P2', 'V2', 'Small white paw prints circle the shrine.'),
  ('P5', 'V2', 'Rice-cake crumbs lie on every step.'),
  ('P2', 'V3', 'A puddle sits by the shrine, but no rain fell today.'),
  ('P5', 'V3', 'The frost on the stairs has melted into rain drops.')
AS new ON DUPLICATE KEY UPDATE sign_text = new.sign_text;

INSERT INTO duel_rounds (round_no, variant_id, form_name, claim_text, is_lie, proof_pearls) VALUES
  (1, 'V1', 'Sun Wukong', 'I stayed under my mountain all day.', 1, 'P2'),
  (1, 'V2', 'Jade Rabbit', 'I never left the moon all day.', 1, 'P2'),
  (1, 'V3', 'Dragon King', 'I stayed under the sea. It was a dry day.', 1, 'P2'),
  (2, 'V1', 'Jade Rabbit', 'The full moon rose just as the sun set.', 0, 'P4,P5'),
  (2, 'V2', 'Dragon King', 'The full moon rose just as the sun set.', 0, 'P4,P5'),
  (2, 'V3', 'Jade Rabbit', 'The full moon rose just as the sun set.', 0, 'P4,P5'),
  (3, 'ALL', 'Sun Wukong', 'The sea broke the hourglass. The glass sand on the beach came first, and the crack came later.', 1, 'P2')
AS new ON DUPLICATE KEY UPDATE form_name = new.form_name, claim_text = new.claim_text, is_lie = new.is_lie, proof_pearls = new.proof_pearls;

INSERT INTO hints (puzzle_key, level_no, hint_text) VALUES
  ('P1', 1, 'What does the sun do in the morning?'),
  ('P1', 2, 'Where is the sun at dawn: low near the hills, or high above you?'),
  ('P1', 3, 'A low sun makes long shadows. When in the day is the sun low and just rising?'),
  ('P2', 1, 'Where does the sun go during the day?'),
  ('P2', 2, 'When is the sun highest in the sky: at dawn, at midday, or at sunset?'),
  ('P2', 3, 'When the sun is straight above you, your shadow almost disappears. When is the sun straight above?'),
  ('P3', 1, 'What happens to a beach when the sea moves away?'),
  ('P3', 2, 'If the water just left, would the sand be wet or dry?'),
  ('P3', 3, 'When the tide goes out, it leaves things behind on the wet sand. What might be lying there?'),
  ('P4', 1, 'The tide goes out and comes back in. Does it stay away all day?'),
  ('P4', 2, 'In the afternoon the sea was far out. A few hours later, which way is the water moving?'),
  ('P4', 3, 'The sea comes back about six hours after low tide. Where would the water reach by sunset?'),
  ('P5', 1, 'When do you usually see a big full moon come up?'),
  ('P5', 2, 'A full moon sits on the opposite side of the sky from the sun. When the sun goes down, what does the moon do?'),
  ('P5', 3, 'A full moon rises just as the sun sets. If the moon is low and rising, what just happened to the sun?'),
  ('P6', 1, 'The full moon climbs across the sky all night. Where does it go after it rises?'),
  ('P6', 2, 'Is the full moon highest at sunset, at midnight, or in the morning?'),
  ('P6', 3, 'A full moon rises at sunset and sets at sunrise. Halfway between, it is straight overhead. What time is that?'),
  ('TIMELINE', 1, 'Think about one whole day, from sunrise to midnight. Which pearl feels like the very start?'),
  ('TIMELINE', 2, 'Shadows, tides and the moon each tell time. Which realm''s clues come early, and which come late?'),
  ('TIMELINE', 3, 'Morning shadows are the longest. Which pearl has the longest shadows? Start there, and let the sun walk across the sky.'),
  ('R1', 1, 'Where did this form say they were all day? Do any of your pearls show they were somewhere else?'),
  ('R1', 2, 'Look at the pearls with strange signs in them. Which one was at the shrine in the Bamboo Forest?'),
  ('R1', 3, 'Your midday pearl shows a strange sign right by the shrine. Does that match what was just said?'),
  ('R2', 1, 'Not every claim is a trick. What do your pearls really show?'),
  ('R2', 2, 'When does a full moon rise: at sunrise or at sunset?'),
  ('R2', 3, 'One pearl shows the sun touching the sea, and one shows a full moon low in the sky. Do they agree with the claim?'),
  ('R3', 1, 'Think about your timeline. What happened earlier in the day?'),
  ('R3', 2, 'When did the crack appear, and when did the glass sand show up on the beach?'),
  ('R3', 3, 'Midday comes before afternoon. Which pearl shows the crack was already there before the sand?'),
  ('VERDICT', 1, 'Who could leave the signs you found at the shrine and on the stairs?'),
  ('VERDICT', 2, 'Two of your pearls hold strange signs. Which two are they, and what do the signs look like?'),
  ('VERDICT', 3, 'Hair, paw prints, or puddles: each sign belongs to someone. Match the signs in your two sign pearls to a suspect.')
AS new ON DUPLICATE KEY UPDATE hint_text = new.hint_text;
