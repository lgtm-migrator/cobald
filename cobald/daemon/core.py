import sys
import logging
import platform

from .logger import initialise_logging
from .config.yaml import load_configuration
from .cli import CLI
from . import runner
from .. import __about__


def core(configuration: str, level: str, target: str, short_format: bool):
    initialise_logging(level=level, target=target, short_format=short_format)
    logger = logging.getLogger(__package__)
    logger.info('COBalD %s', __about__.__version__)
    logger.info(__about__.__url__)
    logger.info('%s %s (%s)', platform.python_implementation(), platform.python_version(), sys.executable)
    pipeline = load_configuration(configuration)
    logger.info('Running main event loop...')
    runner.run()


def main():
    options = CLI.parse_args()
    core(options.CONFIGURATION, options.log_level, options.log_target, options.log_journal)