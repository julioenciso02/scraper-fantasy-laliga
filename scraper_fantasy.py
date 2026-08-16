import requests
from bs4 import BeautifulSoup
import json
import sqlite3
import pandas as pd
from datetime import datetime
from pathlib import Path


# ============================================================
# CONFIGURACIÓN
# ============================================================

URL = "https://www.analiticafantasy.com/fantasy-la-liga/mercado"

DB_FILE = "fantasy_laliga_v2.db"

CARPETA_CSV = Path("snapshots")
CARPETA_CSV.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/139.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}


# ============================================================
# EXTRAER ARRAY JSON
# ============================================================

def extraer_array_balanceado(texto, inicio):

    nivel = 0
    en_string = False
    escape = False

    for i in range(inicio, len(texto)):

        c = texto[i]

        if en_string:

            if escape:
                escape = False

            elif c == "\\":
                escape = True

            elif c == '"':
                en_string = False

            continue

        if c == '"':
            en_string = True

        elif c == "[":
            nivel += 1

        elif c == "]":

            nivel -= 1

            if nivel == 0:
                return texto[inicio:i + 1]

    raise Exception(
        "No se encontró el cierre del array"
    )


# ============================================================
# EXTRAER JUGADORES
# ============================================================

def extraer_jugadores(html):

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    scripts = soup.find_all("script")

    print(
        f"Número de scripts: {len(scripts)}"
    )

    script_objetivo = None
    numero_script = None

    for i, script in enumerate(scripts):

        texto = script.string

        if not texto:
            texto = script.get_text()

        if not texto:
            continue

        if "initialPlayers" in texto:

            script_objetivo = texto
            numero_script = i

            break

    if script_objetivo is None:

        raise Exception(
            "No se encontró initialPlayers"
        )

    print("Script encontrado")
    print(
        f"Número de script: {numero_script}"
    )

    print(
        f"Longitud: {len(script_objetivo)}"
    )


    # --------------------------------------------------------
    # LOCALIZAR initialPlayers
    # --------------------------------------------------------

    pos = script_objetivo.find(
        "initialPlayers"
    )

    if pos == -1:

        raise Exception(
            "No se encontró initialPlayers"
        )

    print(
        "initialPlayers encontrado"
    )

    print(
        f"Posición: {pos}"
    )


    # --------------------------------------------------------
    # RECUPERAR CADENA JAVASCRIPT
    # --------------------------------------------------------

    inicio_comillas = script_objetivo.find(
        '"'
    )

    fin_comillas = None

    escape = False

    for i in range(
        inicio_comillas + 1,
        len(script_objetivo)
    ):

        c = script_objetivo[i]

        if escape:

            escape = False
            continue

        if c == "\\":

            escape = True
            continue

        if c == '"':

            fin_comillas = i
            break


    cadena = script_objetivo[
        inicio_comillas + 1:
        fin_comillas
    ]


    # --------------------------------------------------------
    # DESESCAPAR
    # --------------------------------------------------------

    try:

        contenido = json.loads(
            '"' + cadena + '"'
        )

    except json.JSONDecodeError:

        contenido = cadena.replace(
            '\\"',
            '"'
        )


    print(
        "Longitud del contenido desescapado:",
        len(contenido)
    )


    # --------------------------------------------------------
    # BUSCAR initialPlayers
    # --------------------------------------------------------

    pos = contenido.find(
        '"initialPlayers":'
    )

    if pos == -1:

        raise Exception(
            "No se encontró initialPlayers "
            "en contenido desescapado"
        )

    print(
        "initialPlayers encontrado "
        "en contenido desescapado"
    )

    print(
        f"Posición: {pos}"
    )


    # --------------------------------------------------------
    # EXTRAER ARRAY
    # --------------------------------------------------------

    inicio_array = contenido.find(
        "[",
        pos
    )

    contenido_array = extraer_array_balanceado(
        contenido,
        inicio_array
    )

    print(
        "Longitud del array extraído:",
        len(contenido_array)
    )


    # --------------------------------------------------------
    # JSON
    # --------------------------------------------------------

    jugadores = json.loads(
        contenido_array
    )

    return jugadores


