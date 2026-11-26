"""Builds docs/testing/Basera_Test_Cases.pdf from the test cases below.

Every automated case names the Django test that proves it. This script RUNS the
whole suite (python manage.py test -v 2), looks each named test up, and writes
"Pass" only if that exact test passed. A case whose test is missing or failing
stops the build, so the PDF can never claim a pass that did not happen.

Manual cases carry the result recorded when they were performed on `dev`.

Needs reportlab (not part of the project's requirements):
    pip install reportlab
    python docs/testing/build_test_cases_pdf.py [output.pdf]
"""

import re
import subprocess
import sys
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

ROOT = Path(__file__).resolve().parents[2]
PY = ROOT / ".venv" / "bin" / "python"
GREEN, ZEBRA, GRID = colors.HexColor("#23392d"), colors.HexColor("#e9eedd"), colors.HexColor("#bfc7b4")

# --------------------------------------------------------------------------------------
# Automated cases: (ID, test case, expected result, "module.Class.test_name")
# --------------------------------------------------------------------------------------
AT = "accounts.tests."
AV = "accounts.test_views."
SECT = [
    ("A1. User accounts and passwords (accounts/tests.py)", [
        ("U-01", "Old PBKDF2 password still logs in", "Login works and the hash is upgraded to Argon2", AT + "PasswordHashingTests.test_old_pbkdf2_password_still_works_and_is_upgraded_to_argon2"),
        ("U-02", "New password is hashed; login ignores email case", "Stored as an argon2 hash, never plain text; uppercase email logs in", AT + "PasswordHashingTests.test_password_is_hashed_and_case_insensitive_login"),
        ("U-03", "Email is lower-cased and trimmed on creation", "\" Ana@Example.COM \" is stored as \"ana@example.com\"", AT + "UserManagerTests.test_create_user_lowercases_and_strips_email"),
        ("U-04", "Password is hashed by create_user", "Stored value differs from the plain password", AT + "UserManagerTests.test_password_is_hashed"),
        ("U-05", "Login with differently cased email", "Authenticates the same user", AT + "UserManagerTests.test_authenticate_with_differently_cased_email"),
        ("U-06", "Login lookup normalises email", "Mixed case and spaces find the user", AT + "UserManagerTests.test_get_by_natural_key_normalises"),
        ("U-07", "Whitespace-only email", "Rejected with an error", AT + "UserManagerTests.test_whitespace_only_email_rejected"),
        ("U-08", "Blank full name", "Rejected with an error", AT + "UserManagerTests.test_blank_full_name_rejected_by_manager"),
        ("U-09", "Full name is trimmed", "Leading and trailing spaces removed", AT + "UserManagerTests.test_full_name_is_stripped"),
        ("U-10", "createsuperuser gives the Admin role", "Role = ADMIN, superuser = true", AT + "UserManagerTests.test_create_superuser_is_admin"),
        ("U-11", "Superuser with a non-admin role", "Rejected", AT + "UserManagerTests.test_create_superuser_rejects_non_admin_role"),
        ("U-12", "Duplicate email, same case", "Database rejects it", AT + "UserConstraintTests.test_duplicate_email_same_case"),
        ("U-13", "Duplicate email, different case (via create_user)", "Database rejects it", AT + "UserConstraintTests.test_duplicate_email_mixed_case_via_create_user"),
        ("U-14", "Duplicate email bypassing app code (bulk_create)", "Case-insensitive database index rejects it", AT + "UserConstraintTests.test_duplicate_email_differing_only_by_case_db_constraint"),
        ("U-15", "Empty full name saved directly", "Database rule rejects it", AT + "UserConstraintTests.test_empty_full_name_db_constraint"),
        ("U-16", "Invalid role value", "Database rule rejects it", AT + "UserConstraintTests.test_invalid_role_db_constraint"),
        ("U-17", "Superuser who is not Admin (checked both ways)", "Database rule rejects it", AT + "UserConstraintTests.test_superuser_must_be_admin_db_constraint"),
    ]),
    ("A2. Sign-up page (accounts/test_views.py)", [
        ("S-01", "Page shows the role choice", "Customer (pre-selected) and Seller; no Admin option", AV + "SignUpViewTests.test_page_has_role_choice_with_customer_selected"),
        ("S-02", "Valid sign-up as Customer", "Account saved, user logged in, sent to Home", AV + "SignUpViewTests.test_creates_customer_logs_in_and_goes_home"),
        ("S-03", "Valid sign-up as Seller", "Account saved with role SELLER", AV + "SignUpViewTests.test_creates_seller"),
        ("S-04", "Forged request choosing ADMIN", "Rejected; no account created", AV + "SignUpViewTests.test_cannot_sign_up_as_admin"),
        ("S-05", "Email already registered (any case)", "Error \"An account with this email already exists\" + \"Log in instead\" link", AV + "SignUpViewTests.test_duplicate_email_any_case_is_rejected"),
        ("S-06", "Password under 8 characters", "Rejected with the reason shown", AV + "SignUpViewTests.test_weak_password_is_rejected_with_reason"),
        ("S-07", "Password too similar to the name", "Rejected (\"too similar\")", AV + "SignUpViewTests.test_password_similar_to_name_is_rejected"),
        ("S-08", "Blank name and password", "Errors shown under each field; email kept", AV + "SignUpViewTests.test_blank_fields_show_errors_and_keep_values"),
        ("S-09", "Form has errors", "Password never shown back on the page", AV + "SignUpViewTests.test_password_never_echoed_back"),
    ]),
    ("A3. Login, logout and protected pages (accounts/test_views.py)", [
        ("L-01", "Correct login, email in any case", "Logged in; Home opens", AV + "LoginLogoutViewTests.test_login_with_any_email_case_goes_home"),
        ("L-02", "Wrong password", "One general error, email kept, not logged in", AV + "LoginLogoutViewTests.test_wrong_password_shows_one_generic_error"),
        ("L-03", "Email with no account", "Same general error (does not reveal which emails exist)", AV + "LoginLogoutViewTests.test_unknown_email_gets_the_same_error"),
        ("L-04", "Deactivated account", "Cannot log in", AV + "LoginLogoutViewTests.test_deactivated_user_cannot_log_in"),
        ("L-05", "Open Home while logged out", "Redirected to login, returned to Home after logging in", AV + "LoginLogoutViewTests.test_home_requires_login_and_returns_after"),
        ("L-06", "Login with next pointing to another website", "Ignored; goes to Home (prevents open redirects)", AV + "LoginLogoutViewTests.test_next_to_another_site_is_ignored"),
        ("L-07", "Logout", "POST only; shows \"You've been logged out.\"; session ended", AV + "LoginLogoutViewTests.test_logout_needs_post_and_shows_message"),
        ("L-08", "Logged-in user opens Login or Sign-up", "Redirected to Home", AV + "LoginLogoutViewTests.test_logged_in_user_skips_login_and_signup"),
    ]),
    ("A4. Forgot password and reset (accounts/test_views.py)", [
        ("R-01", "Full reset with a registered email", "Email sent with link; mismatched passwords rejected; new password saved; can log in; link works only once", AV + "PasswordResetViewTests.test_known_email_gets_link_and_can_reset"),
        ("R-02", "Email with no account", "Same confirmation message; no email sent", AV + "PasswordResetViewTests.test_unknown_email_looks_the_same_but_sends_nothing"),
        ("R-03", "Invalid email format", "Error shown under the field", AV + "PasswordResetViewTests.test_invalid_email_shows_error"),
        ("R-04", "Fake or broken reset link", "\"Link expired\" page", AV + "PasswordResetViewTests.test_bad_link_shows_expired"),
    ]),
    ("A5. Plant database rules (catalog/tests.py)", [
        ("C-01", "Stock never below zero", "Reducing stock below 0 is rejected; reaching exactly 0 is allowed", "catalog.tests.CatalogConstraintTests.test_stock_never_below_zero"),
        ("C-02", "Negative price", "Rejected", "catalog.tests.CatalogConstraintTests.test_price_not_negative"),
        ("C-03", "Invalid growing setting", "Only indoor / outdoor / both allowed", "catalog.tests.CatalogConstraintTests.test_setting_must_be_valid"),
        ("C-04", "Duplicate region name", "Rejected", "catalog.tests.CatalogConstraintTests.test_region_name_unique"),
        ("C-05", "Same species linked to the same region twice", "Rejected", "catalog.tests.CatalogConstraintTests.test_species_region_pair_unique"),
    ]),
    ("A6. Cart and order database rules (orders/tests.py)", [
        ("O-01", "New order defaults", "Status PENDING, payment Cash on Delivery", "orders.tests.OrdersConstraintTests.test_order_defaults"),
        ("O-02", "Cart quantity of 0", "Rejected (minimum 1)", "orders.tests.OrdersConstraintTests.test_cart_quantity_at_least_one"),
        ("O-03", "Same species added twice to one user's cart", "Rejected (one line per species)", "orders.tests.OrdersConstraintTests.test_cart_user_species_unique"),
        ("O-04", "Order item quantity of 0", "Rejected", "orders.tests.OrdersConstraintTests.test_order_item_quantity_at_least_one"),
        ("O-05", "Negative unit price on an order item", "Rejected", "orders.tests.OrdersConstraintTests.test_order_item_unit_price_not_negative"),
        ("O-06", "Same species twice in one order", "Rejected", "orders.tests.OrdersConstraintTests.test_order_item_order_species_unique"),
        ("O-07", "Negative order total", "Rejected", "orders.tests.OrdersConstraintTests.test_order_total_not_negative"),
    ]),
]

