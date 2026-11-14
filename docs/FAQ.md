<!-- Owner: Person 3 (Integration, Logic & API Lead) -->
# AgriLink Africa: questions people might ask

Simple answers for anyone new to the project, whether they're judges, teammates or first-time coders.

## About the app

**What is AgriLink Africa?**
It's an app where farmers sell crops and buyers find them, a bit like Depop but for maize, beans, coffee and other crops. It also shows crop prices as charts (like a stock-trading app), the weather, and an AI assistant that gives farming advice.

**Who is it for?**
Small farmers and crop buyers in Africa. The demo users are in Kenya, Nigeria, Ghana, Uganda and Somalia.

**What problem does it solve?**
Farmers often don't know the fair price for their crop, so middlemen can underpay them. AgriLink shows today's price, where it's heading, and lets farmers talk to buyers directly.

**Is it a real app that's live right now?**
It's a working prototype. It runs on your own computer with demo data. The prices are realistic but simulated, and no real money changes hands.

## Using it

**How do I log in?**
Use one of the demo accounts, for example username `amina_w` and password `Password123!`. Or tap **Create an account** to make your own.

**How do I see my password while I type it?**
Tick **Show password** under the box, or tap the eye icon. Untick it and your password goes back to dots.

**How do I log out?**
Tap the **logout icon** (an arrow leaving a door) at the top right of any main screen, or go to **Settings > Log out**. The app asks you to confirm first.

**How do I sell a crop?**
Tap **Sell**, pick the crop, then type the amount, your price and the pickup place. The app shows today's market price so you can pick a fair one.

**How do I buy?**
Open **Market**, tap a listing, choose how much you want and tap **Buy now**. You can tap **Message seller** first to agree on delivery.

**What does the price chart mean?**
Green means the price went up, and red means it went down. Tap 1W, 1M, 3M or 1Y to see the last week, month, 3 months or year. Turn on **Show AI prediction** to see a dashed line guessing the next 30 days.

**What is a price alert?**
You pick a crop and a target price. The app tells you when the price goes above or drops below it.

**Can I use it in Swahili or Somali?**
Yes. Go to **Settings > Language**. Menus are translated into Kiswahili and Soomaali, and the AI assistant answers in your language.

**The text is too small or too big. Can I change it?**
Yes. Go to **Settings > Text size** and move the slider. Dark mode is also there.

## How it works (for beginners)

**What language is it written in?**
Python. The screens are made with **Flet**, a Python library that builds apps for desktop, web and phone.

**Where is the data stored?**
In a small database file called `agrilink.db` (SQLite). It's created and filled with demo data the first time you run the app.

**How does the AI price prediction work?**
It looks at a year of past prices and learns the pattern: when prices usually rise, when harvest makes them drop, and whether they're trending up. Then it continues that pattern forward. On data it hadn't seen, it was off by about 2 to 3% on average.

**How does the chatbot work?**
When you ask a question, the app collects useful facts (today's prices, the forecast, your local weather and your crops) and sends them along with your question to Claude, an AI model. With no AI key, it gives simpler built-in answers from the same facts.

**Do I need to pay for anything to run it?**
No. Every paid service (AI, SMS, email, translation) is optional. Without a key, each one quietly switches to a free offline version.

**What is the `.env` file?**
It's a private settings file where you put secret keys, such as an AI key. It's never shared or uploaded. Copy `.env.example` to `.env` to start.

**Why are there three folders: Databases, UI and Auth?**
Each team member owns one:
- **Databases** stores and finds data (Person 1).
- **UI** draws the screens (Person 2).
- **Auth** handles logins and connects the outside services (Person 3).

Keeping them separate means three people can work at once without clashing.

**What is the server for?**
It's an optional online part that can send and receive real SMS messages and share market data. You only need it if you deploy the app on Render.com.

**How do I know it works?**
Run `pytest`. It runs 112 automatic checks, and they should all pass.

## Problems

**`pip install` fails on Windows with an error about pyyaml.**
Your Python is too new. Install Python 3.12, then create the venv with `py -3.12 -m venv .venv` and try again.

**The window opens but the weather says "sample".**
The app couldn't reach the weather service, usually because you're offline. It shows example weather so the screen still works.

**I forgot a demo password.**
Every demo account uses `Password123!`.

**I typed the wrong password 5 times and now I'm locked out.**
That's a safety feature. Wait 5 minutes, or restart the app.

**How do I start again with fresh demo data?**
Close the app, delete `agrilink.db`, and run `python main.py` again.
