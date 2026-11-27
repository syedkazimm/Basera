# Basera — project guide

Basera is a website for finding native plants (university Software Engineering
group project). Stack: **Django 6.1 (Python 3.14) + Bootstrap 5.3.3**, with a
local **PostgreSQL 18** database. Always go through the Django ORM; don't write
raw SQL.

- Figma source of truth: https://www.figma.com/design/kB2FzhVoebdXc99wE52fi2/Untitled
  (frames "Moss / Login", "Moss / Create account", "Moss / Forgot password").
- Requirements, use cases and the ERD: `Basera_Sprint0_Technical_Proposal_.docx`.

## Setting up and running

First time on a new computer (full details in `docs/database/README.md`):

1. `python -m venv .venv`, then `.venv/Scripts/pip install -r requirements.txt`.
2. Create the database and its user once, as the postgres superuser:
   `& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -h localhost -f docs\database\setup_postgres.sql`
   (it asks you to choose the `basera_app` password).
3. Copy `.env.example` to `.env` and put that password in `DB_PASSWORD=`.
   `.env` holds secrets and is git-ignored: never commit it.
4. `.venv/Scripts/python manage.py migrate`, then `createsuperuser` for an admin account.

Every day: `.venv/Scripts/python manage.py runserver`, then open http://127.0.0.1:8000/.
Run the tests with `.venv/Scripts/python manage.py test` (they run on PostgreSQL;
the `basera_app` role is allowed to create the test database).

## Where things live

| What | Where |
|---|---|
| Settings (reads `.env`) / root URLs | `basera_site/settings.py`, `basera_site/urls.py` |
| Users, login, sign-up, password reset | `accounts/` (`models.py`, `forms.py`, `views.py`, `urls.py`) |
| Regions, plant species (listings), species ↔ regions | `catalog/` |
| Grow profiles | `growprofiles/` |
| Cart items, orders, order items | `orders/` |
| Database docs: ERD transcription, generated `schema.sql`, setup script | `docs/database/` |
| Shared page shell (fonts, Bootstrap, header, footer, background) | `accounts/templates/accounts/base.html` |
| Design tokens + all component styles | `accounts/static/accounts/css/basera.css` |
| Show/Hide password script (reusable) | `accounts/static/accounts/js/password-toggle.js` |
| Scroll parallax + button loading state | `accounts/static/accounts/js/basera.js` |
| Background illustration | `accounts/static/accounts/img/background.png` |
| Add a plant (US-13) form, views, URLs | `catalog/forms.py`, `catalog/views.py`, `catalog/urls.py` |
| Signed-in page shell (light "botanical" look from the wireframes) | `catalog/templates/catalog/app_base.html` (extends `accounts/base.html`) |
| Styles + tokens for signed-in pages | `catalog/static/catalog/css/app.css` |
| 403 page | `accounts/templates/403.html` |
| Tests | `accounts/tests.py`, `accounts/test_views.py`, `catalog/tests.py`, `catalog/test_views.py`, `orders/tests.py` |

**Every new page should `{% extends "accounts/base.html" %}`** so it gets the
same fonts, background, header, footer and motion. Use the `basera-*` classes and
CSS variables in `basera.css`; don't hard-code colours or fonts in templates.

URL names: `login` (/), `logout` (POST only), `signup`, `forgot_password`,
`password_reset_confirm` (the emailed link), `home` (login required), `privacy`,
`terms`, `help`, `listing_add` (/seller/plants/add/, sellers only, others get 403),
`plant_detail` (/plants/<id>/). `home` is a placeholder (`accounts/templates/accounts/home.html`)
until the real Home page is built; `privacy`, `terms` and `help` use
`placeholder.html`.

## Database and authentication

- **User model:** `accounts.User` (`AUTH_USER_MODEL`). Users log in with their
  **email** (stored lower-case, unique in any letter case). It also stores
  `full_name`, `phone`, `role`, `is_active` and `date_joined`. Get the model with
  `get_user_model()` or `settings.AUTH_USER_MODEL`, never `auth.User`.
- **Roles:** `CUSTOMER`, `SELLER`, `ADMIN`.
  - The sign-up page lets people choose **Customer** or **Seller** only.
  - **Admin is never self-selected:** admins are created with `createsuperuser`,
    or an existing admin changes a user's role in `/admin/`.
  - A superuser must have the Admin role (a database rule enforces it).
  - Role ADMIN lets a user into `/admin/`, but a non-superuser admin still needs
    permissions granted there before they can see or edit anything.
  - `is_staff` is calculated from the role: you can't set it or filter on it.
    Use `user.role`, `user.is_customer` or `user.is_seller`.