CV, DQ, CT = "catalog.test_views.", "catalog.test_data_quality.", "orders.test_cart_views.CartTests."
GV, GI, MM, MQ = "growprofiles.test_views.", "growprofiles.test_integrity.", "matching.test_matching.", "matching.test_quality."
SC = "accounts.test_security."

NEW_SECT = [
    ("A7. Browse and search the catalogue - US-18 (catalog/test_views.py, catalog/test_data_quality.py)", [
        ("K-01", "Guest opens the catalogue", "Opens without logging in; only active species are listed", CV + "CatalogueTests.test_guest_can_browse_and_sees_only_active_species"),
        ("K-02", "35 plants in the catalogue", "12 per page with page links", CV + "CatalogueTests.test_twelve_per_page_with_pagination"),
        ("K-03", "Search by common or scientific name, any case", "Matching plants only", CV + "CatalogueTests.test_search_matches_common_or_scientific_name_case_insensitively"),
        ("K-04", "Search with no match", "Says nothing matched", CV + "CatalogueTests.test_search_with_no_match_says_so"),
        ("K-05", "Search then go to page 2", "The search word is kept across pages", CV + "CatalogueTests.test_search_keeps_term_across_pages"),
        ("K-06", "Live search request from the page (HTMX)", "Only the results block is returned, not a whole page", CV + "CatalogueTests.test_htmx_request_gets_only_the_results_partial"),
        ("K-07", "Invasive plant in the list", "Warning tag shown and no buy button", CV + "CatalogueTests.test_invasive_has_warning_and_no_buy_button"),
        ("K-08", "Out-of-stock plant in the list", "Listed and marked, cannot be added", CV + "CatalogueTests.test_out_of_stock_is_listed_but_cannot_be_added"),
        ("K-09", "Guest presses Add to cart", "Sent to log in, then returned to the plant", CV + "CatalogueTests.test_guest_add_to_cart_goes_to_login_and_returns_to_species"),
        ("K-10", "Seller opens the catalogue", "No buy button is shown", CV + "CatalogueTests.test_seller_does_not_see_a_buy_button"),
        ("K-11", "Page number past the end (page=999)", "Shows the last page, no error", DQ + "CataloguePagingTests.test_dq09_a_page_number_past_the_end_shows_the_last_page"),
        ("K-12", "Page number that is not a number (page=abc)", "Shows the first page", DQ + "CataloguePagingTests.test_dq10_a_page_number_that_is_not_a_number_shows_the_first_page"),
        ("K-13", "Empty or blank search", "Lists everything", DQ + "CataloguePagingTests.test_dq11_an_empty_or_blank_search_lists_everything"),
        ("K-14", "Extra spaces around the search word", "Ignored; the plant is still found", DQ + "CataloguePagingTests.test_dq12_search_ignores_extra_spaces_around_the_term"),
    ]),
    ("A8. Species details - US-12 (catalog/test_views.py)", [
        ("D-01", "Open a species page", "Shows names, price, stock, description, growing needs, regions and seller", CV + "SpeciesDetailTests.test_shows_all_the_details"),
        ("D-02", "Inactive or missing species", "404 page", CV + "SpeciesDetailTests.test_inactive_or_missing_species_give_404"),
        ("D-03", "Invasive species page", "Red warning banner, no Add to cart", CV + "SpeciesDetailTests.test_invasive_shows_banner_and_hides_add_to_cart"),
        ("D-04", "Out-of-stock species page", "Marked out of stock, no Add to cart", CV + "SpeciesDetailTests.test_out_of_stock_hides_add_to_cart"),
        ("D-05", "Customer and guest on the same page", "Customer sees Add to cart; guest is asked to log in", CV + "SpeciesDetailTests.test_customer_sees_add_to_cart_and_guest_sees_login_prompt"),
        ("D-06", "\"You may also like\" row", "Never includes an invasive species or the plant itself", CV + "SpeciesDetailTests.test_related_species_never_include_invasive_or_itself"),
    ]),
    ("A9. Seed data - EN-02 (catalog/test_views.py, catalog/test_data_quality.py)", [
        ("E-01", "Run seed_catalog", "35 species, 5 regions, 4 invasive", DQ + "SeedDataTests.test_dq01_creates_35_species_in_5_regions_with_4_invasive"),
        ("E-02", "Native regions", "Every species has at least one native region", DQ + "SeedDataTests.test_dq02_every_species_has_at_least_one_native_region"),
        ("E-03", "Photos", "Every species has a photo and the file exists", DQ + "SeedDataTests.test_dq03_every_species_has_a_photo_file"),
        ("E-04", "Botanical details", "Light, water, soil, role and description filled; valid setting; price above 0", DQ + "SeedDataTests.test_dq04_every_species_has_complete_botanical_details"),
        ("E-05", "Names", "Common and scientific names are unique", DQ + "SeedDataTests.test_dq05_names_are_unique"),
        ("E-06", "Demo accounts", "Admin (superuser), seller and customer exist with usable passwords", DQ + "SeedDataTests.test_dq06_demo_accounts_have_the_right_roles_and_usable_passwords"),
        ("E-07", "Seller of the plants", "Every seeded species belongs to the demo seller", DQ + "SeedDataTests.test_dq07_all_seeded_species_belong_to_the_demo_seller"),
        ("E-08", "Run seed_catalog again", "Nothing is duplicated", DQ + "SeedDataTests.test_dq08_running_it_again_changes_nothing"),
        ("E-09", "Run it twice end to end", "35 species, 5 regions, 4 invasive, 3 demo accounts after two runs", CV + "SeedCatalogueTests.test_seed_command_creates_35_species_and_is_repeatable"),
    ]),
    ("A10. Cart - US-19 and US-20 (orders/test_cart_views.py)", [
        ("T-01", "Add a plant", "One cart line with quantity 1", CT + "test_add_creates_a_line_with_one_plant"),
        ("T-02", "Add the same plant again", "Quantity goes up; still one line", CT + "test_adding_again_raises_the_quantity_instead_of_a_second_line"),
        ("T-03", "Add when all the stock is already in the cart", "Tells the customer the limit is reached", CT + "test_adding_the_last_one_again_reports_the_limit"),
        ("T-04", "Quantity above what is in stock", "Capped at the stock", CT + "test_quantity_is_capped_by_stock"),
        ("T-05", "Raise a line above the stock", "Never exceeds the stock", CT + "test_quantity_never_exceeds_stock"),
        ("T-06", "Lower a line below 1", "Stays at 1", CT + "test_quantity_never_drops_below_one"),
        ("T-07", "Plus and minus buttons", "Move the quantity up and down", CT + "test_stepper_moves_the_quantity_up_and_down"),
        ("T-08", "Type a quantity", "That quantity is saved", CT + "test_update_accepts_an_explicit_quantity"),
        ("T-09", "Remove a line", "The line is deleted", CT + "test_remove_deletes_the_line"),
        ("T-10", "Remove something that is not there", "Harmless, no error", CT + "test_removing_something_that_is_not_there_is_harmless"),
        ("T-11", "Change the cart with a link (GET)", "Refused; cart changes accept POST only", CT + "test_cart_changes_only_accept_post"),
        ("T-12", "Guest presses Add to cart", "Sent to log in", CT + "test_guest_is_sent_to_log_in"),
        ("T-13", "Guest opens the cart page", "Sent to log in", CT + "test_cart_page_needs_a_login"),
        ("T-14", "Seller tries to shop", "Refused: only customers can shop", CT + "test_seller_cannot_shop"),
        ("T-15", "Add an invasive plant", "Never enters the cart", CT + "test_invasive_plant_never_enters_the_cart"),
        ("T-16", "Add an out-of-stock plant", "Never enters the cart", CT + "test_out_of_stock_plant_never_enters_the_cart"),
        ("T-17", "Add a hidden (inactive) plant", "Cannot be added", CT + "test_hidden_listing_cannot_be_added"),
        ("T-18", "Stock drops below what is in the cart", "The line is not silently lowered", CT + "test_stock_dropping_below_the_cart_never_lowers_the_line"),
        ("T-19", "Cart page", "Each line shows its price and total", CT + "test_cart_page_lists_each_line_with_its_total"),
        ("T-20", "Empty cart", "Says so and links to the catalogue", CT + "test_empty_cart_page_says_so"),
        ("T-21", "A plant sells out while in the cart", "The line is flagged", CT + "test_cart_page_flags_a_line_that_sold_out"),
        ("T-22", "Header cart icon", "Badge shows how many plants are in the cart", CT + "test_header_badge_shows_how_many_plants_are_in_the_cart"),
        ("T-23", "Add from a page", "Returns to the page the button was on", CT + "test_next_returns_to_the_page_the_button_was_on"),
        ("T-24", "Return address pointing to another website", "Ignored", CT + "test_next_cannot_point_at_another_site"),
        ("T-25", "Add without reloading (HTMX)", "A small fragment is returned; no redirect", CT + "test_htmx_add_answers_with_a_fragment_and_no_redirect"),
        ("T-26", "Change quantity without reloading", "Cart body is swapped in place", CT + "test_htmx_update_swaps_the_cart_body_in_place"),
        ("T-27", "Remove the last line without reloading", "Falls back to the empty-cart message", CT + "test_htmx_remove_falls_back_to_the_empty_state"),
        ("T-28", "Plus/minus without reloading", "Success is quiet; limits show a message", CT + "test_htmx_stepper_success_is_quiet_but_limits_are_not"),
        ("T-29", "Expired session during an in-place change", "Browser is told to go to the login page", CT + "test_htmx_request_from_a_guest_asks_the_browser_to_navigate"),
    ]),
    ("A11. Grow profiles - US-06 (growprofiles/test_views.py, growprofiles/test_integrity.py)", [
        ("G-01", "Valid profile", "Saved under the logged-in customer and listed", GV + "CreateGrowProfileTests.test_valid_profile_is_saved_under_the_logged_in_customer_and_listed"),
        ("G-02", "Every field left empty", "An error under each field; nothing saved", GV + "CreateGrowProfileTests.test_every_missing_field_shows_its_own_error_and_saves_nothing"),
        ("G-03", "A save that fails", "What the customer typed and picked is kept", GV + "CreateGrowProfileTests.test_a_failed_save_keeps_what_the_user_typed"),
        ("G-04", "Answer outside the fixed choices", "Rejected", GV + "CreateGrowProfileTests.test_values_outside_the_fixed_choices_are_rejected"),
        ("G-05", "Region list", "Comes from the Region table", GV + "CreateGrowProfileTests.test_region_choices_come_from_the_region_table"),
        ("G-06", "Choose another user in a forged request", "Ignored; the profile is saved for the logged-in customer", GV + "CreateGrowProfileTests.test_the_user_cannot_be_chosen_through_the_form"),
        ("G-07", "How matching works panel", "Each weight drawn as a bar (30, 25, 20, 15, 10 points)", GV + "CreateGrowProfileTests.test_how_matching_works_draws_each_weight_as_a_bar"),
        ("G-08", "Answer buttons", "Cards with icons; purposes are small buttons", GV + "CreateGrowProfileTests.test_answers_are_cards_with_icons_and_purposes_are_pill_buttons"),
        ("G-09", "No profiles yet", "Invites the customer to create one", GV + "ProfileListTests.test_empty_list_invites_the_customer_to_create_one"),
        ("G-10", "Two customers with profiles", "Each sees only their own", GV + "ProfileListTests.test_a_customer_only_sees_their_own_profiles"),
        ("G-11", "Logged-out visitor", "Sent to log in", GV + "ProfileListTests.test_logged_out_visitors_are_sent_to_log_in"),
        ("G-12", "Seller opens grow profiles", "Sent Home; profiles are for customers", GV + "ProfileListTests.test_sellers_cannot_use_grow_profiles"),
        ("G-13", "Delete a region that profiles use", "Blocked", GI + "ProfileIntegrityTests.test_gp01_a_region_that_profiles_use_cannot_be_deleted"),
        ("G-14", "Delete a user", "Their profiles are deleted with them", GI + "ProfileIntegrityTests.test_gp02_deleting_a_user_deletes_their_profiles"),
        ("G-15", "Profile name of only spaces", "Rejected", GI + "ProfileIntegrityTests.test_gp03_a_name_of_only_spaces_is_rejected"),
        ("G-16", "Profile name over 100 characters", "Rejected", GI + "ProfileIntegrityTests.test_gp04_a_name_over_100_characters_is_rejected"),
        ("G-17", "Region that does not exist", "Rejected with \"Please choose a region\"", GI + "ProfileIntegrityTests.test_gp05_a_region_that_does_not_exist_is_rejected"),
        ("G-18", "Several profiles", "Newest is listed first", GI + "ProfileIntegrityTests.test_gp06_the_newest_profile_is_listed_first_and_each_user_can_have_several"),
        ("G-19", "Spaces around the name", "Trimmed", GI + "ProfileIntegrityTests.test_gp07_whitespace_around_a_name_is_trimmed"),
    ]),
    ("A12. Ranked matches - US-08 (matching/test_matching.py, matching/test_quality.py)", [
        ("H-01", "A species that fits perfectly", "Scores 100", MM + "ScoreTests.test_a_perfect_species_scores_100"),
        ("H-02", "Sunlight", "30 points; loses half per step away", MM + "ScoreTests.test_sunlight_is_30_points_and_loses_half_per_step"),
        ("H-03", "Water", "20 points with the same rule", MM + "ScoreTests.test_water_is_20_points_with_the_same_formula"),
        ("H-04", "Soil", "25 for an exact match, half for adaptable loam, 0 otherwise", MM + "ScoreTests.test_soil_exact_is_25_loam_is_adaptable_for_half_otherwise_0"),
        ("H-05", "Indoor / outdoor", "15 points; a plant that grows in both always fits", MM + "ScoreTests.test_indoor_outdoor_is_15_and_both_always_fits"),
        ("H-06", "Purpose", "10 points when the plant serves it", MM + "ScoreTests.test_purpose_is_10_points_when_the_plant_serves_it"),
        ("H-07", "Which plants are considered", "Only active, native to the region and not invasive", MM + "RankTests.test_only_native_active_non_invasive_species_are_candidates"),
        ("H-08", "Order of results", "Best score first, then by name; out-of-stock plants kept", MM + "RankTests.test_sorted_by_score_then_name_and_out_of_stock_is_kept"),
        ("H-09", "Plant native to two regions", "Appears once", MM + "RankTests.test_a_species_in_two_regions_appears_once"),
        ("H-10", "Reading species text such as \"Full sun\"", "Turned into the right codes; unclear text reads as unknown", MM + "VocabularyTests.test_text_is_read_into_codes"),
        ("H-11", "Results page cards", "Rank, score, price, stock and details link", MM + "MatchPageTests.test_lists_ranked_cards_with_score_price_stock_and_details_link"),
        ("H-12", "Out-of-stock match", "Marked, no Add to cart", MM + "MatchPageTests.test_out_of_stock_plants_have_no_add_to_cart"),
        ("H-13", "Eight matches", "Opens on the top five; Show all lists all eight", MM + "MatchPageTests.test_opens_on_the_top_five_and_show_all_lists_the_rest"),
        ("H-14", "Someone else's profile", "404", MM + "MatchPageTests.test_someone_elses_profile_is_a_404"),
        ("H-15", "Match Results link in the header", "Goes to the newest profile, or to the list when there is none", MM + "MatchPageTests.test_the_header_link_goes_to_the_newest_profile_or_the_list"),
        ("H-16", "Profile list", "Has a Find plants button for each profile", MM + "MatchPageTests.test_the_list_page_links_to_find_plants"),
        ("H-17", "Logged-out visitor", "Sent to log in", MM + "MatchPageTests.test_logged_out_visitors_are_sent_to_log_in"),
        ("H-18", "Page layout", "Uses the shared site header and footer", MM + "MatchPageTests.test_the_page_is_wrapped_in_the_site_layout"),
        ("H-19", "All 432 possible profiles in one region", "Scores stay between 0 and 100, sorted, no invasive plant", MQ + "MatchingQualityTests.test_mq01_every_possible_profile_gets_scores_between_0_and_100_in_order"),
        ("H-20", "500 species ranked", "Under 2 seconds and one database query", MQ + "MatchingQualityTests.test_mq02_five_hundred_species_are_ranked_in_under_two_seconds_with_one_query"),
        ("H-21", "Results page with 500 species", "Opens in under 2 seconds", MQ + "MatchingQualityTests.test_mq03_the_match_page_itself_stays_fast_with_five_hundred_species"),
        ("H-22", "Add to cart from a match", "Returns to the match page with the plant in the cart", MQ + "MatchingQualityTests.test_mq04_add_to_cart_from_the_match_page_returns_to_the_match_page"),
    ]),
    ("A13. Reasons for each match - US-09 (matching/test_matching.py)", [
        ("Y-01", "A perfect match", "Five plain-language reasons, all marked as matches", MM + "ReasonTests.test_each_match_has_one_reason_per_criterion_in_plain_language"),
        ("Y-02", "A partial and a poor match", "Reasons say why (for example \"adaptable, but your soil is sandy\")", MM + "ReasonTests.test_partial_and_no_match_say_why"),
        ("Y-03", "Every criterion", "The reason's state always agrees with the points scored", MM + "ReasonTests.test_the_state_always_agrees_with_the_points"),
        ("Y-04", "A plant with unrecorded needs", "Scores 0 for that criterion and says it is not recorded", MM + "ReasonTests.test_a_species_with_unrecorded_needs_scores_zero_there_and_says_so"),
        ("Y-05", "Match cards", "Show the reasons and the ecological benefit", MM + "ReasonTests.test_cards_show_the_reasons_and_the_ecological_benefit"),
    ]),
    ("A14. Invasive species and no matches - US-10 (matching/test_matching.py)", [
        ("V-01", "Invasive plant that fits perfectly", "Still never appears in matches", MM + "InvasiveAndNoMatchTests.test_invasive_species_never_appear_even_when_they_fit_perfectly"),
        ("V-02", "All seeded invasive plants, every region", "None is ever matched", MM + "InvasiveAndNoMatchTests.test_no_seeded_invasive_species_is_ever_matched"),
        ("V-03", "Invasive plant's page", "Warning banner and no cart button", MM + "InvasiveAndNoMatchTests.test_the_invasive_catalogue_page_warns_and_offers_no_cart"),
        ("V-04", "Region with no native plants", "Says so and lists regions that do have plants", MM + "InvasiveAndNoMatchTests.test_a_region_with_no_plants_says_so_and_lists_regions_that_have_some"),
        ("V-05", "Every match is a weak fit", "Says which answer to relax; plants still listed", MM + "InvasiveAndNoMatchTests.test_when_every_plant_is_a_weak_fit_it_says_which_answer_to_relax"),
        ("V-06", "Relaxing hints", "Count the plants that would reach a score of 40", MM + "InvasiveAndNoMatchTests.test_relaxing_hints_count_plants_that_would_reach_a_fit"),
    ]),
    ("A15. Landing pages (catalog/test_views.py)", [
        ("W-01", "Customer Home", "Five featured native plants, never invasive; how it works; why native plants", CV + "LandingPageContentTests.test_customer_home_features_five_native_plants_and_no_invasive_ones"),
        ("W-02", "Seller Home", "Shows only the seller's own numbers", CV + "LandingPageContentTests.test_seller_home_shows_only_their_own_numbers"),
        ("W-03", "Admin Home", "Shows platform-wide numbers and regions", CV + "LandingPageContentTests.test_admin_home_shows_platform_numbers"),
        ("W-04", "New seller with no plants", "Not told \"everything is well stocked\"; invited to list plants", CV + "LandingPageContentTests.test_a_new_seller_with_no_plants_is_not_told_everything_is_well_stocked"),
        ("W-05", "Each role after login", "Customer, seller and admin each land on their own page, linking to the catalogue", CV + "LandingPlaceholderTests.test_each_role_lands_on_its_own_placeholder_that_links_to_the_catalogue"),
        ("W-06", "Header links to later pages", "About, My Listings, Orders, Earnings, Users, Reports, Settings all open", CV + "LandingPlaceholderTests.test_header_placeholder_pages_load"),
    ]),
    ("A16. Security and access control (accounts/test_security.py)", [
        ("SEC-01", "Logged-out visitor opens any private page", "Sent to log in (Home, profiles, matches, cart)", SC + "AccessControlTests.test_sec01_logged_out_visitors_are_sent_to_log_in_from_every_private_page"),
        ("SEC-02", "Public pages", "Open without logging in", SC + "AccessControlTests.test_sec02_public_pages_open_without_logging_in"),
        ("SEC-03", "Seller or admin opens customer-only pages", "Sent Home", SC + "AccessControlTests.test_sec03_sellers_and_admins_cannot_use_customer_only_pages"),
        ("SEC-04", "Admin site", "Customers and sellers are turned away; admins get in", SC + "AccessControlTests.test_sec04_the_admin_site_is_for_admins_only"),
        ("SEC-05", "Another customer's profile", "404 and not listed", SC + "AccessControlTests.test_sec05_a_customer_cannot_open_another_customers_profile"),
        ("SEC-06", "A page that does not exist", "404", SC + "AccessControlTests.test_sec06_unknown_pages_give_a_404"),
        ("SEC-07", "Log out without the CSRF token", "Refused (403)", SC + "CsrfTests.test_sec07_log_out_needs_the_token"),
        ("SEC-08", "Add to cart without the CSRF token", "Refused; nothing added", SC + "CsrfTests.test_sec08_add_to_cart_needs_the_token"),
        ("SEC-09", "Create a profile without the CSRF token", "Refused; nothing saved", SC + "CsrfTests.test_sec09_creating_a_profile_needs_the_token"),
        ("SEC-10", "Script tag in a plant name", "Shown as text in the catalogue, never run", SC + "InjectionTests.test_sec10_a_script_in_a_plant_name_is_escaped_in_the_catalogue"),
        ("SEC-11", "Script tag in a profile name", "Shown as text on the list and match pages", SC + "InjectionTests.test_sec11_a_script_in_a_profile_name_is_escaped_on_every_page_that_shows_it"),
        ("SEC-12", "Script tag typed in the search box", "Shown as text, never run", SC + "InjectionTests.test_sec12_a_script_in_the_search_box_is_escaped"),
        ("SEC-13", "SQL-looking searches (' OR 1=1 --, DROP TABLE, %, _)", "Treated as plain text; no results; tables untouched", SC + "InjectionTests.test_sec13_sql_looking_searches_are_treated_as_plain_text"),
        ("SEC-14", "Log out", "Session ended; Home asks for login again", SC + "OpenRedirectAndSessionTests.test_sec14_log_out_ends_the_session"),
        ("SEC-15", "Password reset email", "Has the link but never the password or its hash", SC + "OpenRedirectAndSessionTests.test_sec15_the_reset_email_has_a_link_but_never_the_password_or_its_hash"),
    ]),
]

