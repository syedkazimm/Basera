from django.urls import path

from . import views

urlpatterns = [
    path("", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("signup/", views.signup_view, name="signup"),
    path("forgot-password/", views.ForgotPasswordView.as_view(), name="forgot_password"),
    path("reset/<uidb64>/<token>/", views.ResetPasswordView.as_view(), name="password_reset_confirm"),
    path("home/", views.home_view, name="home"),
    path("profile/", views.profile_view, name="profile"),
    path("privacy/", views.placeholder, {"page_name": "Privacy"}, name="privacy"),
    path("terms/", views.placeholder, {"page_name": "Terms"}, name="terms"),
    path("help/", views.placeholder, {"page_name": "Help"}, name="help"),
    # Header links to pages that later stories build; replace these when they exist.
    path("about/", views.coming_soon, {"page_name": "About"}, name="about"),
    path("password/", views.coming_soon, {"page_name": "Change password"}, name="change_password"),
    path("orders/", views.coming_soon, {"page_name": "My orders"}, name="my_orders"),
    path("seller/listings/", views.coming_soon, {"page_name": "My Listings"}, name="seller_listings"),
    path("seller/orders/", views.coming_soon, {"page_name": "Orders"}, name="seller_orders"),
    path("seller/earnings/", views.coming_soon, {"page_name": "Earnings"}, name="seller_earnings"),
    path("seller/guide/", views.coming_soon, {"page_name": "Packing guide"}, name="seller_guide"),
    path("manage/users/", views.coming_soon, {"page_name": "Users"}, name="admin_users"),
    path("manage/reports/", views.coming_soon, {"page_name": "Reports"}, name="admin_reports"),
    path("manage/settings/", views.coming_soon, {"page_name": "Settings"}, name="admin_settings"),
]