- **Passwords:** hashed with **Argon2** (older PBKDF2 hashes still work and are
  upgraded on next login). Rules: at least 8 characters, not too common, not all
  numbers, not too similar to the name or email.
- **Login:** session-based. Protect pages with `@login_required`; logged-out
  users are sent to the login page and brought back after logging in.
- **Password reset:** "Forgot password?" emails a one-time link that expires in
  1 hour. Emails are printed in the `runserver` console (no real email is sent).
- **Database rules:** stock, prices and totals can't be negative, quantities are
  at least 1, and duplicate cart/order lines are rejected. Schema changes go
  through migrations (`makemigrations`, then `migrate`); never edit an applied
  migration.

## Design system ("Moss")

Start from the Figma file: login screen = node 3:425, login box = node 3:433,
create account = 3:452, forgot password = 3:484, background = 3:427. On top of
Figma, the team agreed on these additions:
- a light glass effect and a stronger shadow on the form box;
- stronger text shadows so text stands out from the illustration;
- the welcome copy raised 24px;
- a slightly taller page with a scroll parallax;
- motion.

Don't add other effects: no rounded corners and no extra accent colours.

### Colours

| Token (CSS variable) | Value | Used for |
|---|---|---|
| `--basera-bg` | `#23392d` | Page background (under the illustration) |
| `--basera-cream` | `#fffcf0` | Headings, labels, links, main text |
| `--basera-mist` | `#eff2e5` | Secondary text: subtitles, tagline, footer, hints |
| `--basera-placeholder` | `#e2e9da` | Input placeholder text |
| `--basera-input-bg` | `#2f4835` | Input fill |
| `--basera-input-border` | `#9aab8e` | Input border (1px) |
| `--basera-sage` | `#d3deaf` | Primary button fill, hover and focus accent |
| `--basera-sage-hover` | `#dde6c0` | Primary button hover |
| `--basera-forest` | `#213b29` | Primary button text |
| `--basera-panel-bg` | `rgba(69,94,74,0.28)` | Form box fill |
| `--basera-panel-border` | `rgba(153,173,141,0.3)` | Form box border (1px) |
| `--basera-divider` | `rgba(240,241,220,0.18)` | 1px divider lines |
| Error (coral) | border `#f0a58c`, text `#ffc8b6` | Invalid fields and error messages |

Background: `background.png` at **62% opacity** over `#23392d`, cover-fit,
fixed (class `.basera-backdrop`, already in `base.html`).

### Form box (glass) — `.basera-panel`

- Figma fill `--basera-panel-bg`, plus a faint diagonal sheen (`--basera-panel-sheen`).
- `backdrop-filter: blur(2px) saturate(115%)` (`--basera-panel-blur`).
- Lit edges:
  - top border `rgba(214,226,204,0.42)`;
  - left border `rgba(190,206,180,0.35)`;
  - inner top highlight (`--basera-panel-highlight`).
- Layered drop shadow (`--basera-panel-shadow`):
  `0 1px 3px rgba(10,23,15,.26), 0 10px 26px -6px rgba(10,23,15,.38), 0 30px 60px -18px rgba(10,23,15,.62)`.
- Radius **2px**, width **400px**, padding **28px × 32px**, 20px between sections.
- Modifiers:
  - `.basera-panel--compact` (12px gap, with `.basera-form--compact`, 14px) for taller forms like Create account;
  - `.basera-panel--raised` moves a tall box up 24px.

### Fonts (Google Fonts, loaded in `base.html`)

- **Bricolage Grotesque ExtraBold (800)**: display font for the logo and headings.
  Class `.basera-display`. Variation settings `"opsz" 14, "wdth" 100`.
- **DM Sans Medium (500)** for body text and **Bold (700)** for labels, links and buttons.
  Variation setting `"opsz" 14`.

