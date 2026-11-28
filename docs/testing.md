# Tests

Everything the suite checks, how to run it, and how to add a case.

The project has **105 tests** in 7 files. They run against **PostgreSQL**, not
SQLite, so the database constraints (unique emails, `CHECK quantity >= 1`, and
so on) are the real ones.

---

## Running the tests

You need the setup from the top-level `README`/`CLAUDE.md`: a `.venv` with
`requirements.txt` installed, PostgreSQL running, and a `.env` with the
database settings.

```powershell
# from C:\Users\PC\Documents\GitHub\Basera
.venv\Scripts\python manage.py test
```

Expected last lines:

```
Found 105 test(s).
System check identified no issues (0 silenced).
.................................................................
Ran 105 tests in ~16s
OK
Destroying test database for alias 'default' ('test_basera')...
```

Django creates a **separate** database called `test_basera`, runs the
migrations into it, runs the tests and drops it again. Your real `basera`
database is never touched, so it is safe to run any time.

If you see `permission denied to create database`, the app role needs that
right (the setup script grants it):

```powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -h localhost -c "ALTER ROLE basera_app CREATEDB;"
```

### Running part of the suite

```powershell
.venv\Scripts\python manage.py test orders                      # one app
.venv\Scripts\python manage.py test orders.test_cart_views      # one module
.venv\Scripts\python manage.py test orders.test_cart_views.CartTests            # one class
.venv\Scripts\python manage.py test orders.test_cart_views.CartTests.test_remove_deletes_the_line   # one test
```

Useful flags:

| Flag | What it does |
|---|---|
| `-v 2` | print every test name as it runs (good for a report) |
| `--keepdb` | keep the test database between runs; much faster while you iterate |
| `--failfast` | stop at the first failure |
| `--parallel` | run in parallel (a few seconds faster here) |

---

## Where the tests live

| File | Covers |
|---|---|
| `accounts/tests.py` | user manager, password hashing, database constraints |
| `accounts/test_views.py` | sign-up, log in/out, password reset |
| `catalog/tests.py` | catalogue database constraints |
| `catalog/test_views.py` | catalogue, species pages, landing pages, seeding |
| `orders/tests.py` | cart/order database constraints |
| `orders/test_cart_views.py` | the cart: add, quantity, remove, HTMX |
| `growprofiles/tests.py` | grow profile ownership and deletion rules |

### Conventions used here

- **`@FAST_HASHERS`** (from `accounts.tests`) switches to an instant password
  hasher. Argon2 takes ~1s per hash, so every test that creates a user and is
  not *about* hashing uses it. `PasswordHashingTests` deliberately does not.
- **`make_species(seller, "Neem", stock_qty=0)`** builds a valid listing in one
  line; `make_profile()` does the same for grow profiles. Copy that pattern
  instead of repeating twenty keyword arguments.
- Tests assert on **what the page shows** (`assertContains`) and on **what the
  database holds** (`CartItem.objects.get(...)`), not on internals.
- Requests are made with `self.client` and named URLs (`reverse("cart_add", args=[pk])`),
  never hard-coded paths.
- The HTMX variants pass `HTTP_HX_REQUEST="true"` and assert the fragment comes
  back instead of a redirect.

---

## The test cases

Grouped by area, with the test method that implements each one. IDs are for
reports and don't appear in the code.

### Accounts — sign up (`accounts/test_views.py::SignUpViewTests`)

| ID | Test case | Expected |
|---|---|---|
| A1 | Open the sign-up page | Page shows the Customer/Seller choice with Customer preselected |
| A2 | Sign up as a customer | Account created, logged in, lands on the customer home |
| A3 | Sign up as a seller | Account created with the Seller role |
| A4 | Try to sign up as admin | Rejected — admin is never self-selected |
| A5 | Sign up with an email already used, in different letter case | Rejected as a duplicate |
| A6 | Sign up with a weak password (`12345678`) | Rejected with the reason shown |
| A7 | Sign up with a password similar to the name | Rejected |
| A8 | Submit with blank fields | Errors shown, typed values kept |
| A9 | Submit any sign-up form | The password is never echoed back into the HTML |

### Accounts — log in and out (`LoginLogoutViewTests`)

| ID | Test case | Expected |
|---|---|---|
| L1 | Log in with the email in a different case | Works, lands on home |
| L2 | Log in with the wrong password | One generic error, no hint which field |
| L3 | Log in with an unknown email | Same generic error |
| L4 | Log in as a deactivated user | Refused |
| L5 | Open a protected page while logged out | Sent to log in, returned to that page afterwards |
| L6 | `?next=https://other-site/` | Ignored, no open redirect |
| L7 | Log out | Only via POST, with a confirmation message |
| L8 | Visit login/sign-up while logged in | Redirected to home |