EP, DP = "accounts.test_error_pages.ErrorPageTests.", "basera_site.test_deploy."
NEW_SECT += [
    ("A17. Error pages (accounts/test_error_pages.py)", [
        ("EP-01", "Open a page that does not exist", "Branded 404: butterfly, \"Page not found\", Back to home and Browse catalogue", EP + "test_ep01_a_missing_page_shows_the_branded_404_with_two_ways_out"),
        ("EP-02", "404 page layout", "Keeps the site header and footer", EP + "test_ep02_the_404_page_keeps_the_site_header_and_footer"),
        ("EP-03", "404 page when logged in", "Works for a logged-in customer", EP + "test_ep03_the_404_page_works_when_logged_in"),
        ("EP-04", "Access denied", "Branded 403 with Back to home and Log in", EP + "test_ep04_access_denied_shows_the_branded_403"),
        ("EP-05", "Form sent without a valid security token", "Friendly \"Please try again\" 403 page", EP + "test_ep05_a_form_without_a_valid_token_shows_a_friendly_403"),
        ("EP-06", "Server error page", "Plain, self-contained page that needs nothing else to work", EP + "test_ep06_the_500_page_is_plain_html_that_needs_no_context"),
    ]),
    ("A18. Production setup (basera_site/test_deploy.py)", [
        ("DP-T01", "Yes/no settings (1, true, yes, on)", "Read in any case; anything else is no", DP + "EnvHelperTests.test_dp01_flag_reads_yes_and_no_words_in_any_case"),
        ("DP-T02", "Yes/no setting left unset or blank", "Uses the default", DP + "EnvHelperTests.test_dp02_flag_uses_the_default_when_unset_or_blank"),
        ("DP-T03", "Comma-separated setting", "Becomes a clean list", DP + "EnvHelperTests.test_dp03_csv_gives_a_clean_list"),
        ("DP-T04", "DATABASE_URL from the host", "Turned into a database setting, with special characters and sslmode", DP + "EnvHelperTests.test_dp04_database_url_becomes_a_django_database_entry"),
        ("DP-T05", "DATABASE_URL without a port", "Uses 5432", DP + "EnvHelperTests.test_dp05_a_database_url_without_a_port_uses_5432"),
        ("DP-T06", "Wrong kind of DATABASE_URL", "Refused with a clear error", DP + "EnvHelperTests.test_dp06_bad_database_urls_are_refused"),
        ("DP-T07", "Django's own deploy check, production settings", "Only two optional HSTS notes remain (include-subdomains, preload)", DP + "ProductionSettingsTests.test_dp07_production_passes_the_django_deploy_check_except_two_optional_hsts_extras"),
        ("DP-T08", "Debug off, no secret key", "The site refuses to start", DP + "ProductionSettingsTests.test_dp08_with_debug_off_the_site_refuses_to_start_without_a_secret_key"),
        ("DP-T09", "Debug off, no allowed hosts", "The site refuses to start", DP + "ProductionSettingsTests.test_dp09_with_debug_off_the_site_refuses_to_start_without_allowed_hosts"),
        ("DP-T10", "Running on Render with DEBUG not set", "Debug is off by itself", DP + "ProductionSettingsTests.test_dp10_running_on_render_turns_debug_off_by_itself"),
        ("DP-T11", "Render's address", "Added to allowed hosts and trusted origins", DP + "ProductionSettingsTests.test_dp11_render_adds_its_own_address_to_hosts_and_trusted_origins"),
        ("DP-T12", "Local development", "Still starts with none of the production settings", DP + "ProductionSettingsTests.test_dp12_local_development_keeps_working_without_any_of_this"),
        ("DP-T13", "Production cookies and HTTPS", "Secure cookies, https redirect, HSTS, proxy header trusted", DP + "ProductionSettingsTests.test_dp13_in_production_cookies_are_secure_and_https_is_forced"),
        ("DP-T14", "Server packages", "gunicorn and WhiteNoise are pinned and WhiteNoise is in the middleware", DP + "BuildFileTests.test_dp14_whitenoise_and_gunicorn_are_installed_requirements"),
        ("DP-T15", "Build script", "Executable; installs, collects static files, migrates, seeds, in that order", DP + "BuildFileTests.test_dp15_the_build_script_collects_static_migrates_and_seeds_in_that_order"),
        ("DP-T16", "Render blueprint", "Describes the site; admin and email passwords are not stored in it", DP + "BuildFileTests.test_dp16_the_render_blueprint_describes_the_site_without_secrets"),
        ("DP-T17", "Git ignore", "Keeps .env, collected static files and uploads out of GitHub", DP + "BuildFileTests.test_dp17_secrets_and_build_output_stay_out_of_git"),
        ("DP-T18", "Seed on the live site", "35 plants, no demo logins, nursery account that cannot be logged into, no password printed", DP + "ProductionSeedTests.test_dp18_no_demo_logins_and_no_shared_password_in_production"),
        ("DP-T19", "ADMIN_EMAIL and ADMIN_PASSWORD", "A real admin is created with the Admin role", DP + "ProductionSeedTests.test_dp19_a_real_admin_is_created_from_the_environment"),
        ("DP-T20", "Weak ADMIN_PASSWORD", "The seed stops and no admin is created", DP + "ProductionSeedTests.test_dp20_a_weak_admin_password_stops_the_seed"),
        ("DP-T21", "Seed run again", "Keeps the admin; nothing duplicated", DP + "ProductionSeedTests.test_dp21_running_it_again_keeps_the_admin_and_changes_nothing"),
        ("DP-T22", "A photo file disappears (host restart)", "The next seed puts it back", DP + "ProductionSeedTests.test_dp22_a_photo_file_that_disappeared_is_put_back"),
        ("DP-T23", "Media route and ../ paths", "Files outside the media folder are refused and never returned", DP + "MediaServingTests.test_dp23_the_media_route_never_serves_files_outside_the_media_folder"),
    ]),
]

