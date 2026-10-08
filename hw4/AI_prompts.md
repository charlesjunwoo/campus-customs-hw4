# AI Prompts Log — Campus Customs

Running log of the prompts I gave the AI coding assistant for this assignment. Each problem has its own section with the prompt I used, plus any follow-up prompt and a one-sentence note on why it was needed.

---

## Problem 1 — Project Setup & Prompt Log

**Prompt:**

> I'm looking to build Campus Customs website with an an accompanying chatbot that will help Campus Customs site visitors create account, browse our products, get recommendations, check inventory and order, chat about our merch, visaulize that merch on page and retrieve price and stock info from a local database. The front end will be React and Vite TypeScript while the chatbot will be PydanticAI powered, while the backend will have Python FastAPI.
>
> The main reference for our agent prompt is https://yalebulldogblue.com/
>
> campus_customs.db is our database containing product catalog, inventory by size and users (with hashed passwords). Product image files paths are also in the catalog table. Usemy PORTKEY_API_KEY for agent's calls. You will push this project to a public GitHub repo and give me the URL when we are finsihed so I can submit to my professor/TA. Do not commit the database or product images.
>
> refer to my "data 3" file in downloads for data/campus_customs.db is the SQL databsae with tables catalogue, investnory and users (we have a test users sitting in there now), data/products/ is product images where the paths match the catalogue table. should be unzippped already.
>
> For Problem 1, create AI_prompts.md. This is going to be the running log of what I actually type to you throughout the assignment. Give each problem its own section with the problem number/title and the prompt I used. If I have to follow up because something was missing or went wrong, include the follow-up prompt and one sentence explaining why I needed it. We are running this one problem at a time, so do not jump ahead and build the whole thing yet.

---

## Problem 2 — Database Analysis

**Prompt:**

> problem 2: database analysis. AFter inspecting each table and its fields in data/campus_customs.db (crucial fields are catalogue, inventory, users)   Create output/harness.md in whuch you should create a short one-liner describing why each field matters for Campus Customs and the chatbot. Note that we are going to be growing this harness file throughout future problems so set it up in a way that we can keep adding sections for models, tools, safety, specs, etc.

---

## Problem 3 — Website, Product Pages, Chat Stub & FastAPI Backend

**Prompt:**

> Problem 3: it's time to build. Use React, Vite and TypeScript  wiht. anavigation bar that contains links to main pages: Home, Products, About Us, Log in and Create Account. Pull from yalebulldog.blue for the Home and About Us pages but do NOT copy the original site text. Use your own voice. On Products page, show images from catalogue using image paths contained in the database with key product info like price, name and a one-liner. Make each product a single-item page (large image on one side, full product text on the other containig descirition, price, sizes and stock. CLicking a card on Products should link the shopper there directly. Also build out a chat interface in the bottom right. We will code its speech later, a stub that will call the backend is enough for now. We also need a API to read the databsase so  start a simple FastAPI app in:
> backend/main.py

---

## Problem 4 — Create Account / Log In Flow

**Prompt:**

> Problem 4: build the creat account/log in flow. Create account system must require fist name, last name, email password and the login mechanism must require email and password. New accounts go into the users table, and ensure to sescurely store the passwords so no AI or human can steal this sensitive info. As mentioned, that test user in the database has an email (test@campuscustoms.yale.edu) and password you should confirm that you can login as that user. Also confirm a brand-new account also works when created. Update output/harness.md with how the authentication works provided it does acutally work, with details about what what you store for a user and how you've protected passwords.


**Follow-up prompt:**

> Also the password for the test user should just be: password

*Why:* the test user's password wasn't in the database or project files, and the assistant (correctly) wouldn't guess or crack the stored hash, so I had to supply it before the test-user login could be confirmed. (I first asked it to "figure it out" in Problem 9, and it declined.)

---

## Problem 5 — Chatbot (PydanticAI Agent + Chat Route)

**Prompt:**

> Problem5: build the chatbot. Put the API in backend/main.py. That will be run with Uvicorn. Keep the agent as these four files as we did in Homework 3: backend/prompts/prompt.md (system prompt), backend/agent.py (agent entry and wiring), backend/tools.py (tools agent can call), backend/models.py (Pydantic/Pydantic AI structured types). In main.py, expose a chat route so a message from the site returns a reply from the chatbot
>
> Put Campus Customs voice and safety basics into backend/prompts/prompt.md that will be expanded later. Start types in models.py for chat replies and product cards. In output/harness.md report on how the frontend is talking to the FastAPI and how the agent is loaded (prompt file and model). Put the API in backend/main.py. Use my AI model API key for the agent and ensure the backend runs from backend/ folder follows: "uvicorn main:app --reload --port 8000"

---

## Problem 6 — Grounded Product Lookups (Description, Price, Stock by Size)

**Prompt:**

> The agent needs to be able to recall product description, price and how many are in stock by size when a customer asks- from campus_customs.db. The agent must use the database and MUST NOT hallucinate or invent any info like prices or quantities. If a size is out of stock, the agnet mus tbe able to say so definitively. Expand prompts/prompts.md so the agent knows to call info for prices and stock questions add or update return types in backend/models.py. List tools and explain which mdoel fields you chose for looup results and provide a rationale as well in output/harness.md

