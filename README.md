# Doppel

Doppel identifies a piece of clothing or a pair of shoes from a photo, then finds its price using that name.

The cropped photo is sent to eBay's search-by-image. The titles of the matching listings are merged into a single name. When the titles agree, the name is the brand and model, such as Nike Dunk Low Panda. When they don't, it falls back to the brand, the type, and the color, such as Levi's 501, dark blue. A model number is kept only if it appears in at least 60 percent of the titles.

Prices are searched by that name. A signed-in user has one clothes size and one shoe size, and only listings in the matching size are shown, split into new and used and sorted from cheapest to most expensive. If nothing matches, both lists are empty and the name is still returned.

A price alert tracks a name and size. Once a day, if the cheapest listing is below the saved price, the user is notified and the saved price is updated to the new one. If the price hasn't dropped, nothing is sent. Setting the same alert again saves today's lowest price.

Passwords are stored only as hashes. Prices come from the official eBay Buy Browse API. The server is written in Python and uses only the standard library.

## Run

From the `backend` folder:

```bash
python3 main.py
```

The server listens on `http://127.0.0.1:8787`.

Add the following to `backend/.env`:

```
EBAY_CLIENT_ID=
EBAY_CLIENT_SECRET=
EBAY_MARKETPLACE_ID=EBAY_US
PORT=8787
```

Use a production keyset. `backend/.env` and `backend/data` are not committed. Accounts, sizes, sessions, and alerts are stored in `backend/data/doppel.db`. eBay listings are not stored.

## Routes

POST bodies are JSON. Routes that require sign-in expect an `Authorization: Bearer <token>` header.

- `POST /register` takes `name`, `email`, and `password`, and returns a token and the user.
- `POST /login` takes `email` and `password`, and returns a token and the user.
- `POST /reset` takes `email` and a new `password`. It replaces the hash and signs out that account's sessions.
- `POST /profile` takes `clothes_size` and `shoe_size`, and returns the updated user.
- `POST /recognize` takes `image` as base64 (up to 8 MB) and returns the name, kind, label, size, and the lists of new and used listings.
- `POST /alerts` takes `name`, `kind` (`clothes` or `shoes`), and `label`. It returns the alert, or an error if there is no size or no price.
- `GET /alerts` returns the user's alerts, after running any daily check that is due.