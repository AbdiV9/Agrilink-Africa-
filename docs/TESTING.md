<!-- Owner: Person 3 (Integration, Logic & API Lead) -->
# What to test for a good user experience

Run `pytest` first. It should report 112 passed. Then work through this list by hand with `python main.py`. Try each part twice: once at a **phone-sized window (about 390 px wide)** and once **maximised**, in **light** and **dark** mode.

## 1. First impressions (most important)
- [ ] The app opens in under about 5 seconds, straight to the login screen
- [ ] All text is easy to read: no pale grey on white, and nothing hard to see in dark mode
- [ ] Nothing is cut off or overlapping at phone width; long crop names end in "…" instead of spilling over
- [ ] Buttons are big enough to tap with a thumb

## 2. Login and accounts
- [ ] The username and password boxes have clear labels and dark text
- [ ] The password shows as dots; **Show password** reveals it, and unticking hides it again
- [ ] A wrong password shows a clear red message with the number of tries left
- [ ] 5 wrong tries lock the account for 5 minutes, and the message says so
- [ ] Register with mistakes (short username, bad email, a phone number without +254, weak password) and check each box shows its own error
- [ ] After registering, you can log in with the new account
- [ ] The **Logout** icon is at the top right of Home, Market, Sell, Messages and Settings; it asks "Log out?" and goes back to login
- [ ] After logging out, the back button can't get back into the app

## 3. Main tasks (can someone do these without help?)
- [ ] **Find a crop**: search "maize" in Market, filter by price, and sort cheapest first
- [ ] **Check a price**: open a crop and switch 1W, 1M, 3M and 1Y; the chart and % change update
- [ ] **See the forecast**: turn on **Show AI prediction** and a dashed line appears
- [ ] **Sell**: list a crop; empty or wrong boxes show an error; the new listing appears in Market
- [ ] **Buy**: buy part of a listing; the amount left goes down; it appears in **Settings > Purchase history**
- [ ] **Message a seller**: the message is pre-filled; send it; the seller sees the unread badge
- [ ] **Price alert**: set one just below today's price; a 🔔 message appears within the check time
- [ ] **Ask the AI**: tap each suggestion button; an answer appears and the app doesn't freeze while it waits

## 4. Settings and accessibility
- [ ] Move the **text size** slider to the largest size; text, icons, buttons and pictures all grow together and nothing is cut off
- [ ] **Dark mode** switches straight away and is remembered after logging out and back in
- [ ] Switch the **language** to Kiswahili or Soomaali, and the menus change
- [ ] Edit your details with a bad email and check the error appears next to the box

## 5. When things go wrong
- [ ] Turn off Wi-Fi: weather and news show sample data, and nothing crashes
- [ ] Use the app with no `.env` keys: the chatbot still answers (offline mode), and SMS and email say "logged"
- [ ] Put a wrong AI key in `.env`: the chatbot shows "⚠️" plus a helpful offline answer, not a crash
- [ ] Open a page that doesn't exist (for example `/crop/9999`): you get a friendly message and a way back

## 6. Speed and feel
- [ ] Moving between tabs feels instant
- [ ] Weather and news load in the background, with a spinner instead of a frozen screen
- [ ] The back arrow always goes somewhere sensible

## How to report a problem
Write down the screen, what you tapped, what you expected and what happened, plus any red error text from the terminal. Then send it to the person who owns that folder (see the README).
