-- GENERATED FILE - do not edit by hand.
-- Edit content/story.json, then run: python scripts/build_seed.py
-- Load order (design doc section 8): variants -> realms -> pearls ->
-- pearl_signs -> duel_rounds -> assessment_items -> hints. Safe to run more than once.

INSERT INTO variants (variant_id, culprit, culprit_words, ending_text) VALUES
  ('V1', 'Sun Wukong', 'wukong,monkey king', 'Wukong laughs and bows low. "You caught me, little Seeker! I only wanted one more peach festival."\nHe gives back the hours, and the hourglass is whole again. As a thank-you, he teaches the Seeker one of his 72 changes. He insists it was his idea all along.'),
  ('V2', 'Jade Rabbit', 'jade rabbit,rabbit', 'The Jade Rabbit steps out, ears down. "I only wanted the Moon Festival to last."\nWukong grins. "I hid her tracks to test you, and you did not blame the obvious monkey!"\nThe Rabbit returns the hours. The village plans a festival together, a sensible length this time.'),
  ('V3', 'Dragon King', 'dragon king,dragon', 'The Dragon King rises from the sea, dripping. "My sea was thirsty." It is not much of an excuse, and he knows it.\nWukong shrugs. "I shook my own mountain to warn the village, and everyone blamed me. You looked at the evidence."\nThe Dragon returns the hours. The rain falls only in its season again.')
AS new ON DUPLICATE KEY UPDATE culprit = new.culprit, culprit_words = new.culprit_words, ending_text = new.ending_text;

INSERT INTO realms (realm_id, name, display_order, image_url, look_text, listen_text) VALUES
  ('bamboo', 'Bamboo Forest', 1, '/static/img/bamboo.svg', 'The bamboo shadows are very long. They stretch across the path as if they have somewhere to be.', 'Wind chimes ring at the shrine. Somebody hung them there, and the wind does the rest.'),
  ('sea', 'East Sea Shore', 2, '/static/img/sea.svg', 'A dark wet line marks the big stones. That is how high the water can climb, when it puts its mind to it.', 'Waves whisper far away, then crash closer and closer. The sea is patient about these things.'),
  ('moon', 'Moon Palace Stairs', 3, '/static/img/moon.svg', 'Silver light falls on a long stone staircase. It climbs into the sky, as if the sky were expecting visitors.', 'Soft bells ring from the palace at the top of the stairs. Someone up there is fond of bells.')
AS new ON DUPLICATE KEY UPDATE name = new.name, display_order = new.display_order, image_url = new.image_url, look_text = new.look_text, listen_text = new.listen_text;

INSERT INTO pearls (pearl_id, realm_id, true_order, time_label, title, visual, shared_text, predict_q, predict_ok, predict_no1, predict_no2) VALUES
  ('P1', 'bamboo', 1, 'Dawn', 'Pearl of Long Shadows', '{"kind": "sun", "sun": "low-east"}', 'The sun is just rising. Long bamboo shadows stretch across the path. The Hourglass of Seasons glows on the shrine, whole and bright.', 'The forest has long shadows. What time is it?', 'Early morning', 'Midday', 'Midnight'),
  ('P2', 'bamboo', 2, 'Midday', 'Pearl of the Cracked Glass', '{"kind": "sun", "sun": "high"}', 'The sun is at its highest, and the bamboo shadows are at their shortest. A thin crack runs across the hourglass. [variant sign]', 'The shadows are at their shortest. What time is it?', 'Midday', 'Dawn', 'Sunset'),
  ('P3', 'sea', 3, 'Afternoon', 'Pearl of the Far Sea', '{"kind": "tide", "sun": "mid-west", "water": "low"}', 'The afternoon sun is sinking toward the western hills. The sea is far out, leaving wet sand and stranded shells behind. Sharp, glowing glass sand sparkles by the rocks.', 'The sea is far out. What do you expect on the sand?', 'Wet sand and shells', 'Dry sand', 'Deep water'),
  ('P4', 'sea', 4, 'Sunset', 'Pearl of the High Tide', '{"kind": "tide", "sun": "setting-west", "water": "high"}', 'The water has climbed back up to the high stone line. The setting sun glows red as it sinks behind the western hills. A trail of glowing glass sand leads up toward the sky stairs.', 'All afternoon the waves have crashed closer and closer. Where is the water now?', 'Up at the stone line', 'Far out', 'No water at all'),
  ('P5', 'moon', 5, 'Moonrise', 'Pearl of the Low Moon', '{"kind": "moon", "moon": "low-east"}', 'The sun has gone down. A huge full moon is rising in the east, just above the sea. [variant sign]', 'A full moon is rising in the east. What just happened?', 'The sun just set', 'It is noon', 'It is dawn'),
  ('P6', 'moon', 6, 'Midnight', 'Pearl of the Empty Hourglass', '{"kind": "moon", "moon": "high"}', 'The full moon is at its highest point in the sky. The last grain of glowing time falls. The broken hourglass is empty.', 'The full moon is at its highest point. What time is it?', 'About midnight', 'Sunset', 'Morning')
