"""Configuração de logging por serviço."""
import logging

from medwatch.config import get_settings


def setup_logging(service: str) -> None:
    """Configura o logging raiz com o nome do serviço no formato."""
    logging.basicConfig(
        level=get_settings().log_level.upper(),
        format="%(asctime)s %(levelname)s [" + service + "] %(name)s: %(message)s",
    )
