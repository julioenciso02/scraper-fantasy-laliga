import sqlite3
import sys
import os
from datetime import datetime
from mercado import analizar_mercado

# ============================================================
# CONFIGURACIÓN
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "fantasy_laliga_v2.db")

MODEL_VERSION = "v0.2"


# ============================================================
# CONEXIÓN
# ============================================================

def conectar():
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(
            f"No se encuentra la base de datos:\n{DB_PATH}"
        )

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ============================================================
# UTILIDADES
# ============================================================

def numero(valor, default=0):
    if valor is None:
        return default

    try:
        return float(valor)
    except (TypeError, ValueError):
        return default


def entero(valor, default=0):
    if valor is None:
        return default

    try:
        return int(valor)
    except (TypeError, ValueError):
        return default


def euros(valor):
    if valor is None:
        return "N/D"

    valor = int(round(valor))

    signo = "-" if valor < 0 else ""

    valor = abs(valor)

    return signo + f"{valor:,}".replace(",", ".") + " €"


def signo_euros(valor):
    if valor is None:
        return "N/D"

    valor = int(round(valor))

    if valor > 0:
        return "+" + euros(valor)

    return euros(valor)


def porcentaje(valor):
    if valor is None:
        return "N/D"

    return f"{float(valor):.1f} %"


def limitar(valor, minimo, maximo):
    return max(minimo, min(maximo, valor))


# ============================================================
# TABLA DE PREDICCIONES
# ============================================================

def crear_tabla_predicciones(conn):

    conn.execute("""
        CREATE TABLE IF NOT EXISTS prediction_history (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            fecha_prediccion TEXT NOT NULL,
            timestamp_prediccion TEXT NOT NULL,

            player_key TEXT NOT NULL,
            master_player_id INTEGER,

            nickname TEXT,
            team_name TEXT,

            market_value INTEGER,

            prediction_24h INTEGER,
            prediction_3d INTEGER,
            prediction_7d INTEGER,

            probability_up_24h REAL,
            probability_up_3d REAL,
            probability_up_7d REAL,

            opportunity_score REAL,

            bid_conservative INTEGER,
            bid_balanced INTEGER,
            bid_aggressive INTEGER,

            confidence REAL,

            model_version TEXT NOT NULL,

            actual_change_24h INTEGER,
            actual_change_3d INTEGER,
            actual_change_7d INTEGER,

            error_24h INTEGER,
            error_3d INTEGER,
            error_7d INTEGER
        )
    """)

    conn.commit()


# ============================================================
# JUGADORES
# ============================================================

def obtener_jugadores(conn):

    return conn.execute("""
        SELECT *
        FROM players
        ORDER BY nickname
    """).fetchall()


# ============================================================
# BUSCAR JUGADOR
# ============================================================

def buscar_jugador(conn, busqueda):

    jugadores = obtener_jugadores(conn)

    termino = busqueda.strip().lower()

    # --------------------------------------------------------
    # masterPlayerId
    # --------------------------------------------------------

    for jugador in jugadores:

        if jugador["master_player_id"] is not None:

            if str(jugador["master_player_id"]) == termino:
                return jugador

    # --------------------------------------------------------
    # player_key
    # --------------------------------------------------------

    for jugador in jugadores:

        if jugador["player_key"]:

            if str(jugador["player_key"]).lower() == termino:
                return jugador

    # --------------------------------------------------------
    # nickname exacto
    # --------------------------------------------------------

    for jugador in jugadores:

        if jugador["nickname"]:

            if jugador["nickname"].lower() == termino:
                return jugador

    # --------------------------------------------------------
    # slug
    # --------------------------------------------------------

    for jugador in jugadores:

        if jugador["slug"]:

            if jugador["slug"].lower() == termino:
                return jugador

    # --------------------------------------------------------
    # nickname parcial
    # --------------------------------------------------------

    coincidencias = []

    for jugador in jugadores:

        nickname = jugador["nickname"]

        if nickname and termino in nickname.lower():

            coincidencias.append(jugador)

    if len(coincidencias) == 1:
        return coincidencias[0]

    if len(coincidencias) > 1:

        print()
        print("Se encontraron varios jugadores:")
        print()

        for i, jugador in enumerate(coincidencias, 1):

            print(
                f"{i}. "
                f"{jugador['nickname']} "
                f"({jugador['team_name']}) "
                f"[{jugador['master_player_id']}]"
            )

        print()

        try:

            opcion = int(
                input("Selecciona jugador: ")
            )

            if 1 <= opcion <= len(coincidencias):

                return coincidencias[opcion - 1]

        except ValueError:
            pass

    return None