| Style | Font | Size / line-height | Letter-spacing | Class |
|---|---|---|---|---|
| Logo "basera" | Bricolage 800 | 48 / 52 | -1.92px | `.basera-brand__name` |
| Hero heading | Bricolage 800 | 84 / 88 | -1.68px | `.basera-hero` |
| Panel title (keep to one line) | Bricolage 800 | 32 / 38 | -0.64px | `.basera-panel__title` |
| Lede paragraph | DM Sans 500 | 22 / 34 | | `.basera-lede` |
| Eyebrow (uppercase) | DM Sans 700 | 13 / 20 | 0.91px | `.basera-eyebrow` |
| Panel subtitle / input text | DM Sans 500 | 16 / 24 | | `.basera-panel__subtitle`, `.basera-input` |
| Field label | DM Sans 700 | 14 / 20 | | `.basera-label` |
| Hint / legal / error text | DM Sans 500 | 14 / 21 | | `.basera-hint`, `.basera-legal`, `.basera-error` |
| Button | DM Sans 700 | 16 / 22 | | `.basera-btn-primary` |
| Account switch line | DM Sans 500 (link 700, underlined) | 15 / 22 | | `.basera-switch` |
| Footer links | DM Sans 500 | 15 / 22 | | `.basera-footer__links` |
| Tagline / footer text | DM Sans 500 | 14 / 22 | | |

**Text shadows:** text over the illustration uses layered shadows so it stands out:
- the hero uses `--basera-text-pop-xl`;
- the logo and lede use `--basera-text-pop`;
- small text (eyebrow, tagline, footer) uses `--basera-text-pop-sm`.

### Spacing and layout

- Designed at **1366 × 768**. Content column is **1013px** wide (`.basera-shell`),
  16.5px left of the window's centre (measured with `100vw` so the scrollbar
  doesn't shift it).
- Page padding is 36px top, 24px bottom.
- The page is **120px taller than the window** (`--basera-scroll-room`), so it
  scrolls slightly on a laptop.
- Header 88px tall. Footer 44px tall with 24px gaps between links.
- **Auth pages:**
  - Welcome copy on the left: 532px wide, 24px gap, **80px** below the header
    (Figma has 104px, raised 24px).
  - Form box on the right, 4px below the header. The Create account box is
    raised 24px more (top at y=104) because it's taller.
- Inside the form: 16px between the field group and the button, 12px between
  fields, 6px between a label and its input.
- Inputs and buttons are **44px tall** with radius **1px** and 16px horizontal
  padding (button: 20px).
- Footer of the box: 1px divider, then 8px gap, then a 32px-tall line.
- Below 992px the layout stacks (copy above the form) and the hero shrinks.

### Form patterns

- **Field error:** add `is-invalid` to `.basera-input-wrap`, set `aria-invalid`,
  and put a `<p class="basera-error">` under the field. Keep the user's typed
  values, except passwords.
- **Notice at the top of a form:** use `.basera-notice`, or
  `.basera-notice--error` for a form-wide error. Django `messages` are shown
  through `accounts/includes/messages.html`.
- **Two-option choice** (the Customer / Seller choice on sign-up): a `<fieldset>`
  with `.basera-choice` holding two 44px `.basera-choice__option` radios. The
  chosen one turns sage.
- Forms use `novalidate`, so the server shows the styled errors instead of the
  browser's.

### Motion

Tokens: `--basera-fast` 150ms (hover/press), `--basera-medium` 250ms (focus,
toggles), `--basera-enter` 700ms (entrance), easing `--basera-ease-out` /
`--basera-spring`. The motion rules sit at the bottom of `basera.css`.

- **Page entrance:** the background fades in from a slight zoom; header, eyebrow,
  hero and lede fade up in a stagger; the form box rises in; the footer fades in.
- **Scroll parallax:** `basera.js` writes the scroll distance to `--basera-scroll`.
  The welcome copy and the box trail the page slightly and the background
  drifts up (capped). There is **no** mouse-wheel effect.
- **Inputs:** border and focus ring ease in when you click into a field.
- **Primary button:** lifts 1px on hover with a light sweep, presses down on click,
  and shows a spinner plus its `data-loading-text` while the form submits (`basera.js`).
- **Show/Hide:** label pops when it switches. Markup:
  `<button class="basera-toggle" aria-controls="<input id>">Show</button>` inside
  `.basera-input-wrap`, plus `password-toggle.js`.
- **Footer links:** underline slides in on hover.
- Animate only `transform`/`translate` and `opacity`. Keep entrance animations off
  `.basera-shell`, which carries the layout offset.
- `prefers-reduced-motion` is respected globally; keep it.
- Keep every clickable target at least 44px tall.