PF = "basera_site.test_performance."
NEW_SECT += [
    ("A19. Speed budgets (basera_site/test_performance.py)", [
        ("PF-01", "Plant photos", "Each is at most 720 px and 200 KB (all 35 checked)", PF + "ImageBudgetTests.test_pf01_every_plant_photo_is_at_most_720px_and_200kb"),
        ("PF-02", "All plant photos together", "Under 3 MB", PF + "ImageBudgetTests.test_pf02_all_plant_photos_together_stay_under_3mb"),
        ("PF-03", "Home page hero picture", "At most 1920 px wide and 250 KB", PF + "ImageBudgetTests.test_pf03_the_home_page_hero_is_at_most_1920px_wide_and_250kb"),
        ("PF-04", "Login page background", "A JPEG under 150 KB; the 1 MB PNG no longer ships", PF + "ImageBudgetTests.test_pf04_the_login_background_is_a_jpeg_under_150kb"),
        ("PF-05", "Every site image", "None over 400 KB", PF + "ImageBudgetTests.test_pf05_no_image_in_the_static_folder_is_over_400kb"),
        ("PF-06", "Scripts from other websites", "Never block the page from drawing (defer or async)", PF + "NonBlockingScriptTests.test_pf06_scripts_from_other_websites_never_block_the_page"),
        ("PF-07", "Static files in production", "Hashed names (cached for a year) that never error if missing", PF + "CachingTests.test_pf07_production_uses_hashed_static_file_names_that_never_error_when_missing"),
        ("PF-08", "Seeded plant photos in production", "Served with a week of caching by WhiteNoise", PF + "CachingTests.test_pf08_seeded_photos_are_served_with_a_week_of_caching"),
        ("PF-09", "Server setup", "Two workers with four threads each, so several requests run at once", PF + "CachingTests.test_pf09_the_server_handles_several_requests_at_once"),
    ]),
]