# ============================================================
# HISTÓRICO
# ============================================================

def historico_jugador(conn, player_key):

    return conn.execute("""
        SELECT *
        FROM market_history
        WHERE player_key = ?
        ORDER BY fecha ASC, timestamp ASC
    """, (player_key,)).fetchall()


# ============================================================
# CAMBIO ENTRE SNAPSHOTS
# ============================================================

def cambio_entre(filas, dias):

    if len(filas) < 2:
        return None

    actual = filas[-1]

    valor_actual = numero(
        actual["market_value"],
        None
    )

    if valor_actual is None:
        return None

    # --------------------------------------------------------
    # Fecha actual
    # --------------------------------------------------------

    try:

        fecha_actual = datetime.strptime(
            str(actual["fecha"]),
            "%Y-%m-%d"
        ).date()

    except Exception:

        return None

    objetivo = fecha_actual.toordinal() - dias

    candidato = None

    for fila in filas[:-1]:

        try:

            fecha = datetime.strptime(
                str(fila["fecha"]),
                "%Y-%m-%d"
            ).date()

        except Exception:

            continue

        if fecha.toordinal() <= objetivo:

            candidato = fila

    # Si todavía no tenemos tantos días,
    # usamos el primer snapshot.

    if candidato is None:

        candidato = filas[0]

    valor_anterior = numero(
        candidato["market_value"],
        None
    )

    if valor_anterior is None:
        return None

    return valor_actual - valor_anterior


# ============================================================
# CAMBIO ENTRE ÚLTIMOS SNAPSHOTS
# ============================================================

def cambio_ultimo(filas):

    if len(filas) < 2:
        return None

    actual = numero(
        filas[-1]["market_value"],
        None
    )

    anterior = numero(
        filas[-2]["market_value"],
        None
    )

    if actual is None or anterior is None:
        return None

    return actual - anterior


# ============================================================
# DATOS DE MERCADO
# ============================================================

def datos_mercado(filas):

    return {

        "cambio_ultimo":
            cambio_ultimo(filas),

        "cambio_1d":
            cambio_entre(filas, 1),

        "cambio_3d":
            cambio_entre(filas, 3),

        "cambio_7d":
            cambio_entre(filas, 7),

        "filas":
            filas
    }


# ============================================================
# MODELO
# ============================================================