### Accounts — password reset (`PasswordResetViewTests`)

| ID | Test case | Expected |
|---|---|---|
| P1 | Request a reset for a known email | Link is emailed (printed in the console) and resets the password |
| P2 | Request a reset for an unknown email | Same response, nothing sent — doesn't reveal accounts |
| P3 | Enter a malformed email | Form error |
| P4 | Open a tampered/expired link | "Expired" page, no crash |

### Accounts — hashing and the user manager (`accounts/tests.py`)

| ID | Test case | Expected |
|---|---|---|
| H1 | Log in with an old PBKDF2 hash | Works, and the hash is upgraded to Argon2 |
| H2 | Create a user | Password stored hashed, never in plain text |
| U1 | `create_user` with `" ANA@Example.COM "` | Stored as `ana@example.com` |
| U2 | Check the stored password | Argon2 hash, not the raw password |
| U3 | Authenticate with different letter case | Succeeds |
| U4 | `get_by_natural_key` with odd case | Normalises and finds the user |
| U5 | Email of only spaces | Rejected |
| U6 | Blank full name | Rejected |
| U7 | Full name with spaces around it | Stored trimmed |
| U8 | `create_superuser` | Role is Admin, `is_staff` follows |
| U9 | `create_superuser` with another role | Rejected |

### Accounts — database rules (`UserConstraintTests`)

| ID | Test case | Expected |
|---|---|---|
| C1 | Two users, same email | Second insert fails at the database |
| C2 | Duplicate email through `create_user` | Fails |
| C3 | Emails differing only by case, inserted directly | Fails on the unique constraint |
| C4 | Empty full name inserted directly | Fails on the check constraint |
| C5 | Unknown role inserted directly | Fails |
| C6 | Superuser whose role isn't Admin | Fails |

### Catalogue (`catalog/test_views.py::CatalogueTests`)

| ID | Test case | Expected |
|---|---|---|
| K1 | Guest opens the catalogue | 200, only active listings, inactive hidden |
| K2 | 15 listings, page 1 and 2 | 12 then 3, with "Showing 1–12 of 15" |
| K3 | Search `nEEm` | Matches common *or* scientific name, case-insensitively |
| K4 | Search with no match | "No plants match …" and a way to clear it |
| K5 | Search then page 2 | The search term is kept |
| K6 | Same request with `HX-Request` | Returns only the results partial |
| K7 | Invasive listing in the grid | Flagged, no buy button |
| K8 | Out-of-stock listing | Listed, "Out of stock", cannot be added |
| K9 | Guest clicks add-to-cart | Sent to log in, then back to that plant |
| K10 | Seller browses the catalogue | No buy button at all |

### Species page (`SpeciesDetailTests`)

| ID | Test case | Expected |
|---|---|---|
| S1 | Open a species | Name, scientific name, price, stock, chips, facts, tabs |
| S2 | Open an inactive or missing species | 404 |
| S3 | Invasive species | Warning banner, no add-to-cart |
| S4 | Out-of-stock species | No add-to-cart |
| S5 | Customer vs guest | Customer sees "Add to cart", guest sees "Log in to add to cart" |
| S6 | "You may also like" | Never includes itself or an invasive plant |

### Landing pages (`LandingPlaceholderTests`, `LandingPageContentTests`)

| ID | Test case | Expected |
|---|---|---|
| LP1 | Log in as each role | Each lands on its own page, which links to the catalogue |
| LP2 | Header placeholder pages | All load with 200 |
| LC1 | Customer home | Five featured plants, all native and non-invasive |
| LC2 | Seller home | Only that seller's own numbers |
| LC3 | Admin home | Platform-wide numbers |
| SEED | `manage.py seed_catalog` twice | 35 species, 5 regions, no duplicates |

### Catalogue and order database rules (`catalog/tests.py`, `orders/tests.py`)

| ID | Test case | Expected |
|---|---|---|
| CC1 | Stock of `-1` | Rejected |
| CC2 | Price of `-1` | Rejected |
| CC3 | Unknown `setting` value | Rejected |
| CC4 | Two regions with the same name | Rejected |
| CC5 | Same species+region twice | Rejected |
| O1 | New order | Status Pending, payment COD, no grow profile |
| O2 | Cart quantity `0` | Rejected |
| O3 | Two cart rows for one user+species | Rejected |
| O4 | Order item quantity `0` | Rejected |
| O5 | Order item with a negative unit price | Rejected |
| O6 | Same species twice in one order | Rejected |
| O7 | Order total `-0.01` | Rejected |

### Cart (`orders/test_cart_views.py::CartTests`)