LY = "accounts.test_layout.OneScreenLayoutTests."
NEW_SECT += [
    ("A20. One-screen layout of the log in pages (accounts/test_layout.py)", [
        ("LY-01", "Extra scroll room on the log in, sign-up and password pages", "None: the page is exactly one screen tall", LY + "test_ly01_the_auth_pages_have_no_extra_scroll_room"),
        ("LY-02", "Page height", "Follows the visible screen, including phone browser bars (100dvh)", LY + "test_ly02_the_page_height_follows_the_visible_screen_including_phone_bars"),
        ("LY-03", "Short desktop screens", "Tighter spacing at three heights (860, 740 and 680 px)", LY + "test_ly03_short_desktop_screens_get_tighter_spacing_at_three_heights"),
        ("LY-04", "Compact layouts", "Fields and buttons never drop below 44 px tall", LY + "test_ly04_fields_and_buttons_stay_44px_tall_in_the_compact_layouts"),
        ("LY-05", "Login background", "The image file the stylesheet names exists", LY + "test_ly05_the_login_background_file_the_css_names_exists"),
    ]),
]

PR = "accounts.test_profile.ProfileTests."
NEW_SECT += [
    ("A21. My profile - US-05 (accounts/test_profile.py)", [
        ("PR-01", "Open My Profile while logged out", "Redirected to login, then back to the profile", PR + "test_requires_login"),
        ("PR-02", "Open My Profile", "Shows name, email, phone, address, city and account type", PR + "test_shows_current_details"),
        ("PR-03", "Email and role", "Shown read-only; no field submits them", PR + "test_email_and_role_are_read_only"),
        ("PR-04", "Save valid changes", "Saved, tidied and shown at once with a success message", PR + "test_valid_changes_save_and_show_immediately"),
        ("PR-05", "Clear the optional details", "Phone, address and city saved empty", PR + "test_optional_details_can_be_cleared"),
        ("PR-06", "Forged request changing email, role or flags", "Ignored", PR + "test_forged_email_and_role_are_ignored"),
        ("PR-07", "Session and password after saving", "Still logged in; password unchanged", PR + "test_saving_keeps_the_user_logged_in_with_the_same_password"),
        ("PR-08", "Blank full name", "Error shown, typed values kept, nothing saved", PR + "test_blank_name_is_rejected_and_nothing_is_saved"),
        ("PR-09", "Phone that is not a Pakistani mobile number", "Rejected with an example of the format", PR + "test_phone_must_be_a_pakistani_number"),
        ("PR-10", "Both phone formats, with spaces", "Accepted and stored without spaces", PR + "test_both_phone_formats_are_accepted"),
        ("PR-11", "Over-long address or city", "Rejected with the limit", PR + "test_too_long_address_and_city_are_rejected"),
        ("PR-12", "Forged id of another account", "Only your own account changes", PR + "test_editing_never_touches_another_account"),
        ("PR-13", "Customer links and header account icon", "Change password, grow profiles and orders; icon opens the profile", PR + "test_customer_links_and_header_icon"),
        ("PR-14", "Seller opens My Profile", "No customer-only links; name in the header opens the profile", PR + "test_seller_can_open_profile_without_customer_links"),
        ("PR-15", "Save without the security (CSRF) token", "Refused (403)", PR + "test_post_without_csrf_token_is_refused"),
        ("PR-16", "Code that does not know the new columns adds a user", "The database fills them in as empty", PR + "test_database_supplies_defaults_for_code_that_omits_the_new_columns"),
    ]),
]