# ============================================================
# DESCARGAR
# ============================================================

print("\n" + "=" * 80)
print("DESCARGANDO MERCADO")
print("=" * 80)


response = requests.get(
    URL,
    headers=HEADERS,
    timeout=30
)

print(
    "Status:",
    response.status_code
)

print(
    "Bytes:",
    len(response.content)
)

response.raise_for_status()


# ============================================================
# EXTRAER
# ============================================================

jugadores = extraer_jugadores(
    response.text
)


print("\n" + "=" * 80)
print("RESULTADO DE LA EXTRACCIÓN")
print("=" * 80)

print(
    "Jugadores descargados:",
    len(jugadores)
)


if len(jugadores) < 400:

    raise Exception(
        "Se han descargado menos de 400 jugadores. "
        "Se detiene el proceso."
    )


# ============================================================
# DATAFRAME
# ============================================================

df = pd.json_normalize(
    jugadores
)


# ============================================================
# FECHA
# ============================================================

ahora = datetime.now()

fecha_hoy = ahora.strftime(
    "%Y-%m-%d"
)

timestamp = ahora.isoformat()

df["fecha"] = fecha_hoy

df["timestamp"] = timestamp


# ============================================================
# PLAYER KEY
# ============================================================

def crear_player_key(row):

    master_id = row.get(
        "masterPlayerId"
    )

    slug = row.get(
        "slug"
    )

    team_id = row.get(
        "teamId"
    )


    if pd.notna(master_id):

        return (
            f"mp_{int(master_id)}"
        )


    if pd.notna(slug):

        if pd.notna(team_id):

            return (
                f"slug_{slug}_{int(team_id)}"
            )

        return (
            f"slug_{slug}"
        )


    return (
        "unknown_"
        + str(row.get("nickname"))
    )


df["player_key"] = df.apply(
    crear_player_key,
    axis=1
)


# ============================================================
# VALIDACIONES
# ============================================================

print("\n" + "=" * 80)
print("VALIDACIONES")
print("=" * 80)

print(
    "Registros:",
    len(df)
)

print(
    "masterPlayerId:",
    df["masterPlayerId"].notna().sum()
)

print(
    "Sin masterPlayerId:",
    df["masterPlayerId"].isna().sum()
)


duplicados = (
    df["player_key"]
    .duplicated()
    .sum()
)

print(
    "\nplayer_key únicos:",
    df["player_key"].nunique()
)

print(
    "player_key duplicados:",
    duplicados
)


if duplicados != 0:

    raise Exception(
        "Hay player_key duplicados"
    )


print(
    "✓ player_key único"
)


# ============================================================
# PEDRI
# ============================================================

pedri = df[
    df["nickname"]
    .astype(str)
    .str.lower()
    == "pedri"
]


if len(pedri):

    print("\nPedri:")

    print(
        pedri[
            [
                "nickname",
                "masterPlayerId",
                "marketValue",
                "subida",
                "frenada",
                "titularityPercent"
            ]
        ].to_string(
            index=False
        )
    )


# ============================================================
# CSV
# ============================================================

csv_file = (
    CARPETA_CSV
    / f"mercado_laliga_{fecha_hoy}.csv"
)

df.to_csv(
    csv_file,
    index=False,
    encoding="utf-8-sig"
)

print(
    "\nCSV guardado:"
)

print(
    csv_file
)


# ============================================================
# BASE DE DATOS NUEVA
# ============================================================

print("\n" + "=" * 80)
print("BASE DE DATOS")
print("=" * 80)

print(
    f"Base de datos: {DB_FILE}"
)


conn = sqlite3.connect(
    DB_FILE
)

cursor = conn.cursor()


