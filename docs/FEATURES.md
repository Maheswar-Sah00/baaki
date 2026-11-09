# Baaki: feature plan

**One line:** Lakshmi speaks Telugu while she works. Her employer hears a polite Hinglish voice note in her own voice that says what is owed, and they can pay it with one tap.

Who it is for: domestic workers in Hyderabad (maids, cooks, cleaners) who work in 3 to 6 homes, are paid in cash or UPI, have no contract, and lose money through unpaid months, cuts for sick days and quiet underpayment.

Rules every feature follows:
- Voice is used only for things it does reliably: transcription, read-back and speaking. We never infer hidden states like emotion or intent.
- Nothing is sent without the worker confirming the read-back.
- No AI calling of strangers. Delivery uses links and voice notes the worker shares herself.
- Every AI voice says it is AI. This is required by the IT Rules, and it is honest.
- No claims about legal outcomes. Compensation is described as "the authority may award", never as something she is owed.
- Synthetic demo data only.

---

## A. The core loop (must ship)

### 1. Speak it, don't type it
Big mic button. She talks naturally: *"Mūḍu nelalu jītam ivvalēdu, nelaku nālugu vēlu..."* ("Three months' salary not paid, four thousand a month...").
- Prisma v3 with `indic-auto` detects Telugu, Hindi or code-mixed speech, with no language picker.
- **Works in the kitchen.** It's built for noisy audio: a pressure-cooker whistle and a running tap are part of the demo. This targets the noisy-audio award.

### 2. The Baaki Meter (shows something in the first 10 seconds)
As she speaks, a large rupee counter **ticks up live**: ₹4,000 → ₹8,000 → ₹12,000 → +₹1,000 for the sick-day cut.
Every amount appears as a chip she can tap to remove or fix.

### 3. Read-back in her language
Before anything is saved, Baaki reads it back slowly in her own language, using `<slow>` and `<pauses>` for the numbers:
"Teen mahine… chaar hazaar har mahina… kul baara hazaar. Sahi hai?" ("Three months… four thousand each month… twelve thousand in total. Is that right?")
She says "Haan" (yes) or taps ✓. This read-back is the safety gate for everything that follows.

### 4. Haq Check: the money she didn't know about
Baaki compares what she is paid with Telangana's legal minimum for her hours and homes:
"You earn ₹4,000 for 2 hours a day. The legal minimum for that work is ₹X. **Hidden baaki: ₹Y/month.**"
It shows the official notification and lets her decide whether to include it. It reports a fact, not a demand.

### 5. Her voice, their language ⭐ (the signature feature)
With one-time consent, she records 10 seconds of her voice to create a voice profile (Gnani voice clone).
Baaki writes a respectful message in the **employer's** language (Hinglish, Telugu or English) and Timbre speaks it **in Lakshmi's own cloned voice**.
Every note starts with the AI label: "Yeh sandesh Lakshmi ki anumati se, unki awaaz mein, Baaki app ne banaya hai." ("This message was made by the Baaki app, in Lakshmi's voice, with her permission.")
- The employer hears *her*, in a language *they* understand.
- If she declines cloning, a standard Timbre voice is used.

### 6. The Polite → Firm → Formal ladder
Three steps, each in the employer's language. She chooses when to move up.
1. **Polite** (day 0): a warm voice note and an itemised card.
2. **Firm** (about day 7): a clear reminder with the total and her work log attached.
3. **Formal** (about day 15): a bilingual demand letter PDF in Telugu and English that cites the right law and mentions free legal aid through the DLSA.
She shares each step herself through WhatsApp, using Web Share.

### 7. Employer page: pay, discuss or pay in parts
The link opens a simple page for the employer:
- Play the voice note.
- See the itemised baaki.
- **Pay now (UPI):** a deep link pre-filled with her UPI ID and the amount.
- **Pay in parts:** choose 2 or 3 instalments, and Baaki sets up the reminders.
- **Question an item:** the employer records a voice reply in Hinglish, and Baaki plays it to Lakshmi in Telugu.

