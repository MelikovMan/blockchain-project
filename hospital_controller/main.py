import logging
import os

from pkg import config_parse
from internal.domain import config as cfg
from internal.admin_provider.admin_provider import AdminProvider
from internal.handlers.handlers import Handler
from internal.regulator_repo.repo import HospitalRepo
from internal.http_adapter.http_adapter import run_http_adapter


config = cfg.Config
config = config_parse.get_config(config)

admin_provider = AdminProvider(config.Adapters.Secondary.AdminProvider)
repo = None
try:
    repo = HospitalRepo(config.Adapters.Secondary.RegulatorRepo)
except Exception as e:
    # БД опциональна; без неё проект сможет жить (разрешения будут храниться только в памяти)
    print(f"[WARN] Cannot init Postgres repo: {e}")

handler = Handler(
    admin_provider=admin_provider,
    repo=repo,
    regulator_did=config.Regulator.DID,
    regulator_alias=config.Regulator.Alias,
)

os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/hospital.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

run_http_adapter(
    handler=handler,
    config=config.Adapters.Primary.HttpAdapter,
)