# ============================================================
# TABLA PLAYERS
# ============================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS players (

    player_key TEXT PRIMARY KEY,

    master_player_id INTEGER,

    nickname TEXT NOT NULL,

    slug TEXT,

    position_id INTEGER,

    team_id INTEGER,

    team_name TEXT,

    player_slug TEXT,

    player_status TEXT,

    is_sanctioned INTEGER,

    is_new INTEGER,

    titularity_percent REAL

)
""")


# ============================================================
# TABLA MARKET HISTORY
# ============================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS market_history (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    fecha TEXT NOT NULL,

    timestamp TEXT NOT NULL,

    player_key TEXT NOT NULL,

    master_player_id INTEGER,

    nickname TEXT NOT NULL,

    team_name TEXT,

    market_value INTEGER,

    subida INTEGER,

    frenada INTEGER,

    titularity_percent REAL,

    FOREIGN KEY (
        player_key
    )
    REFERENCES players (
        player_key
    ),

    UNIQUE (
        fecha,
        player_key
    )

)
""")


# ============================================================
# ÍNDICES
# ============================================================

cursor.execute("""
CREATE INDEX IF NOT EXISTS
idx_market_history_fecha

ON market_history (
    fecha
)
""")


cursor.execute("""
CREATE INDEX IF NOT EXISTS
idx_market_history_player

ON market_history (
    player_key
)
""")


# ============================================================
# ACTUALIZAR PLAYERS
# ============================================================

print("\n" + "=" * 80)
print("ACTUALIZANDO PLAYERS")
print("=" * 80)


for _, row in df.iterrows():

    master_id = row.get(
        "masterPlayerId"
    )

    if pd.isna(master_id):
        master_id = None
    else:
        master_id = int(master_id)


    position_id = row.get(
        "positionId"
    )

    if pd.isna(position_id):
        position_id = None
    else:
        position_id = int(position_id)


    team_id = row.get(
        "teamId"
    )

    if pd.isna(team_id):
        team_id = None
    else:
        team_id = int(team_id)


    sanctioned = row.get(
        "isSanctioned"
    )

    if pd.isna(sanctioned):
        sanctioned = 0

    sanctioned = int(
        bool(sanctioned)
    )


    is_new = row.get(
        "isNew"
    )

    if pd.isna(is_new):
        is_new = 0

    is_new = int(
        bool(is_new)
    )


    titularity = row.get(
        "titularityPercent"
    )

    if pd.isna(titularity):
        titularity = None


    cursor.execute("""
    INSERT INTO players (

        player_key,
        master_player_id,
        nickname,
        slug,
        position_id,
        team_id,
        team_name,
        player_slug,
        player_status,
        is_sanctioned,
        is_new,
        titularity_percent

    )

    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

    ON CONFLICT(player_key)

    DO UPDATE SET

        master_player_id =
            excluded.master_player_id,

        nickname =
            excluded.nickname,

        slug =
            excluded.slug,

        position_id =
            excluded.position_id,

        team_id =
            excluded.team_id,

        team_name =
            excluded.team_name,

        player_slug =
            excluded.player_slug,

        player_status =
            excluded.player_status,

        is_sanctioned =
            excluded.is_sanctioned,

        is_new =
            excluded.is_new,

        titularity_percent =
            excluded.titularity_percent

    """, (

        row["player_key"],
        master_id,
        row.get("nickname"),
        row.get("slug"),
        position_id,
        team_id,
        row.get("teamName"),
        row.get("playerSlug"),
        row.get("playerStatus"),
        sanctioned,
        is_new,
        titularity

    ))


print(
    "✓ Players actualizados"
)


# ============================================================
# SNAPSHOT DIARIO
# ============================================================

print("\n" + "=" * 80)
print("SNAPSHOT DIARIO")
print("=" * 80)


cursor.execute("""
SELECT COUNT(*)

FROM market_history

WHERE fecha = ?
""", (
    fecha_hoy,
))


registros_hoy = cursor.fetchone()[0]


print(
    "Registros de hoy:",
    registros_hoy
)