def calcular_modelo(player, mercado):

    titularidad = numero(
        player["titularity_percent"]
    )

    subida = numero(
        mercado["filas"][-1]["subida"]
    )

    frenada = numero(
        mercado["filas"][-1]["frenada"]
    )

    cambio_1d = mercado["cambio_1d"]
    cambio_3d = mercado["cambio_3d"]
    cambio_7d = mercado["cambio_7d"]

    # --------------------------------------------------------
    # Opportunity Score
    # --------------------------------------------------------

    score = 50.0

    # Titularidad
    score += (
        titularidad - 50
    ) * 0.25

    # --------------------------------------------------------
    # Tendencia de mercado
    # --------------------------------------------------------

    if cambio_1d is not None:

        score += limitar(
            cambio_1d / 100000,
            -12,
            12
        )

    if cambio_3d is not None:

        score += limitar(
            cambio_3d / 250000,
            -10,
            10
        )

    if cambio_7d is not None:

        score += limitar(
            cambio_7d / 500000,
            -10,
            10
        )

    # --------------------------------------------------------
    # Subida y frenada actuales
    # --------------------------------------------------------

    score += limitar(
        subida / 100000,
        -8,
        10
    )

    score -= limitar(
        frenada / 150000,
        0,
        8
    )

    # --------------------------------------------------------
    # Estado
    # --------------------------------------------------------

    status = (
        player["player_status"]
        or ""
    ).lower()

    if status == "injured":
        score -= 20

    elif status == "doubtful":
        score -= 10

    elif status == "suspended":
        score -= 15

    # --------------------------------------------------------
    # Sancionado
    # --------------------------------------------------------

    if entero(
        player["is_sanctioned"]
    ) == 1:

        score -= 20

    # --------------------------------------------------------
    # Titularidad desconocida
    # --------------------------------------------------------

    if titularidad <= 0:

        score -= 5

    score = limitar(
        score,
        0,
        100
    )

    # ========================================================
    # PREDICCIÓN
    # ========================================================

    momentum = 0

    if cambio_1d is not None:

        momentum += cambio_1d * 0.45

    if cambio_3d is not None:

        momentum += cambio_3d * 0.30

    if cambio_7d is not None:

        momentum += cambio_7d * 0.15

    momentum += subida * 0.10

    # Factor de calidad

    factor = (
        0.65 +
        (score / 100) * 0.70
    )

    pred_24h = momentum * factor

    # Con un único snapshot no existe tendencia.
    # Utilizamos la subida publicada por la web como
    # señal inicial extremadamente débil.

    if (
        cambio_1d is None
        and cambio_3d is None
        and cambio_7d is None
    ):

        pred_24h = subida * 0.35

    pred_24h = limitar(
        pred_24h,
        -2000000,
        3000000
    )

    pred_3d = pred_24h * 2.2
    pred_7d = pred_24h * 4.5

    # ========================================================
    # PROBABILIDADES
    # ========================================================

    prob_base = (
        50 +
        (score - 50) * 0.65
    )

    if pred_24h > 0:
        prob_24 = prob_base + 8
    else:
        prob_24 = prob_base - 8

    if pred_3d > 0:
        prob_3 = prob_base + 10
    else:
        prob_3 = prob_base - 10

    if pred_7d > 0:
        prob_7 = prob_base + 12
    else:
        prob_7 = prob_base - 12

    prob_24 = limitar(
        prob_24,
        5,
        95
    )

    prob_3 = limitar(
        prob_3,
        5,
        95
    )

    prob_7 = limitar(
        prob_7,
        5,
        95
    )

    # ========================================================
    # CONFIANZA
    # ========================================================

    snapshots = len(
        mercado["filas"]
    )

    if snapshots <= 1:

        confianza = 10

    elif snapshots < 3:

        confianza = 20

    elif snapshots < 7:

        confianza = 35

    elif snapshots < 14:

        confianza = 50

    elif snapshots < 30:

        confianza = 65

    else:

        confianza = 80

    return {

        "score":
            score,

        "prediction_24h":
            int(pred_24h),

        "prediction_3d":
            int(pred_3d),

        "prediction_7d":
            int(pred_7d),

        "probability_up_24h":
            prob_24,

        "probability_up_3d":
            prob_3,

        "probability_up_7d":
            prob_7,

        "confidence":
            confianza
    }


# ============================================================
# PUJAS
# ============================================================

def calcular_pujas(precio, modelo):

    score = modelo["score"]

    confianza = modelo["confidence"]

    probabilidad = (
        modelo["probability_up_24h"]
    )

    # --------------------------------------------------------
    # Interés
    # --------------------------------------------------------

    interes = (

        (score - 50) * 0.0015

        +

        (probabilidad - 50)
        * 0.0005
    )

    interes = limitar(
        interes,
        -0.04,
        0.08
    )

    # --------------------------------------------------------
    # Tres perfiles
    # --------------------------------------------------------

    conservadora = precio * (
        1.002 +
        interes * 0.30
    )

    equilibrada = precio * (
        1.010 +
        interes * 0.70
    )

    agresiva = precio * (
        1.025 +
        interes
    )

    # Poca información =
    # pujas prudentes.

    if confianza < 30:

        conservadora = precio * 1.002

        equilibrada = precio * 1.008

        agresiva = precio * 1.018

    return {

        "conservative":
            int(conservadora),

        "balanced":
            int(equilibrada),

        "aggressive":
            int(agresiva)
    }


# ============================================================
# ANÁLISIS
# ============================================================

