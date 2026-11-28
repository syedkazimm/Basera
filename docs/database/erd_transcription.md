# ERD transcription

## Source

- Document: `Basera_Sprint0_Technical_Proposal_.docx` (project root).
- Section **4. Entity Relationship Diagram (ERD)**, "Figure 2. Basera entity
  relationship diagram". In the .docx this is `word/media/image2.png`
  (relationship `rId6`). It was legible at full size; no text had to be guessed.
- Section text: "Covers the 3 required CRUD entities (Grow Profile, Plant Species /
  Listing, Order) plus the supporting entities User, Region, SpeciesRegion,
  CartItem and OrderItem."
- Other figures were not used for the schema: `image1.png` is the use case
  diagram (Figure 1), `image3.png` the architecture (Figure 3). Figure 3 and
  section 5 were used only for the app split (accounts, growprofiles, catalog,
  matching, cart & orders).

The ERD gives entity names, attribute names, PK/FK markers, a few
annotations (`unique`, `nullable`, value lists) and crow's-foot cardinalities.
It gives **no data types, lengths or NOT NULL markers**; those decisions are listed
under each entity and in "Decisions" below.

## Entities as drawn

`PK` = primary key, `FK` = foreign key. Annotations in brackets are copied from the diagram.

### User (8 attributes)
| ERD attribute | Notes in ERD |
|---|---|
| PK id | |
| email | (unique) |
| password_hash | |
| full_name | |
| phone | |
| role | (CUSTOMER/SELLER/ADMIN) |
| is_active | |
| date_joined | |

### GrowProfile (12)
PK id, FK user_id, FK region_id, name, space_type, sunlight, soil_type,
water_availability, purpose, created_at, updated_at.

### Region (4)
PK id, name (unique), description, climate_zone.

### SpeciesRegion (3)
PK id, FK species_id, FK region_id.

### PlantSpecies (Listing) (16)
PK id, FK seller_id, common_name, scientific_name, description, light_need,
water_need, suitable_soils, setting (indoor/outdoor/both), ecological_role,
is_invasive, price, stock_qty, image, is_active, created_at.

### CartItem (5)
PK id, FK user_id, FK species_id, quantity, added_at.

### Order (11)
PK id, FK user_id, FK grow_profile_id (nullable), status, delivery_name,
delivery_address, city, phone, payment_method, total_amount, placed_at.

### OrderItem (5)
PK id, FK order_id, FK species_id, quantity, unit_price.

## Relationships as drawn

Crow's-foot ends read: `||` exactly one, `o|` zero or one, `o<` zero or many, `|<` one or many.

| # | Label | From (end) | To (end) | Meaning | FK column |
|---|---|---|---|---|---|
| 1 | creates | User `\|\|` | GrowProfile `o<` | a user has 0..n grow profiles; each profile has exactly 1 user | GrowProfile.user_id |
| 2 | located in | GrowProfile `o<` (`>o`) | Region `\|\|` | a profile is in exactly 1 region; a region has 0..n profiles | GrowProfile.region_id |
| 3 | (unlabelled) | Region `\|\|` | SpeciesRegion `o<` | a region has 0..n links | SpeciesRegion.region_id |
| 4 | (unlabelled) | PlantSpecies `\|\|` | SpeciesRegion `o<` | a species has 0..n links | SpeciesRegion.species_id |
| 5 | has cart | User `\|\|` | CartItem `o<` | a user has 0..n cart items | CartItem.user_id |
| 6 | (unlabelled) | PlantSpecies `\|\|` | CartItem `o<` | a species is in 0..n cart items | CartItem.species_id |
| 7 | places | User `\|\|` | Order `o<` | a user places 0..n orders | Order.user_id |
| 8 | used for | GrowProfile `o\|` | Order `o<` | an order optionally references 0..1 grow profile; a profile is used for 0..n orders | Order.grow_profile_id (nullable) |
| 9 | contains | Order `\|\|` | OrderItem `\|<` | an order has **1..n** items; each item has exactly 1 order | OrderItem.order_id |
| 10 | sold as | PlantSpecies `\|\|` | OrderItem `o<` | a species appears in 0..n order items | OrderItem.species_id |
| 11 | sells (seller) | User `\|\|` | PlantSpecies `o<` | a (seller) user has 0..n listings; each listing has exactly 1 seller | PlantSpecies.seller_id |