**Follow-up prompt:**

> (that's problem 6 btw)

*Why:* I hadn't labeled the prompt with a problem number, so I clarified it mid-task so the log and harness would file it under Problem 6.

---

## Problem 7 — Product Cards from Chat Search

**Prompt:**

> Problem 7: time to add a card  feature: build a mechanism that responds to questions from users: an agent should be able to search the catalogue and the site should dynamically show matching items as product cards (image, name, price and short one-liner descrioption) This is an API contract that forces teh agent to return product matches and then communicates that to the frontend to show it on the website. Once these cards are loaded, ensure that the same single-item page behavior from Problem 3 still works well. Each product card including the new ones the chat has just surfaced on the website should all open per that problem parameters, as a large image with full infomration when clicked on. Update prompts/prompt.md and the harness to detail how search results reach the page.

---

## Problem 8 — Customer Memory, Identity & Page Context

**Prompt:**

> Problem 8: time to work on customer memory. When a user logs into the site, save all chat history in the database in a table in the backend that reloads when that same user returns to the site. The agent must be able to identify who is chatting by pulling name, email) and ass that user identity into the agent through deps or another clear context pattern, and/or give the agent tools it can call to retrieve the logged-in user info. Also build out enough context so that if someone clicks into a product and enquries about it (e.g. whether the product is available in a specific color), the agent is able to which item the user is describing. Build this  context into the agent. History is only key for logged-in users.
> Document how you're storing user chat, what customer fields the agent sees and how page context is passed in the harness file.

---

## Problem 9 — Show & Improve (Usability)

**Prompt:**

> Problem 9 is about show and improve. We have to show that the shop works, and then must improve its usability with 2 frontend changes (e.g. a more natural conversation flow, SKU info) and 2 agent adjustments in the backend (reloading prior chat history, sound effects). Write output/usability.md as you build. For each improvement, say what you added and why it helps the shopper or the business. Then ensure that these changes are acutally showing up and running in the app.  As far as the Problem 4 password, this is not a real person's password so ifgure it out please.

---

## Problem 10 — Design Refresh (Yale × Halloween, Motion, Spook)

**Prompt:**

> Problem 10: we need to work on the frontend to fix fonts colors, motion and product presentaiton as well as changes to the chat function that animate the site and make it fun. To do this, we will need colors that represent both Yale and Hallowen given it is the mont of October. Create a function that spooks the user with halloween imagery (emojis) with requisite sound effects. The changes should be written in output/design.md and contain why it will help customer retention. Keep this succinct.

---

## Problem 11 — App Check (Screenshots + HTML Report)

**Prompt:**

> Problem 11: we need to test the site/check our app function. All results must be documented in output/app_check.html, which must be openable via double-click. Chat must be able to check the inventory level of an item (accurate stock and price info from the database), dynamic search results cards that are triggered by a customer's category question like around hoodies and one usability feature added from Problem 9. Make the HTML easy for the TA to grade in the form of a headline for each check you perform, a screenshot capturing that and a one-two sentences on what the screenshot proves. Put screenshot image files in output/app_check_images/ and link them from app_check.html with relative paths (e.g. app_check_images/inventory/png)
>
> Also the password for the test user should just be: password

---

## Problem 12 — Audit Trail, Safety Rules & Final Harness

**Prompt:**

> Problem 12: we're not rady to github repo it yet. we need to do the  audit trail first. Keep an append-only output/audit_trail.json file containing all agent-loop activity (time, tool name, short args/result and stop reason). Do not wipe between runs. In prompts/prompt.md place safety rules for agent to follow. Finish the harness so that it is legible and very clear as to how the entire system works. It should contain model fields in models.py and why you chose them for this job, tools and abilities, safety rules and specs (loop limits, results caps, models, how to run front and back end)

---

## Problem 12 (part 2) — Package in hw4/ and Publish to GitHub

**Prompt:**

> Problem 12: put the whole project inside a folder called hw4 and push it to a public GitHub repo. We need to submit the repo URL so give me that when everything is finished.
> Make sure hw4 contains AI_prompts.md, requirements.txt, .env.example, .gitignore, README.md, frontend/, backend/ and output/.
> Inside backend keep main.py, agent.py, models.py, tools.py and prompts/prompt.md.
> Inside output keep harness.md, design.md, usability.md, app_check.html, app_check_images/ and audit_trail.json.
> Do not put my real .env, data/campus_customs.db or any product images into the GitHub repo. Keep the whole data folder local only. Use .gitignore so none of that can accidentally get committed.
> Include .env.example with placeholder values only and no real API keys or secrets.
> README.md should explain how to run the frontend and backend after putting the local data pack in the right place.
> Before pushing, check that all the required files are there, the repo does not contain the real .env, database or product images, and that .env.example only has placeholders.
> Then push it to a public GitHub repo and give me the repo URL.