# --------------------------------------------------------------------------------------
# Manual cases: (ID, test case, expected result, result)
# Result words: Pass | Carried over (files unchanged since Shehroze's run) | Not re-run | Open
# --------------------------------------------------------------------------------------
MANUAL_OLD = [
    ("M-01", "Login page matches the Figma design", "Element positions measured at 1366x768 match Figma", "Carried over"),
    ("M-02", "Create account page matches Figma", "Every field and button matches Figma positions", "Carried over"),
    ("M-03", "Forgot password page matches Figma", "Every element matches Figma positions", "Carried over"),
    ("M-04", "Phone-width layout (375px)", "Pages stack correctly, no sideways scrolling (re-run: login, sign-up, forgot password)", "Pass"),
    ("M-05", "Show / Hide password button", "Switches between hidden and visible text (re-run)", "Pass"),
    ("M-06", "Every link opens the right page", "Create account, Forgot password, Log in, Back to log in, Privacy, Terms, Help (re-run)", "Pass"),
    ("M-07", "Scroll parallax", "Layers move at different speeds; background edge never shows", "Not re-run"),
    ("M-08", "Sign up as Seller through the real page", "Account created; opens the new Seller landing page (was: \"Account type: Seller\")", "Pass"),
    ("M-09", "Empty sign-up form", "Coral borders (#f0a58c) and messages under each field", "Pass"),
    ("M-10", "Wrong password through the real page", "General error shown, email kept, password cleared", "Pass"),
    ("M-11", "Logout, then open Home", "\"You've been logged out.\" shown; Home redirects to login with ?next=/home/", "Pass"),
    ("M-12", "Password reset through the real pages", "Link opens, mismatch rejected, new password set, saved password works (re-run with a generated link)", "Pass"),
    ("M-13", "Reuse a used reset link", "\"Link expired\" shown", "Pass"),
    ("M-14", "Database tables created in PostgreSQL", "All 10 tables and their rules present (12 check rules)", "Pass"),
    ("M-15", "New account stored in the database", "Row in accounts_user; password stored as an argon2 hash", "Pass"),
    ("M-16", "Login and sign-up speed", "Login 0.03 s and sign-up 0.03 s on the test Mac (Argon2); was 0.64 s / 0.94 s on Windows", "Pass"),
    ("M-17", "Real email through Gmail", "Needs the team's Gmail app password in .env; not re-run on dev (R-01 covers the email content)", "Not re-run"),
    ("M-18", "No errors while using the pages", "Browser console and server log clean (only the deliberate missing-page 404)", "Pass"),
    ("M-19", "Secrets kept out of GitHub", ".env not tracked; its database password appears nowhere in git history (re-run)", "Pass"),
]
MANUAL_NEW = [
    ("M-20", "Sign up as a new customer through the real page", "Account created, logged in, customer Home opens", "Pass"),
    ("M-21", "Submit the empty grow profile form", "A banner and six field errors; nothing saved", "Pass"),
    ("M-22", "Create a profile by clicking (Sindh, outdoor, full sun, sandy, low water, pollinators)", "Saved; listed with six answer chips", "Pass"),
    ("M-23", "Find plants for that profile", "19 native plants ranked; Ak, Aloe and Ber top at 100%; five reasons on each; no invasive name anywhere", "Pass"),
    ("M-24", "Add to cart from a match card", "Cart badge shows 1 and a message appears; the page does not reload", "Pass"),
    ("M-25", "Cart: plus, minus and Remove", "Total goes Rs 350 to Rs 700 and back; Remove shows the empty cart and clears the badge; no reload", "Pass"),
    ("M-26", "Live catalogue search with real key presses", "Results update as you type; address bar gets ?q=; no reload", "Pass"),
    ("M-27", "Invasive species page (Mesquite)", "Warning banner, \"Invasive - not sold\" tag, no buy button, \"Native alternatives\" row", "Pass"),
    ("M-28", "Neem page, and a species number that does not exist", "Name, price, three tabs, regions, seller, buy button, related row; missing species gives 404", "Pass"),
    ("M-29", "Every main page opens, for each role", "13 pages return 200, each in under 0.03 s on this Mac", "Pass"),
    ("M-30", "All 35 seeded plant photos", "All 35 load (35 of 35 return 200)", "Pass"),
    ("M-31", "Phone width (375px) on the new pages", "Home, catalogue, species, new profile, profile list, matches and cart: no sideways scrolling; the mobile menu opens and closes", "Pass"),
    ("M-32", "Keyboard use of the profile form", "Arrow keys change the chosen option; a 3px focus ring shows; all 18 options are reachable", "Pass"),
    ("M-33", "Seller logs in (wrong password first)", "General error, then Seller landing; 35 plants, 26 outdoor, 9 both, 2 out of stock match the database", "Pass"),
    ("M-34", "New seller signs up", "Opens the Seller landing page with zeros; invited to list plants (wording fixed during testing)", "Pass"),
    ("M-35", "Admin logs in with the email in capitals", "Admin landing; region counts 25/22/20/13/12, 35 listings, 4 invasive, 2 customers all match the database; every sidebar link opens", "Pass"),
    ("M-36", "Customer hero on different window sizes", "Photo fills the first screen at 700 and 1000 px tall; above 1100 px a cream strip shows by design (cap)", "Pass"),
    ("M-37", "Browser console and network on the new pages", "No script errors; the only 404 was the deliberate missing-species request", "Pass"),
    ("M-38", "Database health", "No missing migrations; PostgreSQL 18; 10 tables; demo passwords stored as argon2", "Pass"),
    ("M-39", "Production build on an empty database (build.sh, DEBUG off)", "141 static files collected, tables created, real admin created, 35 plants seeded, nursery account locked, no demo password printed", "Pass"),
    ("M-40", "Production server (gunicorn) with debug off", "Pages, CSS, JS, images and plant photos served; unknown page gives the plain 404 with no debug details; ../ media path refused; wrong Host answered 400; cookies Secure; HSTS sent behind an HTTPS proxy", "Pass"),
    ("M-41", "Real admin logs in under production settings (simulated HTTPS proxy)", "Wrong password refused; right password works with the email in capitals; session cookie Secure and HttpOnly; admin landing shows 35 listings; a form sent without token or origin is refused (403)", "Pass"),
    ("M-42", "Branded 404 page in the browser", "Butterfly, large 404, \"Page not found\", Back to home and Browse catalogue; matches the Figma design", "Pass"),
    ("M-43", "Speed rehearsal in production mode", "File names carry a hash and are cached for a year; the main stylesheet is 19 KB, 5 KB gzipped; plant photos cached for a week; all 12 catalogue photos (800 KB) load at once; catalogue page HTML in 0.02 s", "Pass"),
    ("M-44", "Local media folder after a full test run", "Stays at 35 photos (before the fix every run added 35 duplicates; 4,330 had piled up and were removed)", "Pass"),
    ("M-45", "Log in page fits one screen (no scrolling)", "At 1366x768, 1366x657 and 1920x1000 the page is exactly the screen height; \"Basera. Grow local.\", Privacy, Terms and Help are all visible", "Pass"),
    ("M-46", "Sign-up page (the tallest form) fits one screen", "Fits at 1920x1000, 1366x768, 1280x720 and 1366x657 (it overflowed by 21 px and 50 px at the last two before the compact layout was added)", "Pass"),
    ("M-47", "Forgot-password page fits one screen", "Fits at 1366x768 and 1366x657; tap targets stay 44 px (a 43 px reading was only the entrance animation at 98% scale)", "Pass"),
]
DEPLOY = [
    ("DP-01", "manage.py check", "No issues", "Pass"),
    ("DP-02", "Migrations in step with the models", "makemigrations --check finds nothing; migrate --check passes", "Pass"),
    ("DP-03", "DEBUG is off in production", "Off automatically on Render (or with DEBUG=False); confirmed: plain 404, no debug page", "Pass"),
    ("DP-04", "Strong secret key from the environment", "Required when debug is off (the site refuses to start without one); Render generates a long one", "Pass"),
    ("DP-05", "ALLOWED_HOSTS lists the site address", "Required when debug is off; Render's address is added automatically; a wrong Host header gets 400", "Pass"),
    ("DP-06", "HTTPS settings", "SSL redirect, secure session and CSRF cookies and HSTS (1 hour); Django's deploy check shows only two optional HSTS notes", "Pass"),
    ("DP-07", "Real email backend", "Set EMAIL_ADDRESS and EMAIL_APP_PASSWORD on the Render dashboard (secrets cannot be stored in the repository); without them reset links are only printed in the log", "Open"),
    ("DP-08", "Static files served in production", "gunicorn and WhiteNoise; collectstatic runs in build.sh; CSS, JS and images served in the production run", "Pass"),
    ("DP-09", "Plant photos survive restarts", "The 35 seeded photos are restored on every deploy (tested by deleting a file); photos uploaded by sellers later need a persistent disk or cloud storage", "Pass"),
    ("DP-10", "Demo account passwords", "No demo logins on the live site; the admin comes from ADMIN_EMAIL and ADMIN_PASSWORD; the nursery owner account cannot be logged into", "Pass"),
    ("DP-11", "Live site created on Render", "Needs your Render account: New > Blueprint > this repository (steps in docs/deployment/README.md)", "Open"),
    ("DP-12", "Smoke test of the live address", "After the first deploy: home, catalogue with photos, sign up, grow profile, matches, admin login, a 404 page", "Open"),
]