Relationships 3+4 make SpeciesRegion the many-to-many junction between
PlantSpecies and Region.

Drawing note: the "used for" line leaves GrowProfile beside the `created_at`
row. That is only line routing; the relationship is GrowProfile to Order through
`Order.grow_profile_id`.

## Implementation (Django)

Apps follow the architecture in section 5 / Figure 3: `accounts`, `growprofiles`,
`catalog`, `orders` ("cart & orders"). `matching` is a service with no tables, so
no app was created for it yet.

Table names: the ERD names entities, not tables, so Django's default
`<app>_<model>` names are kept (this also avoids the reserved words `user` and
`order` in PostgreSQL).

| ERD entity | Django model | Table |
|---|---|---|
| User | `accounts.User` (`AUTH_USER_MODEL`) | `accounts_user` |
| GrowProfile | `growprofiles.GrowProfile` | `growprofiles_growprofile` |
| Region | `catalog.Region` | `catalog_region` |
| SpeciesRegion | `catalog.SpeciesRegion` | `catalog_speciesregion` |
| PlantSpecies (Listing) | `catalog.PlantSpecies` | `catalog_plantspecies` |
| CartItem | `orders.CartItem` | `orders_cartitem` |
| Order | `orders.Order` | `orders_order` |
| OrderItem | `orders.OrderItem` | `orders_orderitem` |