def analizar_jugador(conn, player):

    filas = historico_jugador(
        conn,
        player["player_key"]
    )

    if not filas:

        raise ValueError(
            "No existe histórico de mercado "
            "para este jugador."
        )

    mercado = datos_mercado(
        filas
    )

    modelo = calcular_modelo(
        player,
        mercado
    )

    precio = numero(
        filas[-1]["market_value"]
    )

    pujas = calcular_pujas(
        precio,
        modelo
    )

    return {

        "player":
            player,

        "filas":
            filas,

        "mercado":
            mercado,

        "modelo":
            modelo,

        "pujas":
            pujas
    }


# ============================================================
# GUARDAR PREDICCIÓN
# ============================================================

def guardar_prediccion(conn, analisis):

    player = analisis["player"]

    modelo = analisis["modelo"]

    pujas = analisis["pujas"]

    ahora = datetime.now()

    fecha = ahora.date().isoformat()

    timestamp = ahora.isoformat()

    existente = conn.execute("""
        SELECT id
        FROM prediction_history

        WHERE fecha_prediccion = ?
        AND player_key = ?
        AND model_version = ?

        LIMIT 1
    """, (
        fecha,
        player["player_key"],
        MODEL_VERSION
    )).fetchone()

    if existente:

        return

    precio = numero(
        analisis["filas"][-1]["market_value"]
    )

    conn.execute("""
        INSERT INTO prediction_history (

            fecha_prediccion,
            timestamp_prediccion,

            player_key,
            master_player_id,

            nickname,
            team_name,

            market_value,

            prediction_24h,
            prediction_3d,
            prediction_7d,

            probability_up_24h,
            probability_up_3d,
            probability_up_7d,

            opportunity_score,

            bid_conservative,
            bid_balanced,
            bid_aggressive,

            confidence,

            model_version
        )

        VALUES (

            ?, ?, ?, ?, ?, ?, ?,

            ?, ?, ?,

            ?, ?, ?,

            ?,

            ?, ?, ?,

            ?,

            ?
        )
    """, (

        fecha,
        timestamp,

        player["player_key"],
        player["master_player_id"],

        player["nickname"],
        player["team_name"],

        int(precio),

        modelo["prediction_24h"],
        modelo["prediction_3d"],
        modelo["prediction_7d"],

        modelo["probability_up_24h"],
        modelo["probability_up_3d"],
        modelo["probability_up_7d"],

        modelo["score"],

        pujas["conservative"],
        pujas["balanced"],
        pujas["aggressive"],

        modelo["confidence"],

        MODEL_VERSION
    ))

    conn.commit()


# ============================================================
# MOSTRAR ANÁLISIS
# ============================================================

