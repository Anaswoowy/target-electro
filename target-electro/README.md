# Target Electro — Prototype

A scoped-down, actually-runnable prototype of the Target Electro spec.
Built and tested end-to-end (see "What I tested" below) — not a mockup.

## Stack (and why)

- **Flask** (Python) — small, transparent, no build step.
- **SQLite via Python's built-in `sqlite3`** — no ORM dependency, so
  there's nothing extra to install beyond Flask itself. The database is
  the real source of truth; nothing is hardcoded in templates or JS.
- **Server-rendered Jinja templates, RTL Arabic** — no frontend framework/
  build tooling, so you can read and change any page directly.
- **Vanilla JS** for the AI side-panel and the admin dynamic spec form —
  no bundler needed.
- **Rule-based "Target AI"** (regex + keyword matching over the real
  database) instead of calling an LLM — by construction it can never
  invent a product, price, or spec, satisfying the spec's "never
  hallucinate" requirement without needing any API key.

## Run it

```bash
cd target-electro
pip install -r requirements.txt      # just Flask
python seed.py                       # required: admin user + categories/types (empty store)
# OR, to see the storefront with sample data:
python seed.py --with-demo

python app.py
```

Open **http://127.0.0.1:5000**
Admin panel: **http://127.0.0.1:5000/admin/login** — username `admin`,
password `target1323` (change this — see "Security" below).

To wipe the 3 demo products later: `python seed.py --clear-demo`.

## What's actually implemented (and tested)

- Empty-state-safe homepage — sections only render when real data exists,
  otherwise a clean "لا توجد ..." message (no fake content, ever).
- Category → product type → **dynamic spec fields**, fully working for
  three product types end-to-end: Smartphone, TWS Earbuds, Laptop
  (`PRODUCT_TYPE_FIELDS` in `app.py`).
- Product listing with real filters (category, type, brand, price) + sort
  + keyword search.
- Product detail page — only displays spec rows that actually have a value.
- Cart + checkout (COD only), **server-side stock validation** — the
  backend re-reads price/stock/visibility at checkout, never trusts the
  cart session blindly, and rejects/rolls back if stock changed.
- Order tracking page + admin order management with status transitions;
  cancelling an order restores stock.
- Admin: hashed-password login (Werkzeug `generate_password_hash`),
  session-gated `/admin/*` routes, product CRUD (add/edit/delete/duplicate),
  category & product-type management, brand management.
- Target AI: parses Arabic budget phrases ("300 ألف", "بحدود 500 ألف"),
  detects category and brand keywords, queries the live DB, and only ever
  returns real, in-stock, visible products (or an honest "no match" message).
- Demo/seed data is isolated with an `is_demo` flag and a one-command
  removal path, per the spec's "temporary technical seed data" rule.

I ran the full flow before handing this over: seeded the DB, hit every
public route, added an item to cart, checked out (confirmed the total and
stock decrement), logged into admin, created a product with specs, confirmed
it appeared on the storefront, and confirmed an admin route is unreachable
without a valid session.

## What's deliberately NOT in this prototype

This is a prototype of the architecture and rules, not the full spec —
building the entire spec (every product-type schema, image pipeline,
race-condition-hardened inventory, rate limiting, full responsive polish,
the real logo/location) is realistically a multi-week build. Specifically
left out:

- **Real logo / store location** — `static/img/logo-placeholder.svg` is a
  text placeholder. Drop your real logo file into `static/img/` and swap
  the path in `templates/base.html` (2 occurrences) and `templates/admin/base.html`.
  Add a `location` field to `Category`... actually add it to a `Settings`
  table (doesn't exist yet — see "Extend first" below) once you have the
  real address.
- **Remaining product-type schemas** — Gaming Mouse, Gaming Keyboard, TV,
  and everything else listed in the spec. The pattern is proven with 3
  types; adding more is mechanical (see below).
- **Image upload pipeline** — currently just a comma-separated URL field
  in the admin form. No file upload, resizing, or lazy-loading yet.
- **Hardened inventory concurrency** — stock is decremented inside a
  single SQLite transaction per checkout, which is safe for one process,
  but there's no row-level locking for concurrent checkouts under load
  (SQLite's default isolation handles most of this, but a production
  deployment should move to Postgres with `SELECT ... FOR UPDATE`).
- **Rate limiting on admin login.**
- **Mobile-specific breakpoint polish** — the CSS is responsive (grid
  reflow, bottom nav) but not pixel-tuned against the exact 390×844 /
  768×1024 / 1366×768 targets the spec calls out.
- **Guest vs. account distinction** — there's no account system at all
  yet; checkout is currently guest-only (which matches the spec's
  requirement that guest checkout must work, just without the optional
  account layer on top).

## What I'd extend first

1. **Add a `Settings` table** (key/value or a single-row table) for store
   name, location, delivery info, AI welcome message, admin password
   change — right now those are either hardcoded placeholders or absent.
   This unblocks "real store location" and "AI admin settings" from the spec.
2. **Add the remaining product types.** Pattern per type: add an entry to
   `PRODUCT_TYPE_FIELDS` in `app.py` (list of `(key, arabic_label)` tuples),
   then create the type via `/admin/categories`. No schema migration
   needed — specs are stored as flexible key/value rows.
3. **Real image upload** — swap the `images` text field for a file input,
   save to `static/uploads/`, generate a couple of resized versions.
4. **Move Target AI from keyword-matching to something more forgiving of
   phrasing** while keeping the "only real DB rows" guarantee — e.g. use
   an LLM purely to *extract structured filters* (budget, category, specs)
   from the Arabic sentence, then run those filters through the exact same
   SQL query used now. That keeps hallucination-proofing intact since the
   LLM never sees or invents product data, it only parses intent.
5. **Postgres + connection pooling** once you're past prototype stage —
   the sqlite3 layer here is intentionally simple (functions returning
   plain Python objects, not an ORM), so swapping the `get_db()`/query
   functions for `psycopg2` is a contained change; templates don't need
   to touch it.
6. **Admin password change UI** and moving `SECRET_KEY` /
   `ADMIN_PASSWORD` out of source into environment variables for any
   real deployment (`os.environ` hooks are already there for `SECRET_KEY`).

## Project layout

```
target-electro/
  app.py              # routes, data-access helpers, Target AI engine
  seed.py             # required setup + optional isolated demo data
  requirements.txt
  templates/          # storefront (RTL Arabic) + templates/admin/
  static/css/style.css
  static/js/main.js   # AI panel + admin dynamic spec form
  static/img/         # logo placeholder — swap with the real asset
  instance/store.db   # SQLite database (created on first run)
```