AS new ON DUPLICATE KEY UPDATE realm_id = new.realm_id, true_order = new.true_order, time_label = new.time_label, title = new.title, visual = new.visual, shared_text = new.shared_text, predict_q = new.predict_q, predict_ok = new.predict_ok, predict_no1 = new.predict_no1, predict_no2 = new.predict_no2;

INSERT INTO pearl_signs (pearl_id, variant_id, sign_text) VALUES
  ('P2', 'V1', 'A single golden hair lies by the shrine.'),
  ('P5', 'V1', 'Cloud tracks curl in a somersault shape on the stairs.'),
  ('P2', 'V2', 'Small white paw prints circle the shrine.'),
  ('P5', 'V2', 'Rice-cake crumbs lie on every step.'),
  ('P2', 'V3', 'A puddle sits by the shrine, but no rain fell today.'),
  ('P5', 'V3', 'The frost on the stairs has melted into rain drops.')
AS new ON DUPLICATE KEY UPDATE sign_text = new.sign_text;

INSERT INTO duel_rounds (round_no, variant_id, form_name, claim_text, is_lie, proof_pearls, proof_mode, reason_ok, reason_no1, reason_no2) VALUES
  (1, 'V1', 'Sun Wukong', 'I stayed under my mountain all day.', 1, 'P2', 'any', 'A pearl shows their sign at the shrine at midday', 'Every pearl agrees with the claim', 'The shrine is too far away to visit'),
  (1, 'V2', 'Jade Rabbit', 'I never left the moon all day.', 1, 'P2', 'any', 'A pearl shows their sign at the shrine at midday', 'Every pearl agrees with the claim', 'The shrine is too far away to visit'),
  (1, 'V3', 'Dragon King', 'I stayed under the sea. It was a dry day.', 1, 'P2', 'any', 'A pearl shows their sign at the shrine at midday', 'Every pearl agrees with the claim', 'The shrine is too far away to visit'),
  (2, 'V1', 'Jade Rabbit', 'The full moon rose right after the sun set.', 0, 'P4,P5', 'all', 'The sun set, and then the full moon rose in the east', 'The full moon was highest at midday', 'There was no moon that night'),
  (2, 'V2', 'Dragon King', 'The full moon rose right after the sun set.', 0, 'P4,P5', 'all', 'The sun set, and then the full moon rose in the east', 'The full moon was highest at midday', 'There was no moon that night'),
  (2, 'V3', 'Jade Rabbit', 'The full moon rose right after the sun set.', 0, 'P4,P5', 'all', 'The sun set, and then the full moon rose in the east', 'The full moon was highest at midday', 'There was no moon that night'),
  (3, 'ALL', 'Sun Wukong', 'The sea broke the hourglass. The glass sand on the beach came first, and the crack came later.', 1, 'P2,P3', 'all', 'The crack came first, and the glass sand came later', 'The glass sand came first, and the crack came later', 'The crack and the sand happened at the same moment')
AS new ON DUPLICATE KEY UPDATE form_name = new.form_name, claim_text = new.claim_text, is_lie = new.is_lie, proof_pearls = new.proof_pearls, proof_mode = new.proof_mode, reason_ok = new.reason_ok, reason_no1 = new.reason_no1, reason_no2 = new.reason_no2;

INSERT INTO assessment_items (item_id, phase, skill, question, choice_ok, choice_no1, choice_no2) VALUES
  ('PRE1', 'pre', 'time_from_evidence', 'In a park, a flagpole''s shadow is very long and the sun is low in the east. What time is it most likely?', 'Morning', 'Noon', 'Evening'),
  ('PRE2', 'pre', 'trust_evidence', 'Kai says, "The tide was high this morning." Wet seaweed lies on the top rocks of the beach, where the water only reaches at high tide. What should you think?', 'The evidence supports what Kai says', 'Kai is probably not telling the truth', 'There is no way to tell anything'),
  ('POST1', 'post', 'time_from_evidence', 'At the lake, the sun is low in the west and the tree shadows are getting long. What time is it most likely?', 'Evening', 'Morning', 'Noon'),
  ('POST2', 'post', 'trust_evidence', 'Sam says, "It rained last night." This morning the streets are wet and there are puddles everywhere, even though the sky is clear now. What should you think?', 'The evidence supports what Sam says', 'Sam is probably not telling the truth', 'There is no way to tell anything')