if registros_hoy == 0:

    print(
        "Insertando snapshot..."
    )


    for _, row in df.iterrows():

        master_id = row.get(
            "masterPlayerId"
        )

        if pd.isna(master_id):
            master_id = None
        else:
            master_id = int(master_id)


        market_value = row.get(
            "marketValue"
        )

        if pd.isna(market_value):
            market_value = None
        else:
            market_value = int(
                market_value
            )


        subida = row.get(
            "subida"
        )

        if pd.isna(subida):
            subida = None
        else:
            subida = int(
                subida
            )


        frenada = row.get(
            "frenada"
        )

        if pd.isna(frenada):
            frenada = None
        else:
            frenada = int(
                frenada
            )


        titularity = row.get(
            "titularityPercent"
        )

        if pd.isna(titularity):

            titularity = None


        cursor.execute("""
        INSERT INTO market_history (

            fecha,
            timestamp,
            player_key,
            master_player_id,
            nickname,
            team_name,
            market_value,
            subida,
            frenada,
            titularity_percent

        )

        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

        ON CONFLICT(
            fecha,
            player_key
        )

        DO NOTHING

        """, (

            fecha_hoy,
            timestamp,
            row["player_key"],
            master_id,
            row.get("nickname"),
            row.get("teamName"),
            market_value,
            subida,
            frenada,
            titularity

        ))


    print(
        "✓ Snapshot insertado"
    )

else:

    print(
        "⚠ Ya existe el snapshot de hoy."
    )

    print(
        "No se insertará otro."
    )


# ============================================================
# COMMIT
# ============================================================

conn.commit()


# ============================================================
# RESULTADOS
# ============================================================

print("\n" + "=" * 80)
print("RESULTADO FINAL")
print("=" * 80)


cursor.execute("""
SELECT COUNT(*)
FROM players
""")

num_players = cursor.fetchone()[0]


cursor.execute("""
SELECT COUNT(*)
FROM market_history
""")

num_history = cursor.fetchone()[0]


cursor.execute("""
SELECT COUNT(DISTINCT fecha)
FROM market_history
""")

num_days = cursor.fetchone()[0]


print(
    "Players:",
    num_players
)

print(
    "Registros históricos:",
    num_history
)

print(
    "Días almacenados:",
    num_days
)


# ============================================================
# PEDRI HISTÓRICO
# ============================================================

print("\n" + "=" * 80)
print("HISTÓRICO DE PEDRI")
print("=" * 80)


cursor.execute("""
SELECT

    fecha,
    timestamp,
    master_player_id,
    market_value,
    subida,
    frenada

FROM market_history

WHERE player_key = 'mp_133609'

ORDER BY fecha
""")


for fila in cursor.fetchall():

    print(fila)


# ============================================================
# COMPROBACIÓN DE DUPLICADOS
# ============================================================

print("\n" + "=" * 80)
print("COMPROBACIÓN DE DUPLICADOS")
print("=" * 80)


cursor.execute("""
SELECT

    fecha,
    player_key,
    COUNT(*)

FROM market_history

GROUP BY
    fecha,
    player_key

HAVING COUNT(*) > 1
""")


duplicados = cursor.fetchall()


if duplicados:

    print(
        "⚠ DUPLICADOS ENCONTRADOS:"
    )

    for fila in duplicados:
        print(fila)

else:

    print(
        "✓ No existen duplicados jugador/día"
    )


# ============================================================
# RESUMEN POR DÍA
# ============================================================

print("\n" + "=" * 80)
print("RESUMEN DEL HISTÓRICO")
print("=" * 80)


cursor.execute("""
SELECT

    fecha,
    COUNT(*)

FROM market_history

GROUP BY fecha

ORDER BY fecha
""")


for fila in cursor.fetchall():

    print(
        f"{fila[0]} -> {fila[1]} jugadores"
    )


# ============================================================
# CERRAR
# ============================================================

conn.close()


print("\n" + "=" * 80)
print("✓ PROCESO TERMINADO")
print("=" * 80)