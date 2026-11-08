"""Cria os pacientes fictícios P-0001..P-0005."""
from medwatch import db


def main() -> None:
    for i in range(1, 6):
        db.upsert_patient(f"P-{i:04d}", f"Paciente {i:02d}", f"UTI-{i:02d}")
    print("Pacientes P-0001..P-0005 criados.")


if __name__ == "__main__":
    main()