AS new ON DUPLICATE KEY UPDATE phase = new.phase, skill = new.skill, question = new.question, choice_ok = new.choice_ok, choice_no1 = new.choice_no1, choice_no2 = new.choice_no2;

INSERT INTO hints (puzzle_key, level_no, hint_text) VALUES
  ('P1', 1, 'The sun keeps a routine, like most of us. What does it do first thing in the morning?'),
  ('P1', 2, 'Shadows tell you where the sun is sitting. At dawn, is the sun low near the hills, or high above you?'),
  ('P1', 3, 'A low sun makes long shadows, and these shadows are very long. When in the day is the sun low and just rising?'),
  ('P2', 1, 'The sun moves across the sky all day, slowly and without fuss. Where does it go during the day?'),
  ('P2', 2, 'Short shadows mean the sun is high overhead. When is the sun highest: at dawn, at midday, or at sunset?'),
  ('P2', 3, 'When the sun is at its highest, shadows are at their shortest. These shadows are about as short as they get. When is the sun highest?'),
  ('P3', 1, 'The sea comes and goes, and it is never in a hurry. What happens to a beach when the sea moves away?'),
  ('P3', 2, 'Water leaves things wet when it goes. If the sea just left, would the sand be wet or dry?'),
  ('P3', 3, 'When the tide goes out, it leaves things behind on the wet sand. Shells are not very good at keeping up. What might be lying there?'),
  ('P4', 1, 'Listen to the waves for a moment. Are they moving away from you, or coming closer?'),
  ('P4', 2, 'In the afternoon, the sea was far out. If the waves keep coming closer, where will the water be later?'),
  ('P4', 3, 'Waves that crash closer and closer for hours climb up the beach. The dark line on the stones shows how high they get. Which answer shows the water up high?'),
  ('P5', 1, 'The moon has its habits too. Where does a full moon come up: in the east or in the west?'),
  ('P5', 2, 'A full moon sits across the sky from the sun. When the moon rises in the east, where is the sun?'),
  ('P5', 3, 'A full moon rises in the east just as the sun sets in the west. They take turns, very politely. What just happened to the sun?'),
  ('P6', 1, 'The full moon climbs across the sky all night, taking its time. Where does it go after it rises?'),
  ('P6', 2, 'The moon climbs and then sinks, much like the sun does. Is the full moon highest at sunset, at midnight, or in the morning?'),
  ('P6', 3, 'A full moon rises at sunset and sets at sunrise. Halfway between, it is at its highest. What time is that?'),
  ('TIMELINE', 1, 'Think about one whole day, from sunrise to midnight. Which pearl feels like the very start?'),
  ('TIMELINE', 2, 'Shadows, tides and the moon each keep time in their own way. Which clues come early in the day, and which come late?'),
  ('TIMELINE', 3, 'Morning shadows are the longest of the day. Start with the longest shadows, and let the sun walk across the sky. Which pearl comes next?'),
  ('R1', 1, 'This form says it was somewhere else all day. Do any of your pearls show otherwise?'),
  ('R1', 2, 'Some of your pearls hold strange signs. Which one was at the shrine in the Bamboo Forest?'),
  ('R1', 3, 'Your midday pearl shows a strange sign right by the shrine. Does that match what was just said, and which reason fits?'),
  ('R2', 1, 'Not every claim is a trick. What do your pearls really show?'),
  ('R2', 2, 'Look for the sun going down and the moon coming up. Which two pearls show that?'),
  ('R2', 3, 'One pearl shows the setting sun, and another shows a full moon rising in the east. Do they agree with the claim?'),
  ('R3', 1, 'Think about your timeline for a moment. What happened earlier in the day?'),
  ('R3', 2, 'One pearl shows the crack, and another shows the glass sand. Which two are they?'),
  ('R3', 3, 'Midday comes before afternoon, every single day. Was the crack already there before the sand?'),
  ('VERDICT', 1, 'Somebody left signs behind, at the shrine and on the stairs. Who could leave signs like those?'),
  ('VERDICT', 2, 'Two of your pearls hold strange signs. Which two are they, and what do the signs look like?'),
  ('VERDICT', 3, 'Hair, paw prints, or puddles: each sign belongs to someone. Match the signs in your two sign pearls to a suspect. Who fits?')
AS new ON DUPLICATE KEY UPDATE hint_text = new.hint_text;