| ID | Test case | Expected |
|---|---|---|
| CART1 | Add a plant | One line, quantity 1, "… is in your cart." |
| CART2 | Add the same plant again | Quantity 2, still one line |
| CART3 | Add 5 when stock is 2 | Capped at 2, "that's all that's left in stock" |
| CART4 | Add the last one again | Stays at 1, "already in your cart" |
| CART5 | Stock drops below what the cart holds | Adding never lowers the quantity; says only N are left |
| CART6 | Add an invasive plant | Refused, nothing stored |
| CART7 | Add an out-of-stock plant | Refused |
| CART8 | Add a hidden listing | 404 |
| CART9 | Guest adds to cart | Redirect to log in, nothing stored |
| CART10 | Seller adds to cart | Refused: "Only customer accounts can shop" |
| CART11 | Add with `next` | Returns to that page |
| CART12 | `next` pointing at another site | Ignored, safe fallback |
| CART13 | Press + then − | Quantity 2 → 3 → 2 |
| CART14 | Press − at quantity 1 | Stays 1, line is not deleted |
| CART15 | Press + at the stock limit | Stays at stock, "only 3 … in stock" |
| CART16 | Post an explicit `quantity` | Set to that number |
| CART17 | Remove a line | Line deleted, "… removed from your cart." |
| CART18 | Remove a plant that isn't there | Harmless, tells you |
| CART19 | Cart page | Lists each line with its unit price and line total (2 × 450 = Rs 900) |
| CART20 | Cart holds a plant that sold out | Line flagged "No longer available" |
| CART21 | Empty cart page | "Your cart is empty." and a link to the catalogue |
| CART22 | Header badge | Shows the number of plants (3 → `3`) |
| CART23 | Cart page while logged out | Redirect to log in |
| CART24 | Add with `HX-Request` | 200 fragment, header link swapped, message in `HX-Trigger`, no redirect |
| CART25 | + with `HX-Request` | Cart body fragment with the new quantity and total |
| CART26 | Stepper at the limit with `HX-Request` | Quiet on success, but the limit message is sent |
| CART27 | Remove the last line with `HX-Request` | Empty state comes back in the fragment |
| CART28 | Guest with `HX-Request` | 204 + `HX-Redirect`, so the browser navigates |
| CART29 | GET on add/update/remove | 405 for each |

### Grow profiles (`growprofiles/tests.py`)

| ID | Test case | Expected |
|---|---|---|
| G1 | Create a profile | Belongs to its user; `str()` names it and its owner |
| G2 | Delete the user | Profiles go with them (CASCADE) |
| G3 | Delete a region that a profile uses | Blocked (PROTECT) |
| G4 | List profiles | Most recently updated first |

---

## What is *not* covered

Worth knowing before a review, and good candidates for later:

- **No browser tests.** The HTMX behaviour (no reload, toast, focus) is checked
  at the view level (CART24–CART28) but the JavaScript itself is only verified
  by hand. Playwright or Selenium would close that gap.
- **No coverage measurement.** `coverage.py` is not installed; if you want a
  percentage, `pip install coverage` then
  `coverage run manage.py test && coverage report`.
- **Checkout** has no tests because it does not exist yet — the order is still
  "coming soon".
- **Seeded demo passwords** are not asserted (the command prints a random one
  per new account).
- **Email** is not sent for real; the reset link is printed in the console, and
  that is what P1 checks.

---

## Adding a test

The short version: put the test in the app it belongs to, use the helpers
above, and run it.

```python
# catalog/tests.py
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.tests import FAST_HASHERS

from .models import PlantSpecies

User = get_user_model()


@FAST_HASHERS
class MyNewTests(TestCase):
    def test_price_shows_on_the_card(self):
        seller = User.objects.create_user("s@basera.test", "x", full_name="Sam", role=User.Role.SELLER)
        neem = PlantSpecies.objects.create(
            seller=seller, common_name="Neem", scientific_name="Azadirachta indica",
            light_need="Full sun", water_need="Low", suitable_soils="Loam",
            setting=PlantSpecies.Setting.OUTDOOR, price=Decimal("450.00"), stock_qty=3,
        )

        response = self.client.get(reverse("catalogue"))

        self.assertContains(response, "Rs 450")
```

Then:

```powershell
.venv\Scripts\python manage.py test catalog.tests.MyNewTests -v 2
```

Rules of thumb that keep this suite readable:

1. **One behaviour per test**, named after the behaviour
   (`test_quantity_is_capped_by_stock`, not `test_cart_2`).
2. **A failing test should tell you what broke** — assert the message or the
   number, not just the status code.
3. **Don't weaken an assertion to make it pass.** If the code is wrong, fix the
   code; if the test encoded an old rule, say so in a comment (see
   `catalog/test_views.py`, where `cart` left the placeholder list).
4. **Set up only what the test needs.** `setUp` runs before every test in the
   class, so keep it small and put one-off data inside the test.