def mostrar_analisis(analisis):

    player = analisis["player"]

    filas = analisis["filas"]

    mercado = analisis["mercado"]

    modelo = analisis["modelo"]

    pujas = analisis["pujas"]

    print()

    print("=" * 64)

    print("ANÁLISIS DE JUGADOR")

    print("=" * 64)

    print()

    print(
        f"Jugador:              "
        f"{player['nickname']}"
    )

    print(
        f"Equipo:               "
        f"{player['team_name']}"
    )

    print(
        f"masterPlayerId:       "
        f"{player['master_player_id']}"
    )

    print(
        f"player_key:           "
        f"{player['player_key']}"
    )

    print()

    print("-" * 64)

    print("DATOS ACTUALES")

    print("-" * 64)

    ultimo = filas[-1]

    print(
        f"Precio actual:         "
        f"{euros(ultimo['market_value'])}"
    )

    print(
        f"Titularidad:           "
        f"{porcentaje(ultimo['titularity_percent'])}"
    )

    print(
        f"Subida:                "
        f"{signo_euros(ultimo['subida'])}"
    )

    print(
        f"Frenada:               "
        f"{signo_euros(ultimo['frenada'])}"
    )

    print(
        f"Estado:                "
        f"{player['player_status'] or 'N/D'}"
    )

    print(
        f"Sancionado:            "
        f"{'Sí' if entero(player['is_sanctioned']) else 'No'}"
    )

    print()

    print("-" * 64)

    print("HISTÓRICO DE MERCADO")

    print("-" * 64)

    print(
        f"Snapshots disponibles: "
        f"{len(filas)}"
    )

    print(
        f"Cambio último:         "
        f"{signo_euros(mercado['cambio_ultimo'])}"
    )

    print(
        f"Cambio ~1 día:         "
        f"{signo_euros(mercado['cambio_1d'])}"
    )

    print(
        f"Cambio ~3 días:        "
        f"{signo_euros(mercado['cambio_3d'])}"
    )

    print(
        f"Cambio ~7 días:        "
        f"{signo_euros(mercado['cambio_7d'])}"
    )

    print()

    print("-" * 64)

    print("PREDICCIÓN INICIAL")

    print("-" * 64)

    print(
        f"Opportunity Score:    "
        f"{modelo['score']:.1f} / 100"
    )

    print()

    print(
        f"Predicción 24h:       "
        f"{signo_euros(modelo['prediction_24h'])}"
    )

    print(
        f"Predicción 3 días:    "
        f"{signo_euros(modelo['prediction_3d'])}"
    )

    print(
        f"Predicción 7 días:    "
        f"{signo_euros(modelo['prediction_7d'])}"
    )

    print()

    print(
        f"Prob. subida 24h:     "
        f"{porcentaje(modelo['probability_up_24h'])}"
    )

    print(
        f"Prob. subida 3 días:  "
        f"{porcentaje(modelo['probability_up_3d'])}"
    )

    print(
        f"Prob. subida 7 días:  "
        f"{porcentaje(modelo['probability_up_7d'])}"
    )

    print()

    print(
        f"Confianza:             "
        f"{porcentaje(modelo['confidence'])}"
    )

    if len(filas) < 3:

        print()

        print(
            "⚠ MUY POCO HISTÓRICO: "
            "la predicción todavía es experimental."
        )

    print()

    print("-" * 64)

    print("PUJAS")

    print("-" * 64)

    print(
        f"🟢 Conservadora:      "
        f"{euros(pujas['conservative'])}"
    )

    print(
        f"🟡 Equilibrada:       "
        f"{euros(pujas['balanced'])}"
    )

    print(
        f"🔴 Agresiva:          "
        f"{euros(pujas['aggressive'])}"
    )

    print()

    print(
        f"Modelo: {MODEL_VERSION}"
    )

    print(
        "⚠ Modelo inicial. "
        "Se irá calibrando con histórico real."
    )

    print()

    print("=" * 64)


# ============================================================
# RANKING
# ============================================================

def ranking_oportunidades(conn):

    jugadores = obtener_jugadores(
        conn
    )

    resultados = []

    for jugador in jugadores:

        try:

            analisis = analizar_jugador(
                conn,
                jugador
            )

            resultados.append(
                analisis
            )

        except Exception:

            continue

    resultados.sort(
        key=lambda x:
        x["modelo"]["score"],
        reverse=True
    )

    print()

    print("=" * 100)

    print("RANKING DE OPORTUNIDADES")

    print("=" * 100)

    print()

    print(
        f"{'#':<4}"
        f"{'Jugador':<24}"
        f"{'Equipo':<20}"
        f"{'Precio':>14}"
        f"{'Score':>9}"
        f"{'Pred.24h':>14}"
    )

    print("-" * 100)

    for i, resultado in enumerate(
        resultados[:30],
        1
    ):

        player = resultado["player"]

        modelo = resultado["modelo"]

        nickname = (
            player["nickname"]
            or ""
        )[:22]

        equipo = (
            player["team_name"]
            or ""
        )[:18]

        precio = resultado["filas"][-1]["market_value"]

        print(
            f"{i:<4}"
            f"{nickname:<24}"
            f"{equipo:<20}"
            f"{euros(precio):>14}"
            f"{modelo['score']:>9.1f}"
            f"{signo_euros(modelo['prediction_24h']):>14}"
        )

    print()

    print(
        "⚠ Modelo experimental."
    )


# ============================================================
# AYUDA
# ============================================================

