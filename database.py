
import hashlib
import os

import psycopg
from psycopg.rows import dict_row
from flask import current_app, g


# ==========================================
# LISTA INICIAL DE PRESENTES
# ==========================================

PRESENTES_INICIAIS = [
    ("Jogo de panelas", 1),
    ("Frigideira antiaderente", 1),
    ("Panela de pressão", 1),
    ("Jogo de pratos", 1),
    ("Jogo de copos", 1),
    ("Talheres (jogo completo)", 1),
    ("Conjunto de xícaras", 1),
    ("Potes organizadores", 1),
    ("Escorredor de louças", 1),
    ("Tábua de corte", 1),
    ("Jogo de lençol", 2),
]


# ==========================================
# CONEXÃO COM POSTGRESQL
# ==========================================

def get_db():
    if "db" not in g:
        g.db = psycopg.connect(
            current_app.config["DATABASE_URL"],
            row_factory=dict_row,
            connect_timeout=15,
            application_name="cha-panela",
            autocommit=True
        )

    return g.db


def close_db(error=None):
    db = g.pop("db", None)

    if db is not None:
        db.close()


# ==========================================
# INICIALIZAÇÃO DO BANCO
# ==========================================

def init_db():
    db = get_db()

    schema_path = os.path.join(
        current_app.root_path,
        "schema.sql",
    )

    with open(schema_path, "r", encoding="utf-8") as arquivo:
        comandos = [
            comando.strip()
            for comando in arquivo.read().split(";")
            if comando.strip()
        ]

    with db.transaction():

        # Evita que diferentes processos insiram
        # a lista inicial simultaneamente.
        db.execute(
            """
            SELECT pg_advisory_xact_lock(
                hashtextextended('cha-panela-seed', 0)
            )
            """
        )

        for comando in comandos:
            db.execute(comando)

        quantidade = db.execute(
            """
            SELECT COUNT(*) AS total
            FROM presentes
            """
        ).fetchone()["total"]

        if quantidade == 0:
            # No Psycopg 3, executemany pertence ao cursor.
            with db.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO presentes (
                        nome,
                        quantidade_total
                    )
                    VALUES (%s, %s)
                    """,
                    PRESENTES_INICIAIS,
                )


def init_app(app):
    app.teardown_appcontext(close_db)

    with app.app_context():
        init_db()


# ==========================================
# HASH DOS TOKENS
# ==========================================

def gerar_hash(token):
    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


# ==========================================
# CRIAR OU LOCALIZAR CONVIDADO
# ==========================================

def criar_ou_obter_convidado(nome, token):
    db = get_db()

    token_hash = gerar_hash(token)
    nome_normalizado = nome.strip().lower()

    with db.transaction():

        # Evita dois cadastros simultâneos
        # para o mesmo nome.
        db.execute(
            """
            SELECT pg_advisory_xact_lock(
                hashtextextended(%s, 0)
            )
            """,
            (nome_normalizado,),
        )

        convidado = db.execute(
            """
            SELECT id, nome
            FROM convidados
            WHERE lower(trim(nome)) = lower(trim(%s))
            LIMIT 1
            """,
            (nome,),
        ).fetchone()

        ja_cadastrado = convidado is not None

        if convidado is None:
            convidado = db.execute(
                """
                INSERT INTO convidados (nome)
                VALUES (%s)
                RETURNING id, nome
                """,
                (nome,),
            ).fetchone()

        # Cada acesso recebe seu próprio token.
        db.execute(
            """
            INSERT INTO tokens_convidados (
                token_hash,
                convidado_id
            )
            VALUES (%s, %s)
            """,
            (
                token_hash,
                convidado["id"],
            ),
        )

    return convidado, ja_cadastrado


# ==========================================
# BUSCAR CONVIDADO PELO TOKEN
# ==========================================

def buscar_convidado(token):
    db = get_db()

    token_hash = gerar_hash(token)

    return db.execute(
        """
        SELECT
            c.id,
            c.nome
        FROM tokens_convidados AS t
        JOIN convidados AS c
            ON c.id = t.convidado_id
        WHERE t.token_hash = %s
        """,
        (token_hash,),
    ).fetchone()


# ==========================================
# LISTAR CONVIDADOS
# ==========================================

def listar_convidados():
    db = get_db()

    return db.execute(
        """
        SELECT id, nome
        FROM convidados
        ORDER BY lower(nome)
        """
    ).fetchall()


# ==========================================
# LISTAR PRESENTES
# ==========================================

def listar_presentes(convidado_id):
    db = get_db()

    return db.execute(
        """
        SELECT
            p.id,
            p.nome,
            p.quantidade_total,

            (
                p.quantidade_total
                - p.reservado
                - (
                    SELECT COUNT(*)
                    FROM reservas AS r
                    WHERE r.presente_id = p.id
                )
            ) AS disponiveis,

            EXISTS (
                SELECT 1
                FROM reservas AS r
                WHERE r.presente_id = p.id
                  AND r.convidado_id = %s
            ) AS selecionado_por_mim

        FROM presentes AS p

        ORDER BY lower(p.nome)
        """,
        (convidado_id,),
    ).fetchall()


# ==========================================
# CONTAR RESERVAS DO CONVIDADO
# ==========================================

def contar_reservas(convidado_id):
    db = get_db()

    return db.execute(
        """
        SELECT COUNT(*) AS total
        FROM reservas
        WHERE convidado_id = %s
        """,
        (convidado_id,),
    ).fetchone()["total"]


# ==========================================
# RESERVAR PRESENTES
# ==========================================

def reservar_presentes(convidado_id, presentes_ids):
    db = get_db()

    # Remove IDs repetidos, mantendo a ordem.
    presentes_ids = list(
        dict.fromkeys(presentes_ids)
    )

    if not presentes_ids:
        return False, "Selecione pelo menos um presente."

    try:
        with db.transaction():

            # Serializa reservas simultâneas
            # feitas pelo mesmo convidado.
            db.execute(
                """
                SELECT pg_advisory_xact_lock(
                    hashtextextended(%s, 0)
                )
                """,
                (f"convidado:{convidado_id}",),
            )

            quantidade_atual = db.execute(
                """
                SELECT COUNT(*) AS total
                FROM reservas
                WHERE convidado_id = %s
                """,
                (convidado_id,),
            ).fetchone()["total"]

            if quantidade_atual + len(presentes_ids) > 2:
                return (
                    False,
                    "Você pode escolher no máximo dois presentes."
                )

            # Bloqueia as linhas dos presentes selecionados.
            # Isso impede que duas pessoas reservem
            # a mesma última unidade simultaneamente.
            presentes = db.execute(
                """
                SELECT
                    id,
                    quantidade_total,
                    reservado
                FROM presentes
                WHERE id = ANY(%s)
                ORDER BY id
                FOR UPDATE
                """,
                (presentes_ids,),
            ).fetchall()

            if len(presentes) != len(presentes_ids):
                return (
                    False,
                    "Um dos presentes selecionados não existe."
                )

            # Confere a disponibilidade de cada presente.
            for presente in presentes:

                reservados = db.execute(
                    """
                    SELECT COUNT(*) AS total
                    FROM reservas
                    WHERE presente_id = %s
                    """,
                    (presente["id"],),
                ).fetchone()["total"]

                disponiveis = (
                    presente["quantidade_total"]
                    - presente["reservado"]
                    - reservados
                )

                if disponiveis <= 0:
                    return (
                        False,
                        "Um dos presentes acabou de ser escolhido."
                    )

            # Confirma todas as reservas na mesma transação.
            # Se alguma falhar, nenhuma será confirmada.
            with db.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO reservas (
                        convidado_id,
                        presente_id
                    )
                    VALUES (%s, %s)
                    """,
                    [
                        (convidado_id, presente_id)
                        for presente_id in presentes_ids
                    ],
                )

        return True, "Presentes escolhidos com sucesso!"

    except psycopg.errors.UniqueViolation:
        return (
            False,
            "Você já escolheu um desses presentes."
        )


# ==========================================
# ADICIONAR PRESENTE
# ==========================================

def adicionar_presente(nome, quantidade=1):
    db = get_db()

    with db.transaction():
        presente = db.execute(
            """
            INSERT INTO presentes (
                nome,
                quantidade_total
            )
            VALUES (%s, %s)
            RETURNING id
            """,
            (nome, quantidade),
        ).fetchone()

    return presente["id"]
