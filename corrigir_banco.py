
import sqlite3
from app import app

with app.app_context():
    from database import get_db

    db = get_db()

    # Mostra os nomes duplicados antes da correção.
    duplicados = db.execute("""
        SELECT nome, COUNT(*) AS quantidade
        FROM convidados
        GROUP BY nome COLLATE NOCASE
        HAVING COUNT(*) > 1
    """).fetchall()

    print("\nNomes duplicados encontrados:")

    if not duplicados:
        print("Nenhum.")
    else:
        for pessoa in duplicados:
            print(f"{pessoa['nome']}: {pessoa['quantidade']} registros")

    # Mantém um cadastro por nome.
    # Preserva o registro de menor ID.
    db.execute("""
        DELETE FROM convidados
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM convidados
            GROUP BY nome COLLATE NOCASE
        )
    """)

    db.commit()

    # Cria a proteção contra nomes duplicados.
    db.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_convidados_nome_unico
        ON convidados(nome COLLATE NOCASE)
    """)

    db.commit()

    print("\nBanco corrigido com sucesso!")
