import importlib.util
import sys
import os

ROOT = r"c:\xampp\htdocs\soy-grandez-engine"
sys.path.insert(0, ROOT)
os.chdir(ROOT)


def load(name, rel):
    path = os.path.join(ROOT, rel.replace("/", os.sep))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


print("=== Cargando EmailOTPService ===")
load("services.email_otp_service", "services/email_otp_service.py")
from services.email_otp_service import EmailOTPService  # noqa: E402

pub = [m for m in dir(EmailOTPService) if not m.startswith("_")]
print("EmailOTPService public members:", pub)
print("get_disney_otp_via_imap OK?", hasattr(EmailOTPService, "get_disney_otp_via_imap"))

print()
print("=== Sembrando módulos de paquetes ===")
for pkg, rel in [
    ("config", "config/__init__.py"),
    ("config.settings", "config/settings.py"),
    ("core", "core/__init__.py"),
    ("core.exceptions", "core/exceptions.py"),
    ("core.logger", "core/logger.py"),
    ("services", "services/__init__.py"),
    ("services.browser_manager", "services/browser_manager.py"),
    ("services.capsolver_service", "services/capsolver_service.py"),
    ("services.laravel_api_client", "services/laravel_api_client.py"),
    ("services.auth_service", "services/auth_service.py"),
    ("database", "database/__init__.py"),
    ("database.models", "database/models.py"),
    ("database.connection", "database/connection.py"),
    ("database.repository", "database/repository.py"),
    ("services.orchestrator_service", "services/orchestrator_service.py"),
    ("core.task_manager", "core/task_manager.py"),
    ("scrapers", "scrapers/__init__.py"),
    ("scrapers.base_scraper", "scrapers/base_scraper.py"),
]:
    try:
        load(pkg, rel)
    except Exception as e:
        print(f"WARN: no se pudo cargar {pkg}: {e}")

print("=== Cargando DisneyScraper ===")
load("scrapers.disney_scraper", "scrapers/disney_scraper.py")
from scrapers.disney_scraper import DisneyScraper  # noqa: E402

members_pub = [m for m in dir(DisneyScraper) if not m.startswith("_")]
print("DisneyScraper public methods:", members_pub)
required = [
    "login",
    "revoke_devices",
    "rotate_password",
    "update_profile_pin",
    "run_full_rotation",
    "generate_secure_password",
]
for r in required:
    print(f"  - {r}: {r in members_pub}")

print()
print("=== Prueba generate_secure_password ===")
pwd = DisneyScraper.generate_secure_password(20)
print("Sample:", pwd)
print(
    "len=", len(pwd),
    "upper=", any(c.isupper() for c in pwd),
    "lower=", any(c.islower() for c in pwd),
    "digit=", any(c.isdigit() for c in pwd),
    "symbol=", any(c in "-_.!@#$%^&*" for c in pwd),
)

print()
print("=== Validando forma del diccionario en run_full_rotation ===")
import inspect
src = inspect.getsource(DisneyScraper.run_full_rotation)
keys_to_check = [
    '"success":',
    '"platform":',
    '"username":',
    '"profile_name":',
    '"profile_pin":',
    '"new_password":',
    '"steps":',
    '"login": False',
    '"revoke_devices": False',
    '"rotate_password": False',
    '"update_pin": False',
    '"error":',
]
for k in keys_to_check:
    print(f"  {k!r:40s} -> {k in src}")

print()
print("=== Comprobación imports globales scrapers.__init__ ===")
from scrapers import DisneyScraper as DS2
print("DisneyScraper importable via scrapers package?", DS2 is DisneyScraper)

print()
print("TODO OK.")