FINDINGS = [
    "No automated test failed in the final run. One wording problem was found during manual testing and fixed: a seller with no plants was told \"Every plant is well stocked\" (case W-04).",
    "Shehroze's expectation for M-08 changed on purpose: a new seller now opens the Seller landing page, not a placeholder showing \"Account type: Seller\".",
    "Not re-run: M-07 (scroll parallax: the test browser pane was hidden, which pauses animation) and M-17 (real Gmail: needs the team's app password). Both are unchanged code from Shehroze's passing run.",
    "M-01 to M-03 are carried over: the login, sign-up and forgot-password templates, styles and scripts are identical to Shehroze's branch (checked with git diff).",
    "Production setup was added after the first test run (sections A17 and A18, M-39 to M-42). The production build was rehearsed on this computer with a scratch database, debug off and gunicorn.",
    "After the live site felt slow, images and caching were cut (A19, M-43): plant photos 5.1 to 2.6 MB, hero 349 to 189 KB, login background 1 MB PNG to 99 KB JPEG, hashed and compressed static files, cached photos, 2 workers with 4 threads. A hidden problem was also fixed: older tests had written 4,330 duplicate photos into the real media folder.",
    "The log in, sign-up and password pages were made exactly one screen tall (A20, M-45 to M-47) so the footer links are visible without scrolling. A phone, a window shorter than about 650 px, or a form showing error messages can still scroll rather than cut content off.",
    "Still open: DP-07 (the Gmail details must be entered on the Render dashboard), DP-11 (the live site must be created from the Render account) and DP-12 (smoke test of the live address).",
    "On a very tall window (over 1100 px) a cream strip shows under the customer hero. This is the deliberate height cap (M-36).",
]


