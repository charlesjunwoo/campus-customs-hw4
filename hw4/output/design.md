# Campus Customs: Design Refresh (Problem 10)

**Goal:** a fun, seasonal storefront (Yale x Halloween) that gives shoppers a reason to come back, without hurting readability, accuracy, or accessibility.

## What changed

| Area | Change | Why it helps retention |
|---|---|---|
| **Colors** | October palette layered on the existing CSS variables: **Yale Blue** `#00356b` nav and headings, **pumpkin** `#ff7518` buttons and highlights, **witch purple** `#6a2c91`, **candy corn** `#ffc93c` price tags, **slime** `#8ee04b` accents, **bone** `#f6eddc` background, **midnight** `#160f1f` ink. Turns on automatically in October (`season.ts`) and reverts to the classic look after; `?theme=classic` / `?theme=halloween` for demos. | A seasonal look signals an active store and gives regulars something new to see. It stays clearly Yale, so brand trust isn't diluted. |
| **Fonts** | **Bungee** (80s display) for headings and prices, **Space Grotesk** for body text and product names, **Creepster** for small spooky accents only. Faux-bold disabled. | Clearer hierarchy and more readable product names reduce friction, and a distinctive look is memorable. |
| **Motion** | Cards rise in with a staggered entrance; hover lifts the card and zooms the photo; product pages slide in with a swinging price tag; low-stock badges pulse; hero shapes drift; a bat flies across the hero; the headline flickers. Everything is disabled under `prefers-reduced-motion`. | Motion guides the eye to products and stock urgency, and makes browsing feel lively instead of static. |
| **Product presentation** | Candy-corn price "stickers", "View →" reveal on hover, image zoom on cards and product pages, product names in the readable text face. | Easier scanning and clearer prices mean more product views per visit. |
| **Chat** | Pumpkin chat button that bobs; messages pop in; pumpkin typing dots; Halloween header; quick replies cascade in; in October the agent adds one light Halloween flourish per reply (facts unchanged; the fact guard still applies). | A chat that feels alive gets used more, and conversations convert better than browsing alone. |
| **`spook()`** | An emoji swarm (🦇 swoop, 👻 float, 🕷️ drop on threads, 🎃💀🕸️🍬 pop) with a giant Creepster **BOO!**, plus a synthesized scare sound: a theremin glide, a low "boo" growl, and bat-wing clicks (Web Audio, no files). **Triggers:** the 🎃 "Trick or treat" button in the nav; spooky words in a chat message or reply (boo, Halloween, ghost, pumpkin…); and a small, quiet "mini" boo on the first chat open each session. Click to dismiss, auto-clears in ~3 s, uses the same ♪ mute toggle, and shows a still fade under reduced motion. | A playful surprise is shareable and gets talked about ("try typing *boo*"), which brings people back and invites them to explore the chat. It's opt-in after the first mini boo, so it delights without annoying. |

## Verified in the running app

- **Theme on (Oct 8):** `data-theme="halloween"`. Nav `rgb(0,53,107)` (Yale Blue), CTA `rgb(255,117,24)` (pumpkin), price tags `rgb(255,201,60)`, bone background. Bungee, Creepster, and Space Grotesk all loaded.
- **Seasonal details:** eyebrow "Spooky season at 57 Broadway" in Creepster, "Boo-la Boola!" sticker, cobweb, flying bat, pumpkin chat button.
- **🎃 nav button:** full overlay with "BOO!" and 22 emoji sprites, cleared after ~3 s. 9 synth voices recorded (theremin + vibrato, growl, 6 bat clicks).
- **Chat triggers:** first chat open of the session gave a mini spook; "Got anything spooky for Halloween?" gave a full spook instead of the normal chime. The reply stayed honest: "I didn't find Halloween-specific Yale gear, but… dark, charcoal Bulldog styles… 🎃".
- **Classic theme:** `?theme=classic` restores the original navy and hides the pumpkin button; the new fonts and motion still apply.
- **Checks:** frontend type-check passes and backend tests pass (135).

**Files:** `frontend/src/season.css`, `season.ts`, `spook.ts`, `sound.ts` (`playSpook`), `components/Spooker.tsx`; small edits to `NavBar.tsx`, `ChatWidget.tsx`, `ProductCard.tsx`, `Home.tsx`, `App.tsx`, `main.tsx`, `index.html`; `backend/agent.py` (October tone line).
