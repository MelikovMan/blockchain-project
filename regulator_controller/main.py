from pkg import config_parse
from internal.domain import config as cfg
from internal.admin_provider.admin_provider import AdminProvider
from internal.handlers.handlers import Handler
from internal.regulator_repo.repo import RegulatorRepo
from internal.http_adapter.http_adapter import run_http_adapter

import logging

config = cfg.Config
config = config_parse.get_config(config)

admin_provider = AdminProvider(config.Adapters.Secondary.AdminProvider)
regulator_repo = RegulatorRepo(config.Adapters.Secondary.RegulatorRepo)

handler = Handler(admin_provider, regulator_repo)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/regulator.log'),
        logging.StreamHandler()
    ]
)

http_adapter = run_http_adapter(
    handler=handler,
    config=config.Adapters.Primary.HttpAdapter,
)

