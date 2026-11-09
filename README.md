# Doppel

Doppel names a piece of clothing or a pair of shoes from a photo, then looks up the price by that name.

The crop goes to eBay search by image. The listing titles become one name. If the titles agree, that name is the brand and model, such as Nike Dunk Low Panda. If they do not, it is the brand, the type, and the color, such as Levi's 501, dark blue. A model number is kept only when the same number is in at least 60 percent of the titles.

Prices are searched by the name. A signed-in user has one clothes size and one shoe size, and only listings in that size are shown, split into new and used, cheapest first. If nothing matches, both lists are empty and the name stays.

An alert watches that name and size. Once a day, if the cheapest listing is below the saved price, the user is told and the saved price becomes the new one. If it did not drop, nothing is sent. Setting the same alert again stores today's lowest price.

The password is stored only as a hash. Prices come from the official eBay Buy Browse API. The server is Python and uses only the standard library.

## Run

From `backend`:

```bash
python3 main.py
```

The server listens on `http://127.0.0.1:8787`.

Put this in `backend/.env`:

```
EBAY_CLIENT_ID=
EBAY_CLIENT_SECRET=
EBAY_MARKETPLACE_ID=EBAY_US
PORT=8787
```

Use a production keyset. `backend/.env` and `backend/data` are not committed. Users, sessions, and alerts are stored in `backend/data`.

## Routes

POST bodies are JSON. Signed-in routes send `Authorization: Bearer <token>`.

- `POST /register` takes `name`, `email`, and `password`, and returns a token and the user.
- `POST /login` takes `email` and `password`, and returns a token and the user.
- `POST /profile` takes `clothes_size` and `shoe_size`, and returns the user.
- `POST /recognize` takes `image` as base64, up to 8 MB, and returns the name, kind, label, size, and the new and used listings.
- `POST /alerts` takes `name`, `kind` (`clothes` or `shoes`), and `label`. It returns the alert, or an error when there is no size or no price.
- `GET /alerts` returns this user's alerts, after any daily check that is due.