# --------------------------------------------------------------------------------------
def run_suite():
    """Run the whole Django suite and return {qualified test name: 'ok' / other}."""
    proc = subprocess.run([str(PY), "manage.py", "test", "-v", "2"], cwd=ROOT, capture_output=True, text=True)
    text = proc.stdout + proc.stderr
    results = {}
    for line in text.splitlines():
        m = re.match(r"^\S+ \(([\w.]+)\) \.\.\. (.*)$", line)
        if m:
            results[m.group(1)] = m.group(2).strip()
    summary = re.search(r"Ran (\d+) tests? in ([\d.]+)s", text)
    return results, proc.returncode, summary


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def build(out):
    results, code, summary = run_suite()
    all_sections = SECT + NEW_SECT
    missing = []
    for _, rows in all_sections:
        for case_id, _c, _e, test in rows:
            status = results.get(test)
            if status != "ok":
                missing.append(f"{case_id}: {test} -> {status or 'NOT FOUND'}")
    if missing or code != 0:
        sys.exit("Build stopped. These cases did not pass:\n  " + "\n  ".join(missing or ["(suite failed)"]))

    n_auto_cases = sum(len(rows) for _, rows in all_sections)
    n_tests = int(summary.group(1))
    manual = MANUAL_OLD + MANUAL_NEW
    count = lambda word, rows: sum(1 for r in rows if r[3] == word)
    commit, branch = git("rev-parse", "--short", "HEAD"), git("rev-parse", "--abbrev-ref", "HEAD")

    base = ParagraphStyle("b", fontName="Helvetica", fontSize=8.6, leading=10.8)
    head = ParagraphStyle("h", parent=base, textColor=colors.white, fontSize=9)
    title = ParagraphStyle("t", fontName="Helvetica", fontSize=20, leading=26, textColor=GREEN, spaceAfter=4)
    sub = ParagraphStyle("s", parent=base, fontSize=10, leading=14, textColor=colors.HexColor("#444444"), spaceAfter=10)
    h2 = ParagraphStyle("h2", fontName="Helvetica", fontSize=12.5, leading=17, textColor=GREEN, spaceBefore=12, spaceAfter=5, keepWithNext=1)
    note = ParagraphStyle("n", parent=base, fontSize=9, leading=12.5, spaceAfter=4)

    def table(rows, widths, header=("ID", "Test case", "Expected result", "Result")):
        data = [[Paragraph(h, head) for h in header]] + [[Paragraph(str(c), base) for c in r] for r in rows]
        t = Table(data, colWidths=widths, repeatRows=1)
        style = [("BACKGROUND", (0, 0), (-1, 0), GREEN), ("GRID", (0, 0), (-1, -1), 0.4, GRID),
                 ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 4),
                 ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]
        style += [("BACKGROUND", (0, i), (-1, i), ZEBRA) for i in range(2, len(data), 2)]
        t.setStyle(TableStyle(style))
        return t

    W = [18 * mm, 58 * mm, 74 * mm, 22 * mm]
    story = [
        Paragraph("Basera - Test Cases", title),
        Paragraph(
            f"{n_tests} automated tests (Django test suite, run on PostgreSQL 18) covering {n_auto_cases} cases, "
            f"and {len(manual)} manual tests. Automated: all passing. Manual: {count('Pass', manual)} passed, "
            f"{count('Carried over', manual)} carried over, {count('Not re-run', manual)} not re-run. "
            f"Deployment readiness: {count('Pass', DEPLOY)} passed, {count('Open', DEPLOY)} open.", sub),
        Paragraph(f"Run on the dev branch (commit {commit}, branch {branch}) on {date.today():%d %B %Y}. "
                  "Sections A1 to A6 and tests M-01 to M-19 are Shehroze's original cases, re-run on dev. "
                  "Sections A7 to A21, M-20 to M-47 and section C were added after the catalogue, cart, grow profile, "
                  "matching and landing page work was merged, and production setup was added. A21 covers My Profile (US-05).", note),
        Paragraph("Result words: Pass = performed and passed. Carried over = the files are unchanged since Shehroze's "
                  "passing run (checked with git diff). Not re-run = could not be repeated in this run (reason given). "
                  "Open = a known gap to close before release.", note),
    ]
    for heading, rows in all_sections:
        story.append(Paragraph(heading, h2))
        story.append(table([(i, c, e, "Pass") for i, c, e, _ in rows], W))
    story.append(Paragraph("B. Manual tests (browser and terminal)", h2))
    story.append(table(manual, W))
    story.append(Paragraph("C. Deployment readiness (manage.py check --deploy and file review)", h2))
    story.append(table(DEPLOY, W))
    story.append(Paragraph("D. Findings from this run", h2))
    for f in FINDINGS:
        story.append(Paragraph("- " + f, note))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#777777"))
        canvas.drawString(15 * mm, 10 * mm, "Basera - Test cases")
        canvas.drawRightString(A4[0] - 15 * mm, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()

    SimpleDocTemplate(str(out), pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm,
                      bottomMargin=18 * mm, title="Basera - Test Cases").build(story, onFirstPage=footer, onLaterPages=footer)
    print(f"Wrote {out}: {n_tests} automated tests, {n_auto_cases} cases, {len(manual)} manual, {len(DEPLOY)} deployment checks")


if __name__ == "__main__":
    build(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "testing" / "Basera_Test_Cases.pdf")
