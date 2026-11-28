"""Production setup (test-case section A17): settings, build files and the production seed."""

import os
import re
import secrets
import subprocess
import sys
import tempfile
from io import StringIO
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, TestCase, override_settings

from catalog.models import PlantSpecies

from .envconfig import csv, database_from_url, flag

ROOT = Path(__file__).resolve().parent.parent
User = get_user_model()


class EnvHelperTests(SimpleTestCase):
    def test_dp01_flag_reads_yes_and_no_words_in_any_case(self):
        for word in ("1", "true", "TRUE", " yes ", "On"):
            with mock.patch.dict(os.environ, {"X": word}):
                self.assertTrue(flag("X", False), word)
        for word in ("0", "false", "no", "off", "banana"):
            with mock.patch.dict(os.environ, {"X": word}):
                self.assertFalse(flag("X", True), word)

    def test_dp02_flag_uses_the_default_when_unset_or_blank(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("X", None)
            self.assertTrue(flag("X", True))
            self.assertFalse(flag("X", False))
        with mock.patch.dict(os.environ, {"X": "  "}):
            self.assertTrue(flag("X", True))

    def test_dp03_csv_gives_a_clean_list(self):
        with mock.patch.dict(os.environ, {"H": " a.com , ,b.com,"}):
            self.assertEqual(csv("H"), ["a.com", "b.com"])
        with mock.patch.dict(os.environ, {"H": ""}):
            self.assertEqual(csv("H"), [])

    def test_dp04_database_url_becomes_a_django_database_entry(self):
        config = database_from_url("postgres://basera_app:p%40ss@db.example.com:5433/basera?sslmode=require")
        self.assertEqual(config["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual((config["USER"], config["PASSWORD"], config["HOST"], config["PORT"], config["NAME"]),
                         ("basera_app", "p@ss", "db.example.com", "5433", "basera"))
        self.assertEqual(config["OPTIONS"], {"sslmode": "require"})

    def test_dp05_a_database_url_without_a_port_uses_5432(self):
        self.assertEqual(database_from_url("postgresql://u:p@host/db")["PORT"], "5432")

    def test_dp06_bad_database_urls_are_refused(self):
        for bad in ("mysql://u:p@h/db", "postgres://u:p@h/", "postgres:///db"):
            with self.subTest(url=bad), self.assertRaises(ImproperlyConfigured):
                database_from_url(bad)


def run_django(*args, **env):
    """Run manage.py in a fresh process with the given environment (settings load once per process)."""
    full = {**os.environ, "DATABASE_URL": "postgres://u:p@localhost:5432/unused"}
    for name in ("DEBUG", "SECRET_KEY", "ALLOWED_HOSTS", "RENDER", "RENDER_EXTERNAL_HOSTNAME", "EMAIL_ADDRESS",
                 "EMAIL_APP_PASSWORD", "SECURE_SSL_REDIRECT", "SERVE_MEDIA"):
        full[name] = ""
    full.update(env)
    return subprocess.run([sys.executable, "manage.py", *args], cwd=ROOT, env=full, capture_output=True, text=True)


class ProductionSettingsTests(SimpleTestCase):
    PROD = {"DEBUG": "False", "ALLOWED_HOSTS": "basera.example.com"}

    def secret(self):
        return secrets.token_urlsafe(60)

    def test_dp07_production_passes_the_django_deploy_check_except_two_optional_hsts_extras(self):
        done = run_django("check", "--deploy", **self.PROD, SECRET_KEY=self.secret(),
                          EMAIL_ADDRESS="team@example.com", EMAIL_APP_PASSWORD="abcdabcdabcdabcd")
        issues = set(re.findall(r"\((security|mail|staticfiles|urls|templates)\.([EWC]\d+)\)", done.stdout + done.stderr))
        self.assertEqual({f"{a}.{b}" for a, b in issues}, {"security.W005", "security.W021"}, done.stdout + done.stderr)

    def test_dp08_with_debug_off_the_site_refuses_to_start_without_a_secret_key(self):
        done = run_django("check", **self.PROD)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("SECRET_KEY", done.stderr)

    def test_dp09_with_debug_off_the_site_refuses_to_start_without_allowed_hosts(self):
        done = run_django("check", DEBUG="False", SECRET_KEY=self.secret())
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("ALLOWED_HOSTS", done.stderr)

    def test_dp10_running_on_render_turns_debug_off_by_itself(self):
        # RENDER=true and no DEBUG setting: if debug were still on, this would start fine.
        done = run_django("check", RENDER="true")
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("SECRET_KEY", done.stderr)

    def test_dp11_render_adds_its_own_address_to_hosts_and_trusted_origins(self):
        done = run_django("shell", "-c", "from django.conf import settings as s; print(s.ALLOWED_HOSTS, s.CSRF_TRUSTED_ORIGINS)",
                          RENDER="true", SECRET_KEY=self.secret(), RENDER_EXTERNAL_HOSTNAME="basera-1a2b.onrender.com")
        self.assertIn("basera-1a2b.onrender.com", done.stdout)
        self.assertIn("https://basera-1a2b.onrender.com", done.stdout)

    def test_dp12_local_development_keeps_working_without_any_of_this(self):
        done = run_django("check", DEBUG="True")
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_dp13_in_production_cookies_are_secure_and_https_is_forced(self):
        done = run_django("shell", "-c", "from django.conf import settings as s; print(s.SESSION_COOKIE_SECURE, s.CSRF_COOKIE_SECURE, s.SECURE_SSL_REDIRECT, s.SECURE_HSTS_SECONDS, s.SECURE_PROXY_SSL_HEADER)",
                          **self.PROD, SECRET_KEY=self.secret())
        self.assertIn("True True True 3600 ('HTTP_X_FORWARDED_PROTO', 'https')", done.stdout)


class BuildFileTests(SimpleTestCase):
    def test_dp14_whitenoise_and_gunicorn_are_installed_requirements(self):
        text = (ROOT / "requirements.txt").read_text().lower()
        self.assertIn("gunicorn==", text)
        self.assertIn("whitenoise==", text)
        self.assertIn("whitenoise.middleware.WhiteNoiseMiddleware", settings.MIDDLEWARE)

    def test_dp15_the_build_script_collects_static_migrates_and_seeds_in_that_order(self):
        script = ROOT / "build.sh"
        self.assertTrue(os.access(script, os.X_OK), "build.sh must be executable")
        text = script.read_text()
        self.assertIn("errexit", text)
        positions = [text.index(c) for c in ("pip install", "collectstatic", "migrate", "seed_catalog")]
        self.assertEqual(positions, sorted(positions))

    def test_dp16_the_render_blueprint_describes_the_site_without_secrets(self):
        text = (ROOT / "render.yaml").read_text()
        for needle in ("buildCommand: ./build.sh", "gunicorn basera_site.wsgi", "$PORT", "DATABASE_URL",
                       'key: DEBUG', 'value: "False"', "generateValue: true", "SEED_DEMO_ACCOUNTS"):
            self.assertIn(needle, text)
        for secret in ("ADMIN_PASSWORD", "EMAIL_APP_PASSWORD"):
            self.assertRegex(text, rf"key: {secret}[^\n]*\n\s*sync: false",
                             f"{secret} must be set on the dashboard, not in the file")

    def test_dp17_secrets_and_build_output_stay_out_of_git(self):
        ignored = (ROOT / ".gitignore").read_text().splitlines()
        for name in (".env", "staticfiles/", "media/"):
            self.assertIn(name, ignored)


@override_settings(SEED_DEMO_ACCOUNTS=False)
class ProductionSeedTests(TestCase):
    def seed(self, **env):
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media), \
                mock.patch.dict(os.environ, {"ADMIN_EMAIL": "", "ADMIN_PASSWORD": "", **env}):
            out = StringIO()
            call_command("seed_catalog", stdout=out)
            return out.getvalue(), media

    def test_dp18_no_demo_logins_and_no_shared_password_in_production(self):
        output, _ = self.seed()
        self.assertEqual(PlantSpecies.objects.count(), 35)
        self.assertEqual(list(User.objects.values_list("email", flat=True)), ["seller@basera.test"])
        self.assertFalse(User.objects.get().has_usable_password())
        self.assertNotIn("with password", output)  # the demo accounts print "Created X with password: ..."

    def test_dp19_a_real_admin_is_created_from_the_environment(self):
        self.seed(ADMIN_EMAIL="owner@example.com", ADMIN_PASSWORD="Kite-Orchard-Lantern-7391")
        admin = User.objects.get(email="owner@example.com")
        self.assertTrue(admin.is_superuser)
        self.assertEqual(admin.role, User.Role.ADMIN)
        self.assertTrue(admin.check_password("Kite-Orchard-Lantern-7391"))

    def test_dp20_a_weak_admin_password_stops_the_seed(self):
        with self.assertRaises(CommandError):
            self.seed(ADMIN_EMAIL="owner@example.com", ADMIN_PASSWORD="12345678")
        self.assertFalse(User.objects.filter(email="owner@example.com").exists())

    def test_dp21_running_it_again_keeps_the_admin_and_changes_nothing(self):
        env = dict(ADMIN_EMAIL="owner@example.com", ADMIN_PASSWORD="Kite-Orchard-Lantern-7391")
        self.seed(**env)
        before = (User.objects.count(), PlantSpecies.objects.count())
        self.seed(**env)
        self.assertEqual(before, (User.objects.count(), PlantSpecies.objects.count()))

    def test_dp22_a_photo_file_that_disappeared_is_put_back(self):
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            call_command("seed_catalog", stdout=StringIO())
            neem = PlantSpecies.objects.get(common_name="Neem")
            path = Path(neem.image.path)
            self.assertTrue(path.exists())
            path.unlink()  # what a host does to its disk on restart
            call_command("seed_catalog", stdout=StringIO())
            self.assertTrue(Path(PlantSpecies.objects.get(common_name="Neem").image.path).exists())


@override_settings(SERVE_MEDIA=True)
class MediaServingTests(SimpleTestCase):
    def test_dp23_the_media_route_never_serves_files_outside_the_media_folder(self):
        # The URL config is read at start-up, so this checks the route in a fresh process.
        done = run_django("shell", "-c",
                          "from django.test import Client\n"
                          "c = Client(HTTP_HOST='localhost')\n"
                          "a, b = c.get('/media/../manage.py'), c.get('/media/%2e%2e/manage.py')\n"
                          "print(a.status_code, b.status_code, b'import os' in a.content + b.content)",
                          DEBUG="True", SERVE_MEDIA="True")
        # Refused (400 or 404), and the file's contents never came back.
        self.assertRegex(done.stdout, r"\b(400|404) (400|404) False\b", done.stdout + done.stderr)
