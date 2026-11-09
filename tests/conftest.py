"""Limpeza das linhas que os testes criam no banco real.

Os testes de banco e de API usam ids `T-<hex>` e gravam no mesmo PostgreSQL que o stack usa.
Sem esta limpeza, pacientes, alertas e mídias de teste ficam no banco e aparecem no dashboard.
Só linhas com patient_id começando em `T-` são apagadas (nunca `P-` nem `M-`).
"""
import pytest
from sqlalchemy import text

_PATIENT_TABLES = ("alerts", "risk_snapshots", "evidence", "vitals", "prescriptions",
                   "movement", "media", "patients")


def _purge_test_rows() -> None:
    try:
        from medwatch import db

        with db.get_engine().begin() as conn:
            conn.execute(text(
                "DELETE FROM transcripts WHERE media_id IN "
                "(SELECT media_id FROM media WHERE patient_id LIKE 'T-%')"))
            for table in _PATIENT_TABLES:
                conn.execute(text(f"DELETE FROM {table} WHERE patient_id LIKE 'T-%'"))
    except Exception:
        pass  # sem banco acessível (ou sem tabelas): não há o que limpar


@pytest.fixture(scope="session", autouse=True)
def _clean_test_rows():
    _purge_test_rows()  # restos de execuções anteriores
    yield
    _purge_test_rows()