def ayuda():

    print()

    print("=" * 64)

    print("MOTOR DE ANÁLISIS FANTASY")

    print("=" * 64)

    print()

    print(
        "Analizar jugador:"
    )

    print(
        "python analisis_fantasy.py jugador Pedri"
    )

    print()

    print(
        "Analizar por ID:"
    )

    print(
        "python analisis_fantasy.py jugador 133609"
    )

    print()

    print(
        "Calcular puja:"
    )

    print(
        "python analisis_fantasy.py puja Pedri"
    )

    print()

    print(
        "Ranking:"
    )

    print(
        "python analisis_fantasy.py oportunidad"
    )

    print()


# ============================================================
# MAIN
# ============================================================

def main():

    print()

    print("=" * 64)

    print(
        "FANTASY LALIGA - MOTOR DE ANÁLISIS"
    )

    print("=" * 64)

    print()

    print(
        f"Base de datos: {DB_PATH}"
    )

    try:

        conn = conectar()

    except Exception as e:

        print()

        print(
            "ERROR:"
        )

        print(e)

        return 1

    try:

        crear_tabla_predicciones(
            conn
        )

        if len(sys.argv) < 2:

            ayuda()

            return 0

        comando = (
            sys.argv[1]
            .strip()
            .lower()
        )

        # ====================================================
        # JUGADOR
        # ====================================================

        if comando == "jugador":

            if len(sys.argv) < 3:

                print(
                    "Falta el jugador."
                )

                return 1

            busqueda = " ".join(
                sys.argv[2:]
            )

            jugador = buscar_jugador(
                conn,
                busqueda
            )

            if jugador is None:

                print()

                print(
                    f"No encontrado: "
                    f"{busqueda}"
                )

                return 1

            analisis = analizar_jugador(
                conn,
                jugador
            )

            mostrar_analisis(
                analisis
            )

            guardar_prediccion(
                conn,
                analisis
            )

        # ====================================================
        # PUJA
        # ====================================================

        elif comando == "puja":

            if len(sys.argv) < 3:

                print(
                    "Falta el jugador."
                )

                return 1

            busqueda = " ".join(
                sys.argv[2:]
            )

            jugador = buscar_jugador(
                conn,
                busqueda
            )

            if jugador is None:

                print()

                print(
                    f"No encontrado: "
                    f"{busqueda}"
                )

                return 1

            analisis = analizar_jugador(
                conn,
                jugador
            )

            modelo = analisis["modelo"]

            pujas = analisis["pujas"]

            print()

            print("=" * 64)

            print(
                "RECOMENDACIÓN DE PUJA"
            )

            print("=" * 64)

            print()

            print(
                f"Jugador:          "
                f"{jugador['nickname']}"
            )

            print(
                f"Precio actual:    "
                f"{euros(analisis['filas'][-1]['market_value'])}"
            )

            print()

            print(
                f"🟢 Conservadora:   "
                f"{euros(pujas['conservative'])}"
            )

            print(
                f"🟡 Equilibrada:    "
                f"{euros(pujas['balanced'])}"
            )

            print(
                f"🔴 Agresiva:       "
                f"{euros(pujas['aggressive'])}"
            )

            print()

            print(
                f"Opportunity Score: "
                f"{modelo['score']:.1f}/100"
            )

            print(
                f"Confianza:         "
                f"{modelo['confidence']:.1f}%"
            )

            print()

            print(
                "⚠ Modelo experimental."
            )

            print("=" * 64)

            guardar_prediccion(
                conn,
                analisis
            )

        # ====================================================
        # OPORTUNIDAD
        # ====================================================

        elif comando in (
            "oportunidad",
            "oportunidades",
            "ranking"
        ):

            ranking_oportunidades(
                conn
            )

        # ====================================================
        # AYUDA
        # ====================================================

        elif comando in (
            "ayuda",
            "help",
            "-h",
            "--help"
        ):

            ayuda()
        elif comando == "mercado":
            if len(sys.argv) < 3:
                print("Uso: python analisis_fantasy.py mercado <jugador>")
            else:
                nombre = " ".join(sys.argv[2:])
                analizar_mercado(nombre)
        else:

            print()

            print(
                f"Comando desconocido: "
                f"{comando}"
            )

            ayuda()

            return 1

        return 0

    finally:

        conn.close()


# ============================================================
# EJECUCIÓN
# ============================================================

if __name__ == "__main__":

    sys.exit(
        main()
    )