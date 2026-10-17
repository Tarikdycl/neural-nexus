# Validation kit: interviews and playtests

The judges score **problem validation** and **user experience**. Code can't do this part; people can.
Goal for the weekend: **3 conversations** (teachers, tutors or parents) and **2 observed playtests**.

## 1. Interviews (5 minutes each)

Ask (design doc section 13):

1. "Do the children you know use AI for homework? How?"
2. "What worries you about that?"
3. "Would a game that asks questions instead of giving answers help? Why or why not?"

Write down **the exact words**, the person's **role** (teacher, parent, tutor), and whether they **agree to be quoted**.

| # | Role | Quote (exact words) | OK to quote? |
|---|------|---------------------|--------------|
| 1 |      |                     |              |
| 2 |      |                     |              |
| 3 |      |                     |              |

## 2. Playtests (15 minutes each)

Rules for the observer: **do not help**. Sit beside the player, watch, and write down what happens.
Ask the player to **think out loud** ("tell me what you're thinking").

| Moment | What to watch for | Notes |
|--------|-------------------|-------|
| Before questions | Do they understand the questions? |  |
| Realm | Do they find Look and Listen before Open pearl? |  |
| Predict | Do they guess, or use the clue? (Ask: "Why that one?") |  |
| Clue pictures | Do they look at the sun / water / moon picture? |  |
| Timeline | Where do they hesitate? Which pair do they get wrong? |  |
| Duel round 2 | Do they call the true claim a lie? What reason do they give? |  |
| Reasons | Can they say, in their own words, why the pearls prove it? |  |
| Hints | Which hints helped? Which confused them? |  |
| Narrator voice | Do they listen, or skip/mute it? Can they follow it? Too slow or too fast? |  |
| Anywhere | Where did they guess repeatedly or get stuck? |  |

After each playtest, open `/teacher` and note the numbers for that player.

## 2b. Narrator voice listening test (15 minutes, on the demo laptop)

The narrator should sound **deep, warm, unhurried and a little nonchalant**. Which voice that is depends on the
laptop and browser, so pick it by listening, not by guessing.

1. Open the game in the browser you will demo with (Edge on Windows has the best "Natural" voices; Chrome is fine).
2. Press **Voice settings**. The list shows every English voice on this laptop; the game pre-selects the first match
   from its preference list (`VOICE_PREFERENCE` in `static/app.js`).
3. For 3 to 4 candidate voices: select it, press **Test voice** ("The forest has gone quiet. Someone has misplaced an
   hour. Let's see where it went."). Then play one realm with it.
4. Two or three listeners (ideally one child) score each voice from 1 to 5:

| Voice name (as listed) | Deep | Warm | Unhurried | Calm / nonchalant | Easy to understand | Total |
|------------------------|------|------|-----------|-------------------|--------------------|-------|
|                        |      |      |           |                   |                    |       |
|                        |      |      |           |                   |                    |       |
|                        |      |      |           |                   |                    |       |

5. Leave the winner selected (the browser remembers it). If it is not first in `VOICE_PREFERENCE`, move it to the top
   so other laptops pick it too. Tick **Speak more slowly** if listeners found it fast.
6. Check the controls once: **Skip** stops the current line, **Mute** silences everything (captions stay),
   **Replay** on any line says it again.

Winner: ______________________  Browser: __________  Laptop: __________

## 2c. Deployment check (5 minutes, before every demo)

From any laptop: `python scripts/check_deployment.py http://<public-ip> --play`. Every line must say PASS
(a WARN about the AI means the game is using pre-written lines, which is allowed). On the server,
`bash scripts/test_on_server.sh` runs every test against the real MySQL HeatWave.

| Date | Server | check_deployment result | test_on_server result |
|------|--------|-------------------------|-----------------------|
|      |        |                         |                       |

## 3. Fix one thing, and write it down

Pick **the most common problem** from the playtests, fix it, and record it here. Judges like seeing
"we watched kids play, saw X, and changed Y".

- Problem we saw:
- What we changed:
- Did the second tester still hit it?

## 4. Demo sequence (2 minutes)

One clear story, as the review suggests:

1. A player **makes a mistake** (for example, a wrong timeline order).
2. They get a **useful hint** (the Scroll asks about one pair, without saying which is wrong).
3. They **revise their reasoning** and **succeed with evidence**.
4. **Invite a judge to answer duel round 2** (the true claim). Most people call it a lie.
5. Show the **teacher view**: every number says how many students it is based on, and the before/after card is labelled "early evidence only".

## 5. What we can honestly claim

- "The AI is never given the answer, never writes hints, and every reply is checked." (True, and tested.)
- "We measure reasoning, not finishing." (True: see the teacher view definitions.)
- Before/after results are **early evidence from N students**, not proof that the game improves reasoning. Say the N.