When the employer marks it paid, Lakshmi's phone plays "Paisa aa gaya!" ("The money has arrived!") using `<excited>`. This closes the loop: the agent acts, it doesn't only advise.

### 8. Safety switch
If she mentions being locked in, beaten, having her ID taken, or a minor working, Baaki stops the wage flow. It shows 181 (women's helpline), 112 and 1098, the NDWM and union contacts, and a **quick-exit** that switches the screen to a plain recipe page.

---

## B. Prevention and evidence (strong, ship if time allows)

### 9. Kaam Patta: an agreement made by voice
At the start of a new job, both sides speak the terms: wage, hours, weekly off, leave days and the yearly raise. Baaki produces a one-page bilingual agreement, and both accept it with a tap.
This prevents disputes instead of fighting them. (Note: the Gnani entry "SunoSahi" already confirms wage terms at hiring, so this feature is a nice extra, not our selling point.)

### 10. The 5-second Kaam Diary
A daily voice check-in such as "Aaj Sharma ji ke ghar, do ghante" ("Today at Sharma ji's house, two hours") builds a work calendar for each home. Each entry is timestamped and given a SHA-256 hash, so the log can be shown to be untampered. It becomes the evidence annex in the formal letter.

### 11. One dashboard for all her homes
Each employer gets a card showing their baaki, the last step sent, the next reminder, and status: paid, partly paid or ignored.

### 12. Legal aid pack
If the ladder fails, one tap builds a pack for **India Labourline (1800 833 9020)**. It has a Hyderabad desk at Montfort Social Institute, and has recovered ₹70 crore across 57,000 cases. The pack also suits the Telangana labour office or the DLSA (NALSA 15100). It contains:
- her statement in her language, with an English translation
- the itemised claim
- the diary log with hashes

The route is the state's, never SAMADHAN, which handles central-government employers only. A rival entry, Shramik-Nyay, sends cases there by mistake.

---

## C. Shareable features (for the LinkedIn post and the crowd-favourite award)

### 13. Baaki Wrapped
A year-end card for her to share: "1,240 hours across 4 homes. ₹18,000 recovered with Baaki."

### 14. Fair Employer badge
When an employer pays in full, or signs a Kaam Patta, they get a "Fair Employer" card to share in their society WhatsApp group. It reinforces good employers instead of shaming bad ones, so there's no defamation risk.

### 15. Didi mode
A daughter, NGO volunteer or union member can run Baaki *for* her. The worker's voice and consent stay at the centre.

---

## D. Future ideas (roadmap slide and video ending)
- **Baaki on a basic phone:** a missed-call or IVR line on Gnani's voice agents, so no smartphone is needed.
- **Union and NGO console:** see recovered wages across members, and spot employers with a pattern of withholding pay.
- **Society-level Fair Wage pledges:** residents' associations adopt minimum terms for household staff.
- **Escrow salary:** the employer pre-funds the month and the money is released automatically on the agreed day.
- **More languages:** all 10 that Gnani supports, so the same flow works for Kannada, Tamil and Bengali workers in other cities.

---

## Build priority
1. Core loop: 1 → 2 → 3 → 5 → 6 → 7 (the demo story)
2. 4 Haq Check, and 8 Safety switch (credibility)
3. 11 Dashboard, 10 Kaam Diary, 12 Legal aid pack
4. 9 Kaam Patta, 13 Wrapped, 14 Fair Employer badge, 15 Didi mode (only if time is left)

## Gnani features each one uses
| Feature | Gnani |
|---|---|
| Speak it, Works in the kitchen | Prisma v3 `indic-auto`, code-mix output, noisy audio |
| Read-back | Timbre v3 with `<slow>` and `<pauses>` tags |
| Her voice, their language | Voice clone embeddings + VC TTS |
| Paisa aa gaya | Timbre `<excited>` tag |
| Employer voice reply | Prisma (Hinglish) → Timbre (Telugu) |
