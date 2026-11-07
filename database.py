
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

            GREATEST(
                p.quantidade_total
                - COALESCE((
                    SELECT SUM(r.quantidade)
                    FROM reservas AS r
                    WHERE r.presente_id = p.id
                ), 0),
                0
            ) AS disponiveis,

            EXISTS (
                SELECT 1
                FROM reservas AS r
                WHERE r.presente_id = p.id
                  AND r.convidado_id = %s
            ) AS selecionado_por_mim,

            COALESCE((
                SELECT SUM(r.quantidade)
                FROM reservas AS r
                WHERE r.presente_id = p.id
                  AND r.convidado_id = %s
            ), 0) AS quantidade_selecionada

        FROM presentes AS p

        ORDER BY lower(p.nome)
        """,
        (convidado_id, convidado_id),
    ).fetchall()


# ==========================================
# CONTAR UNIDADES RESERVADAS PELO CONVIDADO
# ==========================================

def contar_reservas(convidado_id):
    db = get_db()

    return db.execute(
        """
        SELECT COALESCE(SUM(quantidade), 0) AS total
        FROM reservas
        WHERE convidado_id = %s
        """,
        (convidado_id,),
    ).fetchone()["total"]


# ==========================================
# RESERVAR PRESENTES
# ==========================================

def reservar_presentes(convidado_id, presentes):
    db = get_db()

    if not isinstance(presentes, list) or not presentes:
        return False, "Selecione pelo menos um presente."

    presentes_normalizados = []
    ids_recebidos = set()

    # Valida os dados recebidos do JavaScript.
    for item in presentes:

        if not isinstance(item, dict):
            return False, "Dados de reserva inválidos."

        presente_id = item.get("id")
        quantidade = item.get("quantidade")

        # bool também é considerado int em Python,
        # por isso fazemos a validação explicitamente.
        if (
            isinstance(presente_id, bool)
            or not isinstance(presente_id, int)
            or presente_id <= 0
        ):
            return False, "Identificação de presente inválida."

        if (
            isinstance(quantidade, bool)
            or not isinstance(quantidade, int)
            or quantidade <= 0
        ):
            return False, "Quantidade de presente inválida."

        if presente_id in ids_recebidos:
            return False, "Um presente foi selecionado mais de uma vez."

        ids_recebidos.add(presente_id)

        presentes_normalizados.append({
            "id": presente_id,
            "quantidade": quantidade
        })

    quantidade_nova = sum(
        item["quantidade"]
        for item in presentes_normalizados
    )

    if quantidade_nova > 2:
        return (
            False,
            "Você pode escolher no máximo duas unidades de presentes."
        )

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

            # Soma as unidades já reservadas.
            quantidade_atual = db.execute(
                """
                SELECT COALESCE(SUM(quantidade), 0) AS total
                FROM reservas
                WHERE convidado_id = %s
                """,
                (convidado_id,),
            ).fetchone()["total"]

            if quantidade_atual + quantidade_nova > 2:
                return (
                    False,
                    "Você já utilizou suas duas unidades de presentes."
                )

            # Bloqueia os presentes selecionados para
            # evitar que duas pessoas reservem a última unidade.
            ids_presentes = [
                item["id"]
                for item in presentes_normalizados
            ]

            presentes_banco = db.execute(
                """
                SELECT
                    id,
                    quantidade_total
                FROM presentes
                WHERE id = ANY(%s)
                ORDER BY id
                FOR UPDATE
                """,
                (ids_presentes,),
            ).fetchall()

            if len(presentes_banco) != len(ids_presentes):
                return (
                    False,
                    "Um dos presentes selecionados não existe."
                )

            presentes_por_id = {
                presente["id"]: presente
                for presente in presentes_banco
            }

            # Confere se o convidado já reservou algum
            # dos presentes selecionados.
            for item in presentes_normalizados:

                ja_reservado = db.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM reservas
                        WHERE convidado_id = %s
                          AND presente_id = %s
                    ) AS existe
                    """,
                    (convidado_id, item["id"]),
                ).fetchone()["existe"]

                if ja_reservado:
                    return (
                        False,
                        "Você já reservou um desses presentes."
                    )

                presente = presentes_por_id[item["id"]]

                quantidade_reservada = db.execute(
                    """
                    SELECT COALESCE(SUM(quantidade), 0) AS total
                    FROM reservas
                    WHERE presente_id = %s
                    """,
                    (item["id"],),
                ).fetchone()["total"]

                disponiveis = (
                    presente["quantidade_total"]
                    - quantidade_reservada
                )

                if item["quantidade"] > disponiveis:
                    return (
                        False,
                        "A quantidade disponível desse presente mudou. Atualize a página e tente novamente."
                    )

            # Insere uma linha por presente, guardando
            # a quantidade escolhida naquela linha.
            with db.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO reservas (
                        convidado_id,
                        presente_id,
                        quantidade
                    )
                    VALUES (%s, %s, %s)
                    """,
                    [
                        (
                            convidado_id,
                            item["id"],
                            item["quantidade"]
                        )
                        for item in presentes_normalizados
                    ],
                )

        return True, "Presentes escolhidos com sucesso!"

    except psycopg.errors.UniqueViolation:
        return (
            False,
            "Você já reservou um desses presentes."
        )


# ==========================================
# ADICIONAR PRESENTE
# ==========================================

def adicionar_presente(nome, quantidade=1):
    db = get_db()

    if not isinstance(quantidade, int) or quantidade < 1:
        raise ValueError("A quantidade precisa ser maior que zero.")

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
