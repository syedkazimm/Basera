"""Grow profiles: describe a growing space and list the saved ones (US-06), and edit them (US-07).

Profiles are private. Every query here is filtered to request.user, so another
customer's profile can't be seen or used (it answers 404, not 403, so its
existence isn't revealed).
"""

from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.ui import page_band

from matching.services import CRITERION_LABELS, WEIGHTS

from . import choices
from .forms import GrowProfileForm
from .models import GrowProfile


def customer_required(view):
    """Log in first; sellers and admins have no grow profiles, so send them home."""

    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_customer:
            messages.error(request, "Grow profiles are for customer accounts.")
            return redirect("home")
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


@customer_required
def profile_list(request):
    profiles = list(GrowProfile.objects.filter(user=request.user).select_related("region"))
    for profile in profiles:
        profile.summary = describe(profile)
    context = {
        "profiles": profiles,
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


def _weight_bars():
    """The "How matching works" panel beside the form."""
    # The bars are drawn against 33 (the longest bar in the design is Sunlight's 30 points).
    return [{"label": CRITERION_LABELS[k], "points": w, "bar": round(w / 33 * 100)} for k, w in WEIGHTS.items()]
