
CREATE TABLE IF NOT EXISTS convidados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS presentes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    reservado INTEGER NOT NULL DEFAULT 0,
    quantidade_total INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS tokens_convidados (
    token_hash TEXT PRIMARY KEY,
    convidado_id INTEGER NOT NULL,
    FOREIGN KEY (convidado_id) REFERENCES convidados(id)
);

CREATE TABLE IF NOT EXISTS reservas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    convidado_id INTEGER NOT NULL,
    presente_id INTEGER NOT NULL,
    criado_em TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (convidado_id, presente_id),
    FOREIGN KEY (convidado_id) REFERENCES convidados(id),
    FOREIGN KEY (presente_id) REFERENCES presentes(id)
);
