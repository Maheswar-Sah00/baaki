# Baaki (బాకీ): a wage advocate in her pocket

*"Bolo. Baaki sambhal lega."* (Just speak. Baaki asks.) · Built on Gnani.ai Prisma and Timbre · [PDF version](Baaki_Solution_Pitch.pdf)

**The problem.** Hyderabad's maids and cooks are often owed money they can't calculate, can't put in writing, and can't safely ask for in their employer's language.

- **81%** of Hyderabad's domestic workers earned below the state's minimum wage (Montfort Social Institute survey, via [Siasat, Aug 2025](https://www.siasat.com/the-silent-domestic-labour-force-in-telangana-is-mostly-invisible-3264044)).
- **6 lakh** domestic workers in Hyderabad, by a union estimate (officials say 2 lakh) ([Siasat](https://www.siasat.com/we-want-dignity-domestic-workers-protest-for-rights-recognition-in-hyderabad-3234135/)).
- **61.1%** literacy among rural women in Telangana, PLFS 2023-24 ([Telangana Today](https://telanganatoday.com/rural-literacy-rate-plunges-in-telangana-stands-second-from-bottom-among-all-states)).

**Who it's for.** Domestic workers in Hyderabad, mostly women, who speak Telugu or Hinglish, work in 3 to 6 homes with no contract, and are paid in cash or UPI. Second user: the employer, who opens the link she shares on WhatsApp. No app, no login.

**The solution.** She speaks, confirms and presses Send. Baaki does the rest: it adds up what she is owed, checks it against the law (Code on Wages 2019; Telangana G.O.Ms.No.6), reads it back to her, and asks the employer for her in a polite, AI-disclosed voice note in his language. It keeps hash-chained proof and follows up until she confirms the money arrived.

**How Gnani's models power it.**
- **Prisma v3.0 STT** hears her (`te-IN,hi-IN,en-IN` in one request, codemix, so there is no language picker), his replies, and her spoken consent. With **Listen-twice**, it also re-hears every voice note before she sends it, to check each amount and the AI label.
- **Timbre v3.0 TTS** speaks the read-back (`<slow>`, `<pauses>`), the voice notes in Hinglish or Telugu, and "Paisa aa gaya!" (`<excited>`).
- **Voice Clone** (opt-in, with spoken consent) can speak the note in her own voice.
- Every rupee comes from our own Telugu and Hindi number parsers, never from a language model.

**Demo in 5 steps** (synthetic data).
1. Lakshmi talks in Telugu. The Baaki Meter counts up as she speaks: ₹13,000.
2. Baaki reads it back slowly in Telugu. She says "Haan, sahi hai". Nothing is saved before that.
3. Law check: s.20(2) allows ₹308 of the ₹1,000 sick-day cut, so her baaki is **₹12,692**.
4. A polite Hinglish voice note, AI disclosure first, checked by Listen-twice. She shares it on WhatsApp.
5. Sharma ji's page plays it and opens UPI. He taps "I've paid". She confirms the money arrived, and her phone says "Paisa aa gaya!".

**Proof.** In a small noise test, Baaki read **34 of 34 rupee amounts exactly** across 24 noisy clips (a kitchen as loud as the voice; kitchen, phone line and WhatsApp compression at once). *Stock Gnani voices, a synthetic kitchen, 12 sentences, run once: a small test, not an accuracy rate.*

**Why it matters, and what's next.** Baaki never asks for more than the law supports, so the request is hard to wave away, and it lets her ask without risking the job. Next: the milkman's bill and chit money (in the app as "other dues"), a basic-phone line on Gnani's voice agents, and more of Gnani's languages. Not legal advice; it points to the Labour Department, NALSA 15100 and India Labourline.

**Links.** Repo: [github.com/Maheswar-Sah00/baaki](https://github.com/Maheswar-Sah00/baaki) · Demo video: <!-- VIDEO_URL --> *(link coming)*