All `id` columns are `bigint` identity (`BigAutoField`, Django 6.1's default).
Exact DDL: `schema.sql`.

### Column types

Rule used everywhere: the ERD marks only `grow_profile_id` as nullable, so
**every other column is NOT NULL**. Optional free-text fields use `blank=True`
(empty string allowed, still NOT NULL), per Django convention for text.

**accounts_user**
| ERD | Column | Type | Constraints / default |
|---|---|---|---|
| id | id | bigint identity | PK |
| email | email | varchar(254) | UNIQUE, plus unique index on `LOWER(email)`; stored lower-cased |
| password_hash | password | varchar(128) | Django salted hash (PBKDF2 by default), set only via `set_password()` |
| full_name | full_name | varchar(150) | required |
| phone | phone | varchar(20) | may be empty |
| (not in ERD) | default_address | text | may be empty; database default '' (D17) |
| (not in ERD) | default_city | varchar(60) | may be empty; database default '' (D17) |
| role | role | varchar(10) | CHECK in ('CUSTOMER','SELLER','ADMIN'); default CUSTOMER |
| is_active | is_active | boolean | default true |
| date_joined | date_joined | timestamptz | default now |
| (not in ERD) | | | CHECK `full_name <> ''`; CHECK `NOT is_superuser OR role = 'ADMIN'` (D11, D12) |
| (not in ERD) | last_login | timestamptz NULL | required by Django auth |
| (not in ERD) | is_superuser | boolean | required by `PermissionsMixin` |
| (not in ERD) | tables `accounts_user_groups`, `accounts_user_user_permissions` | | required by `PermissionsMixin` (admin permissions) |

**catalog_region**: name varchar(100) UNIQUE; description text (may be empty);
climate_zone varchar(100) (may be empty).

**catalog_plantspecies**
| Column | Type | Constraints / default |
|---|---|---|
| seller_id | bigint FK -> accounts_user | NOT NULL, indexed |
| common_name | varchar(150) | |
| scientific_name | varchar(200) | not unique (see decision D6) |
| description | text | may be empty |
| light_need | varchar(50) | |
| water_need | varchar(50) | |
| suitable_soils | varchar(255) | |
| setting | varchar(10) | CHECK in ('INDOOR','OUTDOOR','BOTH') |
| ecological_role | varchar(255) | may be empty |
| is_invasive | boolean | default false |
| price | numeric(10,2) | CHECK >= 0 |
| stock_qty | integer | CHECK >= 0 (from `PositiveIntegerField`), default 0 |
| image | varchar(100) | `ImageField`: path under `MEDIA_ROOT/species/`; may be empty |
| is_active | boolean | default true |
| created_at | timestamptz | set on insert |

**catalog_speciesregion**: species_id FK, region_id FK, both NOT NULL and indexed;
UNIQUE (species_id, region_id). Exposed as `PlantSpecies.regions` /
`Region.species` (a `ManyToManyField` using this table as `through`).

**growprofiles_growprofile**: user_id FK, region_id FK (NOT NULL, indexed);
name varchar(100); space_type, sunlight, soil_type, water_availability
varchar(50); purpose varchar(100); created_at (set on insert), updated_at (set on
every save) timestamptz.

**orders_cartitem**: user_id FK, species_id FK; quantity integer CHECK >= 1,
default 1; added_at timestamptz (set on insert); UNIQUE (user_id, species_id).

**orders_order**
| Column | Type | Constraints / default |
|---|---|---|
| user_id | bigint FK | NOT NULL, indexed |
| grow_profile_id | bigint FK | **NULL** allowed (ERD), indexed |
| status | varchar(20) | default PENDING (values: decision D3) |
| delivery_name | varchar(150) | |
| delivery_address | varchar(255) | |
| city | varchar(100) | |
| phone | varchar(20) | |
| payment_method | varchar(20) | default COD (decision D4) |
| total_amount | numeric(10,2) | CHECK >= 0 |
| placed_at | timestamptz | set on insert |

**orders_orderitem**: order_id FK, species_id FK; quantity integer CHECK >= 1;
unit_price numeric(10,2) CHECK >= 0; UNIQUE (order_id, species_id).

### Foreign keys and on_delete

PostgreSQL FKs are created by Django as `DEFERRABLE INITIALLY DEFERRED` without
an `ON DELETE` clause; the behaviour below is applied by the ORM. Deleting a
referenced row with raw SQL is rejected by PostgreSQL.

| FK | on_delete | Reason |
|---|---|---|
| GrowProfile.user | CASCADE | profiles are private to their user |
| GrowProfile.region | PROTECT | Region is reference data; don't delete one that is in use |
| SpeciesRegion.species / .region | CASCADE | a link row means nothing without both ends |
| PlantSpecies.seller | PROTECT | listings may be in orders; deactivate the seller (`is_active`) instead of deleting |
| CartItem.user | CASCADE | cart belongs to the user |
| CartItem.species | CASCADE | a removed listing just leaves the cart |
| Order.user | PROTECT | orders are business records; deactivate users instead |
| Order.grow_profile | SET_NULL | ERD marks it nullable; deleting a profile keeps the order |
| OrderItem.order | CASCADE | items are part of the order |
| OrderItem.species | PROTECT | keep order history; hide listings with `is_active = false` |

Every FK column has an index (Django adds them automatically).

## Ambiguities and decisions

- **D1. No data types in the ERD.** Types and lengths were chosen as in the tables
  above: money as `numeric(10,2)` (never float), counts as non-negative integers,
  timestamps as `timestamptz` (`USE_TZ = True`), flags as boolean, free text as
  `text`, short labels as `varchar`.
- **D2. password_hash.** Implemented as Django's built-in `password` column, which
  stores a salted hash (`algorithm$iterations$salt$hash`). There is no plain-text
  password column. This also satisfies the proposal's NFR "Passwords shall be
  stored only as salted hashes".
- **D3. Order.status values not listed in the ERD.** Working set: `PENDING`
  (default), `CONFIRMED`, `SHIPPED`, `DELIVERED`, `CANCELLED`. These are Django
  `choices` only (validated by forms/admin), with **no** DB CHECK, because they were
  not specified and the team may change them.
- **D4. Order.payment_method values not listed.** The proposal's scope says Cash on
  Delivery only, so the only choice is `COD` (default). Choices only, no DB CHECK,
  so other methods can be added later.
- **D5. Value lists the ERD does give** (User.role, PlantSpecies.setting) are
  enforced with DB CHECK constraints as well as `choices`. Stored values are upper
  case (`INDOOR`/`OUTDOOR`/`BOTH`) to match the style of `role`; labels shown to
  users are "Indoor"/"Outdoor"/"Both".
- **D6. No other uniqueness is marked**, so `scientific_name` / `common_name` are
  not unique (an entity named "Listing" suggests two sellers may list the same
  species).
- **D7. Implied uniqueness on junction / line tables.** Added
  UNIQUE(species, region) on SpeciesRegion, UNIQUE(user, species) on CartItem (one
  cart line per species; change the quantity instead) and UNIQUE(order, species) on
  OrderItem. These are not drawn in the ERD; they follow from what the tables mean.
- **D8. Quantities and money.** CHECK quantity >= 1 (CartItem, OrderItem),
  stock_qty >= 0 (the proposal's NFR "stock shall never fall below zero"),
  price / unit_price / total_amount >= 0.
- **D9. GrowProfile matching attributes** (space_type, sunlight, soil_type,
  water_availability, purpose) and PlantSpecies light_need, water_need,
  suitable_soils have **no value lists** in the ERD. They are plain `varchar` with
  no `choices`, so the matching feature owner can define the vocabularies later
  (adding `choices` later is a migration with no DB change). `suitable_soils` is
  plural; it is stored as one text field (for example a comma-separated list)
  rather than a PostgreSQL array, to keep the code database-independent.
- **D10. Email is case-insensitive.** The manager and `save()` strip surrounding
  whitespace and lower-case the whole address; login (`get_by_natural_key`)
  normalises the typed email the same way and matches it exactly; a unique index
  on `LOWER(email)` enforces it in the database as well. A blank or
  whitespace-only email is rejected by `create_user` (ValueError).
- **D11. Sign-up page fields.** "Your name" maps to `full_name`, then `email` and
  password. `phone` may be empty because sign-up does not ask for it; `role` defaults
  to CUSTOMER. `full_name` is required: `create_user` strips it and raises
  ValueError if it is blank, and CHECK `accounts_user_full_name_not_empty`
  (`full_name <> ''`) rejects an empty string in the database. Password rules
  (settings): minimum length 8 (matches the sign-up hint "At least 8 characters.")
  and not too similar to `email` / `full_name`.
- **D12. Fields Django auth requires that the ERD lacks:** `last_login`,
  `is_superuser`, and the groups/permissions link tables. `is_staff` is **not** a
  column: it is a read-only property, true for active users with role ADMIN or
  `is_superuser`, so admin-site access follows the ERD's `role`. `createsuperuser`
  sets role ADMIN and `is_superuser`. Side effects of the property:
  `is_staff=` cannot be passed to `create_user()` / `User(...)` and querysets
  cannot filter on `is_staff` (use `role="ADMIN"`); role ADMIN only grants
  admin-site *login*, so a non-superuser ADMIN still needs model permissions
  (groups / user permissions) to see or change data there. CHECK
  `accounts_user_superuser_is_admin` (`NOT is_superuser OR role = 'ADMIN'`) keeps
  `is_superuser` consistent with the ERD's role.
- **D13. Seller role is not enforced in the database.** `PlantSpecies.seller` points
  to any User; checking that the user has role SELLER belongs in the views/forms.
- **D14. "Order contains 1..n OrderItem"** (mandatory many) cannot be expressed as a
  table constraint. The checkout code must create the order and its items in one
  transaction (as section 5 of the proposal says).
- **D15. image** uses `ImageField` (needs Pillow, in `requirements.txt`) with files in
  `MEDIA_ROOT/species/` (`MEDIA_ROOT = BASE_DIR / 'media'`), per the proposal's
  "local Django media directory".
- **D16. Extra index choice.** Besides PK, UNIQUE and FK indexes, Django adds a
  `varchar_pattern_ops` index on the unique `email` and `region.name` columns (for
  `LIKE` lookups). No other indexes were added; add them when real queries need them.
- **D17. Delivery defaults on the user (US-05).** `default_address` and `default_city`
  are saved on My Profile so checkout (US-21) can prefill the delivery form. Orders
  keep their own copy, so editing the profile never changes a placed order. Both have
  a database default, so code written before them can still insert users. The
  Pakistani phone format is checked by `ProfileForm`, not by the database.
