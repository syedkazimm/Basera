"""Grow profiles: describe a growing space and list the saved ones (US-06), then edit or delete them (US-07).

Profiles are private. Every query here is filtered to request.user, so another
customer's profile can't be seen or used (it answers 404, not 403, so its
existence isn't revealed).
"""

import json
from functools import wraps

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from accounts.ui import page_band

from matching.services import CRITERION_LABELS, WEIGHTS

from . import choices
from .forms import GrowProfileForm
from .models import GrowProfile


def _is_htmx(request):
    """True for the in-place requests the Delete buttons send."""
    return request.headers.get("HX-Request") == "true"


def _send_to(url):
    """Make htmx load a whole page, instead of swapping that page into part of this one."""
    response = HttpResponse(status=204)
    response["HX-Redirect"] = url
    return response


def customer_required(view):
    """Log in first; sellers and admins have no grow profiles, so send them home."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            if _is_htmx(request):
                # Come back to the list after logging in, not to a bare fragment.
                return _send_to(f"{reverse('login')}?next={reverse('grow_profiles')}")
            return redirect_to_login(request.get_full_path())
        if not request.user.is_customer:
            messages.error(request, "Grow profiles are for customer accounts.")
            return _send_to(reverse("home")) if _is_htmx(request) else redirect("home")
        return view(request, *args, **kwargs)

    return wrapper


def describe(profile):
    """The profile's answers as readable labels, for the list and results pages."""
    return {
        "region": profile.region.name,
        "space": choices.label_for(choices.SPACE_TYPES, profile.space_type),
        "sunlight": choices.label_for(choices.SUNLIGHT, profile.sunlight),
        "soil": choices.label_for(choices.SOILS, profile.soil_type),
        "water": choices.label_for(choices.WATER, profile.water_availability) + " water",
        "purpose": choices.label_for(choices.PURPOSES, profile.purpose),
    }


def _saved_profiles(user):
    """The customer's profiles, each with what its card shows."""
    profiles = list(GrowProfile.objects.filter(user=user).select_related("region"))
    for profile in profiles:
        profile.summary = describe(profile)
        profile.icon = choices.ICONS.get(profile.space_type, "home")
    return profiles


@customer_required
def profile_list(request):
    context = {
        "profiles": _saved_profiles(request.user),
        **page_band(request, "My grow profiles", "Your saved spaces and the plants that match them.",
                    ("My grow profiles", None)),
    }
    return render(request, "growprofiles/profile_list.html", context)


@customer_required
def profile_create(request):
    if request.method == "POST":
        form = GrowProfileForm(request.POST)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.user = request.user
            profile.save()
            messages.success(request, f"Saved “{profile.name}”. Your grow profile is ready.")
            return redirect("grow_profiles")
    else:
        form = GrowProfileForm()
    context = {
        "form": form,
        "heading": "Describe your space",
        "intro": "Answer six quick questions. You can change them later.",
        "submit_label": "Save grow profile",
        "weights": _weight_bars(),
        **page_band(request, "Create a grow profile", "Answer a few quick questions about your space.",
                    ("My grow profiles", reverse("grow_profiles")), ("New", None)),
    }
    return render(request, "growprofiles/profile_form.html", context)


@customer_required
def profile_edit(request, pk):
    """US-07: change a saved profile. Past orders only point at it, so they stay as they were."""
    profile = get_object_or_404(GrowProfile, pk=pk, user=request.user)
    saved_name = profile.name  # validating the form writes the typed name onto the profile
    if request.method == "POST":
        form = GrowProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, f"Saved your changes to “{profile.name}”.")
            return redirect("grow_profiles")
    else:
        form = GrowProfileForm(instance=profile)
    context = {
        "form": form,
        "heading": "Update your space",
        "intro": "Change any answer, then save. Your matches will follow.",
        "submit_label": "Save changes",
        "weights": _weight_bars(),
        **page_band(request, "Edit grow profile", f"Update the answers for {saved_name}.",
                    ("My grow profiles", reverse("grow_profiles")), ("Edit", None)),
    }
    return render(request, "growprofiles/profile_form.html", context)


@customer_required
@require_http_methods(["GET", "POST"])
def profile_delete(request, pk):
    """US-07: delete a profile, after asking. Orders that used it stay, with the link cleared.

    With htmx the question opens as a dialog over the list and the card goes
    without a reload; without JavaScript it is a page of its own.
    """
    profile = get_object_or_404(GrowProfile, pk=pk, user=request.user)
    if request.method == "POST":
        name = profile.name
        profile.delete()
        notice = f"Deleted “{name}”."
        if _is_htmx(request):
            response = render(request, "growprofiles/_delete_response.html",
                              {"profiles": _saved_profiles(request.user)})
            # htmx turns this into an event the page shows as a toast (see botanical.js).
            response["HX-Trigger"] = json.dumps({"basera:notice": {"message": notice, "level": "success"}})
            return response
        messages.success(request, notice)
        return redirect("grow_profiles")
    if _is_htmx(request):
        return render(request, "growprofiles/_delete_dialog.html", {"profile": profile})
    context = {
        "profile": profile,
        **page_band(request, "Delete grow profile", "Check this is the one you want to remove.",
                    ("My grow profiles", reverse("grow_profiles")), ("Delete", None)),
    }
    return render(request, "growprofiles/profile_confirm_delete.html", context)


def _weight_bars():
    """The "How matching works" panel beside the form."""
    # The bars are drawn against 33 (the longest bar in the design is Sunlight's 30 points).
    return [{"label": CRITERION_LABELS[k], "points": w, "bar": round(w / 33 * 100)} for k, w in WEIGHTS.items()]
