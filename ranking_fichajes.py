import sqlite3
import csv
import math
from collections import defaultdict


# ================================================================
# CONFIGURACIÓN
# ================================================================

DB_PATH = r"C:\Users\Usuario\Desktop\fantasy_laliga\fantasy_historico.db"

OUTPUT_CSV = r"C:\Users\Usuario\Desktop\fantasy_laliga\ranking_fichajes.csv"

TEMPORADA = 2025

# Si es None -> última jornada disponible + 1
JORNADA_OBJETIVO = None

# Mínimo de jornadas históricas para analizar
MIN_HISTORICO = 3

# Ventana reciente del predictor
VENTANA_RECIENTE = 5


# ================================================================
# FILTROS DE PARTICIPACIÓN
# ================================================================

# Participación mínima.
#
# Si existen minutos en la BD:
#   minutos / minutos posibles.
#
# Si NO existen minutos:
#   porcentaje de jornadas con puntos distintos de 0.
#
MIN_PARTICIPACION = 0.35

# Por debajo de este nivel el jugador queda fuera.
FILTRAR_BAJA_PARTICIPACION = True


# ================================================================
# PESOS DEL RANKING
# ================================================================

# Predicción de puntos
PESO_PREDICCION = 0.50

# Valor por precio
PESO_VALOR = 0.30

# Participación
PESO_PARTICIPACION = 0.10

# Seguridad / bajo riesgo
PESO_SEGURIDAD = 0.10


# ================================================================
# PENALIZACIÓN POR PARTICIPACIÓN
# ================================================================

FUERZA_PENALIZACION_PARTICIPACION = 0.35


# ================================================================
# PENALIZACIÓN POR RIESGO
# ================================================================

FUERZA_PENALIZACION_RIESGO = 0.25


# ================================================================
# PRECIO ANÓMALO
# ================================================================

PRECIO_ANOMALIA_FACTOR_BAJO = 0.25
PRECIO_ANOMALIA_FACTOR_ALTO = 4.0


# ================================================================
# UTILIDADES
# ================================================================

def mean(values):

    if not values:
        return 0.0

    return sum(values) / len(values)


def clamp(value, low, high):

    return max(
        low,
        min(high, value)
    )


def percentile(values, p):

    if not values:
        return 0.0

    values = sorted(values)

    if len(values) == 1:
        return values[0]

    index = (
        len(values) - 1
    ) * p

    low = int(
        math.floor(index)
    )

    high = int(
        math.ceil(index)
    )

    if low == high:
        return values[low]

    fraction = index - low

    return (
        values[low]
        +
        (
            values[high]
            - values[low]
        )
        * fraction
    )


def stddev(values):

    if len(values) < 2:
        return 0.0

    m = mean(values)

    variance = sum(
        (x - m) ** 2
        for x in values
    ) / len(values)

    return math.sqrt(
        variance
    )


def posicion_nombre(position_id):

    try:
        p = int(position_id)

    except Exception:
        return "Desconocida"

    return {
        1: "Portero",
        2: "Defensa",
        3: "Centrocampista",
        4: "Delantero",
    }.get(
        p,
        "Desconocida"
    )


def player_key(row):

    if row.get("master_player_id") is not None:

        return (
            "master",
            row["master_player_id"]
        )

    return (
        "player",
        row["player_id"]
    )


def normalizar_0_100(value):

    return round(
        clamp(value, 0.0, 1.0)
        * 100,
        2
    )


# ================================================================
# DETECTAR COLUMNAS DE MINUTOS
# ================================================================

def detectar_columna_minutos(conn):

    cur = conn.cursor()

    cur.execute(
        "PRAGMA table_info(fantasy_points_history)"
    )

    columnas = [
        row[1]
        for row in cur.fetchall()
    ]

    candidatos = [

        "minutes",
        "minute",
        "minutos",
        "minuto",

        "minutes_played",
        "played_minutes",

        "player_minutes",
        "week_minutes",

        "mins",
        "min",
    ]

    for candidato in candidatos:

        if candidato in columnas:
            return candidato

    return None


# ================================================================
# INICIO
# ================================================================

print("=" * 70)
print("FANTASY LALIGA - RANKING DE FICHAJES AVANZADO")
print("=" * 70)

print()
print("Base de datos:")
print(DB_PATH)

conn = sqlite3.connect(
    DB_PATH
)

conn.row_factory = sqlite3.Row

columna_minutos = detectar_columna_minutos(
    conn
)

print()

if columna_minutos:

    print(
        "Columna de minutos detectada:",
        columna_minutos
    )

else:

    print(
        "No se encontró columna de minutos."
    )

    print(
        "Se utilizará participación estimada mediante puntos."
    )


# ================================================================
# CARGA DE DATOS
# ================================================================

cur = conn.cursor()

columnas_sql = """
    temporada,
    jornada,
    player_id,
    master_player_id,
    player_name,
    team_name,
    position_id,
    week_points,
    market_value
"""

if columna_minutos:

    columnas_sql += (
        ", "
        + columna_minutos
        + " AS minutos"
    )

else:

    columnas_sql += (
        ", NULL AS minutos"
    )


query = f"""
    SELECT
        {columnas_sql}
    FROM fantasy_points_history
    WHERE temporada = ?
    ORDER BY jornada, player_id
"""


cur.execute(
    query,
    (TEMPORADA,)
)

data = [
    dict(row)
    for row in cur.fetchall()
]

print()
print(
    f"Registros históricos cargados: {len(data)}"
)


if not data:

    conn.close()

    raise RuntimeError(
        "No se encontraron datos para la temporada indicada."
    )


# ================================================================
# FILTRAR POSICIONES VÁLIDAS
# ================================================================

datos_validos = []

registros_excluidos_posicion = 0

for row in data:

    try:
        position_id = int(
            row["position_id"]
        )

    except Exception:

        position_id = None

    if position_id not in (
        1,
        2,
        3,
        4
    ):

        registros_excluidos_posicion += 1

        continue

    row["position_id"] = position_id

    datos_validos.append(row)


data = datos_validos


print(
    f"Registros excluidos por posición "
    f"(entrenadores/otros): "
    f"{registros_excluidos_posicion}"
)


if not data:

    conn.close()

    raise RuntimeError(
        "No quedan jugadores válidos después del filtro de posición."
    )


# ================================================================
# JORNADAS
# ================================================================

jornadas = sorted(
    set(
        r["jornada"]
        for r in data
    )
)

ultima_jornada = max(
    jornadas
)

if JORNADA_OBJETIVO is None:

    jornada_objetivo = (
        ultima_jornada + 1
    )

else:

    jornada_objetivo = (
        JORNADA_OBJETIVO
    )


print()
print(
    f"Última jornada disponible: "
    f"J{ultima_jornada}"
)

print(
    f"Jornada objetivo: "
    f"J{jornada_objetivo}"
)


# ================================================================
# ORGANIZAR HISTÓRICO
# ================================================================

history = defaultdict(list)

for row in data:

    key = player_key(row)

    try:
        puntos = float(
            row["week_points"] or 0
        )

    except Exception:
        puntos = 0.0


    minutos = row.get(
        "minutos"
    )

    if minutos is not None:

        try:
            minutos = float(
                minutos
            )

        except Exception:
            minutos = None


    try:
        market_value = float(
            row["market_value"]
            if row["market_value"] is not None
            else 0
        )

    except Exception:
        market_value = 0.0


    history[key].append({

        "jornada":
            row["jornada"],

        "player_id":
            row["player_id"],

        "master_player_id":
            row["master_player_id"],

        "player_name":
            row["player_name"],

        "team_name":
            row["team_name"],

        "position_id":
            row["position_id"],

        "week_points":
            puntos,

        "market_value":
            market_value,

        "minutos":
            minutos,
    })


# ================================================================
# ORDENAR HISTÓRICO
# ================================================================

for key in history:

    history[key] = sorted(
        history[key],
        key=lambda x: x["jornada"]
    )


# ================================================================
# ÚLTIMO REGISTRO
# ================================================================

jugadores = {}

for key, rows in history.items():

    if not rows:
        continue

    jugadores[key] = rows[-1]


# ================================================================
# PREDICTOR BASE
# ================================================================

def prediccion_media5_hist(prev):

    puntos = [
        x["week_points"]
        for x in prev
    ]

    if not puntos:
        return None

    ultimos5 = puntos[
        -VENTANA_RECIENTE:
    ]

    media5 = mean(
        ultimos5
    )

    media_hist = mean(
        puntos
    )

    pred = (
        0.60 * media5
        +
        0.40 * media_hist
    )

    return pred


# ================================================================
# PARTICIPACIÓN
# ================================================================

def calcular_participacion(prev):

    if not prev:

        return {
            "participacion": 0.0,
            "metodo": "Sin datos",
            "minutos_totales": 0.0,
            "jornadas_participadas": 0,
        }


    # ------------------------------------------------------------
    # MÉTODO 1: MINUTOS REALES
    # ------------------------------------------------------------

    tiene_minutos = any(
        x["minutos"] is not None
        for x in prev
    )


    if tiene_minutos:

        minutos_validos = [
            x["minutos"]
            for x in prev
            if x["minutos"] is not None
        ]

        minutos_totales = sum(
            minutos_validos
        )

        minutos_posibles = (
            len(prev) * 90
        )

        if minutos_posibles > 0:

            participacion = (
                minutos_totales
                /
                minutos_posibles
            )

        else:

            participacion = 0.0


        participacion = clamp(
            participacion,
            0.0,
            1.0
        )


        jornadas_participadas = sum(
            1
            for x in prev
            if (
                x["minutos"] is not None
                and x["minutos"] > 0
            )
        )


        return {

            "participacion":
                participacion,

            "metodo":
                "Minutos reales",

            "minutos_totales":
                minutos_totales,

            "jornadas_participadas":
                jornadas_participadas,
        }


    # ------------------------------------------------------------
    # MÉTODO 2: ESTIMACIÓN
    # ------------------------------------------------------------

    jornadas_participadas = sum(
        1
        for x in prev
        if abs(
            x["week_points"]
        ) > 0.001
    )

    participacion = (
        jornadas_participadas
        /
        len(prev)
    )

    return {

        "participacion":
            clamp(
                participacion,
                0.0,
                1.0
            ),

        "metodo":
            "Estimación por puntos",

        "minutos_totales":
            0.0,

        "jornadas_participadas":
            jornadas_participadas,
    }


# ================================================================
# CONFIANZA
# ================================================================

def calcular_confianza(
    prev,
    pred
):

    puntos = [
        x["week_points"]
        for x in prev
    ]

    if not puntos:
        return 0.0


    n = len(
        puntos
    )

    factor_muestra = clamp(
        n / 10.0,
        0.0,
        1.0
    )


    desviacion = stddev(
        puntos
    )

    factor_volatilidad = (
        1.0
        /
        (
            1.0
            +
            desviacion / 5.0
        )
    )


    recientes = puntos[-5:]

    media_reciente = mean(
        recientes
    )

    diferencia = abs(
        media_reciente
        -
        pred
    )

    factor_recencia = (
        1.0
        /
        (
            1.0
            +
            diferencia / 5.0
        )
    )


    confianza = (

        0.35
        *
        factor_muestra

        +

        0.40
        *
        factor_volatilidad

        +

        0.25
        *
        factor_recencia
    )


    return clamp(
        confianza,
        0.0,
        1.0
    )


def nivel_confianza(confianza):

    if confianza >= 0.75:
        return "Alta"

    if confianza >= 0.55:
        return "Media"

    return "Baja"


# ================================================================
# GENERAR PREDICCIONES
# ================================================================

print()
print("=" * 70)
print("GENERANDO PREDICCIONES")
print("=" * 70)


resultados = []

jugadores_filtrados_participacion = 0


for key, jugador in jugadores.items():

    prev = [
        x
        for x in history[key]
        if x["jornada"] < jornada_objetivo
    ]

    prev = sorted(
        prev,
        key=lambda x: x["jornada"]
    )


    if len(prev) < MIN_HISTORICO:
        continue


    pred = prediccion_media5_hist(
        prev
    )

    if pred is None:
        continue


    # ------------------------------------------------------------
    # PARTICIPACIÓN
    # ------------------------------------------------------------

    datos_participacion = (
        calcular_participacion(
            prev
        )
    )

    participacion = (
        datos_participacion[
            "participacion"
        ]
    )


    if (
        FILTRAR_BAJA_PARTICIPACION
        and
        participacion < MIN_PARTICIPACION
    ):

        jugadores_filtrados_participacion += 1

        continue


    # ------------------------------------------------------------
    # PRECIO
    # ------------------------------------------------------------

    precio = float(
        jugador["market_value"]
        or 0
    )

    precio_millones = (
        precio
        /
        1_000_000
    )


    if precio_millones > 0:

        valor_por_millon = (
            pred
            /
            precio_millones
        )

    else:

        valor_por_millon = 0.0


    puntos_por_10m = (
        valor_por_millon
        *
        10
    )


    # ------------------------------------------------------------
    # HISTÓRICO
    # ------------------------------------------------------------

    puntos = [
        x["week_points"]
        for x in prev
    ]

    media_historica = mean(
        puntos
    )

    recientes = puntos[
        -VENTANA_RECIENTE:
    ]

    media_reciente = mean(
        recientes
    )

    desviacion = stddev(
        puntos
    )

    mejor_puntuacion = max(
        puntos
    )

    partidos_explosion = sum(
        p >= 12
        for p in puntos
    )


    # ------------------------------------------------------------
    # CONFIANZA
    # ------------------------------------------------------------

    confianza = calcular_confianza(
        prev,
        pred
    )


    # ------------------------------------------------------------
    # RIESGO
    # ------------------------------------------------------------

    if abs(media_historica) > 0:

        coef_variacion = (
            desviacion
            /
            abs(media_historica)
        )

    else:

        coef_variacion = 1.0


    riesgo = clamp(
        coef_variacion / 2.0,
        0.0,
        1.0
    )


    seguridad = (
        1.0
        -
        riesgo
    )


    # ------------------------------------------------------------
    # TENDENCIA
    # ------------------------------------------------------------

    if media_historica > 0:

        diferencia_tendencia = (
            media_reciente
            -
            media_historica
        )

        tendencia_pct = (
            diferencia_tendencia
            /
            media_historica
            *
            100
        )

    else:

        tendencia_pct = 0.0


    if tendencia_pct >= 15:

        tendencia = "Subiendo"

    elif tendencia_pct <= -15:

        tendencia = "Bajando"

    else:

        tendencia = "Estable"


    # ------------------------------------------------------------
    # PARTICIPACIÓN NORMALIZADA
    # ------------------------------------------------------------

    participacion_score = (
        participacion
    )


    # ------------------------------------------------------------
    # SCORE DE JUGADOR
    # ------------------------------------------------------------

    score_jugador = (

        0.70
        *
        clamp(
            pred / 12.0,
            0.0,
            1.0
        )

        +

        0.15
        *
        participacion

        +

        0.15
        *
        seguridad
    )


    # ------------------------------------------------------------
    # PENALIZACIÓN PARTICIPACIÓN
    # ------------------------------------------------------------

    penalizacion_participacion = (

        1.0
        -
        (
            (
                1.0
                -
                participacion
            )
            *
            FUERZA_PENALIZACION_PARTICIPACION
        )
    )


    # ------------------------------------------------------------
    # PENALIZACIÓN RIESGO
    # ------------------------------------------------------------

    penalizacion_riesgo = (

        1.0
        -
        (
            riesgo
            *
            FUERZA_PENALIZACION_RIESGO
        )
    )


    prediccion_ajustada = (

        pred
        *
        penalizacion_participacion
        *
        penalizacion_riesgo
    )


    resultados.append({

        "temporada":
            TEMPORADA,

        "jornada_objetivo":
            jornada_objetivo,

        "player_id":
            jugador["player_id"],

        "master_player_id":
            jugador["master_player_id"],

        "player_name":
            jugador["player_name"],

        "team_name":
            jugador["team_name"],

        "position_id":
            jugador["position_id"],

        "position":
            posicion_nombre(
                jugador["position_id"]
            ),

        "historico_partidos":
            len(prev),

        "jornadas_participadas":
            datos_participacion[
                "jornadas_participadas"
            ],

        "participacion":
            round(
                participacion,
                3
            ),

        "participacion_pct":
            round(
                participacion * 100,
                1
            ),

        "metodo_participacion":
            datos_participacion[
                "metodo"
            ],

        "minutos_totales":
            round(
                datos_participacion[
                    "minutos_totales"
                ],
                0
            ),

        "prediccion":
            round(
                pred,
                2
            ),

        "prediccion_ajustada":
            round(
                prediccion_ajustada,
                2
            ),

        "precio":
            round(
                precio,
                0
            ),

        "precio_millones":
            round(
                precio_millones,
                2
            ),

        "valor_por_millon":
            round(
                valor_por_millon,
                4
            ),

        "puntos_por_10m":
            round(
                puntos_por_10m,
                2
            ),

        "confianza":
            round(
                confianza,
                3
            ),

        "nivel_confianza":
            nivel_confianza(
                confianza
            ),

        "riesgo":
            round(
                riesgo,
                3
            ),

        "riesgo_pct":
            round(
                riesgo * 100,
                1
            ),

        "seguridad":
            round(
                seguridad,
                3
            ),

        "score_jugador":
            round(
                score_jugador * 100,
                2
            ),

        "media_historica":
            round(
                media_historica,
                2
            ),

        "media_reciente":
            round(
                media_reciente,
                2
            ),

        "tendencia":
            tendencia,

        "tendencia_pct":
            round(
                tendencia_pct,
                1
            ),

        "desviacion":
            round(
                desviacion,
                2
            ),

        "coef_variacion":
            round(
                coef_variacion,
                3
            ),

        "mejor_puntuacion":
            round(
                mejor_puntuacion,
                2
            ),

        "explosiones_12+":
            partidos_explosion,

        "precio_anomalo":
            "Pendiente",
    })


print()
print(
    f"Jugadores filtrados por "
    f"baja participación: "
    f"{jugadores_filtrados_participacion}"
)

print(
    f"Jugadores analizados: "
    f"{len(resultados)}"
)


# ================================================================
# DETECTAR PRECIOS ANÓMALOS
# ================================================================

por_posicion = defaultdict(list)

for r in resultados:

    por_posicion[
        r["position"]
    ].append(r)


for posicion, rows in por_posicion.items():

    precios = [
        r["precio_millones"]
        for r in rows
        if r["precio_millones"] > 0
    ]

    if not precios:
        continue


    mediana_precio = percentile(
        precios,
        0.50
    )


    for r in rows:

        precio = r[
            "precio_millones"
        ]


        if precio <= 0:

            r[
                "precio_anomalo"
            ] = "Sin precio"

            continue


        if (
            precio
            <
            mediana_precio
            *
            PRECIO_ANOMALIA_FACTOR_BAJO
        ):

            r[
                "precio_anomalo"
            ] = "MUY BAJO"


        elif (
            precio
            >
            mediana_precio
            *
            PRECIO_ANOMALIA_FACTOR_ALTO
        ):

            r[
                "precio_anomalo"
            ] = "MUY ALTO"


        else:

            r[
                "precio_anomalo"
            ] = "Normal"


# ================================================================
# NORMALIZACIÓN POR POSICIÓN
# ================================================================

for posicion, rows in por_posicion.items():

    if not rows:
        continue

    predicciones = [
        r["prediccion_ajustada"]
        for r in rows
    ]

    valores = [
        r["valor_por_millon"]
        for r in rows
    ]

    participaciones = [
        r["participacion"]
        for r in rows
    ]

    seguridades = [
        r["seguridad"]
        for r in rows
    ]


    min_pred = min(
        predicciones
    )

    max_pred = max(
        predicciones
    )

    min_valor = min(
        valores
    )

    max_valor = max(
        valores
    )


    for r in rows:

        # --------------------------------------------------------
        # PREDICCIÓN
        # --------------------------------------------------------

        if max_pred > min_pred:

            score_pred = (
                r["prediccion_ajustada"]
                -
                min_pred
            ) / (
                max_pred
                -
                min_pred
            )

        else:

            score_pred = 0.5


        # --------------------------------------------------------
        # VALOR
        # --------------------------------------------------------

        if max_valor > min_valor:

            score_valor = (
                r["valor_por_millon"]
                -
                min_valor
            ) / (
                max_valor
                -
                min_valor
            )

        else:

            score_valor = 0.5


        # --------------------------------------------------------
        # PARTICIPACIÓN
        # --------------------------------------------------------

        score_participacion = (
            r["participacion"]
        )


        # --------------------------------------------------------
        # SEGURIDAD
        # --------------------------------------------------------

        score_seguridad = (
            r["seguridad"]
        )


        # --------------------------------------------------------
        # SCORE FINAL DE FICHAJE
        # --------------------------------------------------------

        score = (

            PESO_PREDICCION
            *
            score_pred

            +

            PESO_VALOR
            *
            score_valor

            +

            PESO_PARTICIPACION
            *
            score_participacion

            +

            PESO_SEGURIDAD
            *
            score_seguridad
        )


        r["score_fichaje"] = round(
            score * 100,
            2
        )


        r["score_prediccion"] = round(
            score_pred * 100,
            2
        )

        r["score_valor"] = round(
            score_valor * 100,
            2
        )

        r["score_participacion"] = round(
            score_participacion * 100,
            2
        )

        r["score_seguridad"] = round(
            score_seguridad * 100,
            2
        )


# ================================================================
# RECOMENDACIONES
# ================================================================

for posicion, rows in por_posicion.items():

    if not rows:
        continue

    scores = [
        r["score_fichaje"]
        for r in rows
    ]


    # ------------------------------------------------------------
    # PERCENTILES
    # ------------------------------------------------------------

    p95 = percentile(
        scores,
        0.95
    )

    p85 = percentile(
        scores,
        0.85
    )

    p55 = percentile(
        scores,
        0.55
    )

    p25 = percentile(
        scores,
        0.25
    )


    mediana_pred = percentile(
        [
            r["prediccion_ajustada"]
            for r in rows
        ],
        0.50
    )


    for r in rows:

        score = r[
            "score_fichaje"
        ]

        pred = r[
            "prediccion_ajustada"
        ]

        confianza = r[
            "confianza"
        ]

        participacion = r[
            "participacion"
        ]

        riesgo = r[
            "riesgo"
        ]


        # --------------------------------------------------------
        # COMPRA TOP
        # --------------------------------------------------------

        if (
            score >= p95
            and pred >= mediana_pred
            and confianza >= 0.60
            and participacion >= 0.60
            and riesgo <= 0.60
        ):

            recomendacion = (
                "COMPRA TOP"
            )


        # --------------------------------------------------------
        # COMPRAR
        # --------------------------------------------------------

        elif (
            score >= p85
            and confianza >= 0.45
            and participacion >= 0.45
        ):

            recomendacion = (
                "COMPRAR"
            )


        # --------------------------------------------------------
        # VENDER
        # --------------------------------------------------------

        elif (
            score <= p25
            and pred < mediana_pred
        ):

            recomendacion = (
                "VENDER"
            )


        # --------------------------------------------------------
        # NO PRIORITARIO
        # --------------------------------------------------------

        elif score <= p55:

            recomendacion = (
                "NO PRIORITARIO"
            )


        # --------------------------------------------------------
        # MANTENER
        # --------------------------------------------------------

        else:

            recomendacion = (
                "MANTENER"
            )


        r[
            "recomendacion"
        ] = recomendacion


# ================================================================
# ORDEN GLOBAL
# ================================================================

resultados.sort(

    key=lambda r: (

        r["score_fichaje"],

        r["prediccion_ajustada"],

        r["confianza"]

    ),

    reverse=True
)


for i, r in enumerate(
    resultados,
    start=1
):

    r[
        "ranking_global"
    ] = i


# ================================================================
# RANKING POR POSICIÓN
# ================================================================

for posicion, rows in por_posicion.items():

    ordenados = sorted(

        rows,

        key=lambda r: (

            r["score_fichaje"],

            r["prediccion_ajustada"],

            r["confianza"]

        ),

        reverse=True
    )


    for i, r in enumerate(
        ordenados,
        start=1
    ):

        r[
            "ranking_posicion"
        ] = i


# ================================================================
# TOP FICHAJES
# ================================================================

print()
print("=" * 70)
print("TOP FICHAJES")
print("=" * 70)


for r in resultados[:30]:

    print(

        f"{r['ranking_global']:>2}. "

        f"{str(r['player_name']):<25} "

        f"{r['position']:<15} "

        f"Pred={r['prediccion']:>5.2f} "

        f"Ajust={r['prediccion_ajustada']:>5.2f} "

        f"Precio={r['precio_millones']:>7.2f}M "

        f"Part={r['participacion_pct']:>5.1f}% "

        f"Riesgo={r['riesgo_pct']:>5.1f}% "

        f"Score={r['score_fichaje']:>5.1f} "

        f"{r['recomendacion']}"
    )


# ================================================================
# TOP POR POSICIÓN
# ================================================================

print()
print("=" * 70)
print("TOP POR POSICIÓN")
print("=" * 70)


for posicion in [

    "Portero",
    "Defensa",
    "Centrocampista",
    "Delantero",

]:

    print()
    print(posicion)


    rows = sorted(

        por_posicion.get(
            posicion,
            []
        ),

        key=lambda r: (

            r["score_fichaje"],

            r["prediccion_ajustada"]

        ),

        reverse=True
    )


    for r in rows[:10]:

        print(

            f"  {str(r['player_name']):<25} "

            f"Pred={r['prediccion']:>5.2f} "

            f"Ajust={r['prediccion_ajustada']:>5.2f} "

            f"Precio={r['precio_millones']:>7.2f}M "

            f"Part={r['participacion_pct']:>5.1f}% "

            f"Riesgo={r['riesgo_pct']:>5.1f}% "

            f"Score={r['score_fichaje']:>5.1f} "

            f"{r['recomendacion']}"
        )


# ================================================================
# MEJORES OPORTUNIDADES DE VALOR
# ================================================================

print()
print("=" * 70)
print("MEJORES OPORTUNIDADES POR VALOR")
print("=" * 70)


valorados = sorted(

    resultados,

    key=lambda r: (

        r["valor_por_millon"],

        r["prediccion_ajustada"]

    ),

    reverse=True
)


for r in valorados[:20]:

    print(

        f"{str(r['player_name']):<25} "

        f"{r['position']:<15} "

        f"Pred={r['prediccion']:>5.2f} "

        f"Ajust={r['prediccion_ajustada']:>5.2f} "

        f"Precio={r['precio_millones']:>7.2f}M "

        f"P/10M={r['puntos_por_10m']:>5.2f} "

        f"Part={r['participacion_pct']:>5.1f}% "

        f"Conf={r['nivel_confianza']}"
    )


# ================================================================
# MAYOR PREDICCIÓN
# ================================================================

print()
print("=" * 70)
print("MAYOR PREDICCIÓN DE PUNTOS")
print("=" * 70)


por_prediccion = sorted(

    resultados,

    key=lambda r: (

        r["prediccion"],

        r["confianza"]

    ),

    reverse=True
)


for r in por_prediccion[:20]:

    print(

        f"{str(r['player_name']):<25} "

        f"{r['position']:<15} "

        f"Pred={r['prediccion']:>5.2f} "

        f"Ajust={r['prediccion_ajustada']:>5.2f} "

        f"Precio={r['precio_millones']:>7.2f}M "

        f"Part={r['participacion_pct']:>5.1f}% "

        f"Conf={r['nivel_confianza']} "

        f"Riesgo={r['riesgo_pct']:>5.1f}% "

        f"Tendencia={r['tendencia']}"
    )


# ================================================================
# MEJORES JUGADORES POR SCORE DE JUGADOR
# ================================================================

print()
print("=" * 70)
print("MEJORES JUGADORES - CALIDAD PURA")
print("=" * 70)


por_calidad = sorted(

    resultados,

    key=lambda r: (

        r["score_jugador"],

        r["prediccion"]

    ),

    reverse=True
)


for r in por_calidad[:20]:

    print(

        f"{str(r['player_name']):<25} "

        f"{r['position']:<15} "

        f"Pred={r['prediccion']:>5.2f} "

        f"ScoreJugador={r['score_jugador']:>5.1f} "

        f"Part={r['participacion_pct']:>5.1f}% "

        f"Riesgo={r['riesgo_pct']:>5.1f}% "
    )


# ================================================================
# PRECIOS SOSPECHOSOS
# ================================================================

precios_anomalos = [

    r
    for r in resultados
    if r["precio_anomalo"]
    in (
        "MUY BAJO",
        "MUY ALTO"
    )
]


print()
print("=" * 70)
print("CONTROL DE PRECIOS")
print("=" * 70)


print(
    f"Precios marcados como anómalos: "
    f"{len(precios_anomalos)}"
)


for r in precios_anomalos[:20]:

    print(

        f"{str(r['player_name']):<25} "

        f"{r['position']:<15} "

        f"Precio={r['precio_millones']:>8.2f}M "

        f"{r['precio_anomalo']}"
    )


# ================================================================
# CSV
# ================================================================

fieldnames = [

    "ranking_global",
    "ranking_posicion",

    "temporada",
    "jornada_objetivo",

    "player_id",
    "master_player_id",

    "player_name",
    "team_name",

    "position_id",
    "position",

    "historico_partidos",

    "jornadas_participadas",

    "participacion",
    "participacion_pct",

    "metodo_participacion",

    "minutos_totales",

    "prediccion",
    "prediccion_ajustada",

    "precio",
    "precio_millones",

    "precio_anomalo",

    "valor_por_millon",
    "puntos_por_10m",

    "score_jugador",

    "score_prediccion",
    "score_valor",
    "score_participacion",
    "score_seguridad",

    "score_fichaje",

    "confianza",
    "nivel_confianza",

    "riesgo",
    "riesgo_pct",

    "seguridad",

    "media_historica",
    "media_reciente",

    "tendencia",
    "tendencia_pct",

    "desviacion",
    "coef_variacion",

    "mejor_puntuacion",

    "explosiones_12+",

    "recomendacion",
]


with open(

    OUTPUT_CSV,

    "w",

    newline="",

    encoding="utf-8-sig"

) as f:

    writer = csv.DictWriter(

        f,

        fieldnames=fieldnames

    )

    writer.writeheader()

    writer.writerows(
        resultados
    )


# ================================================================
# RESUMEN
# ================================================================

conteo = defaultdict(int)

for r in resultados:

    conteo[
        r["recomendacion"]
    ] += 1


print()
print("=" * 70)
print("RESUMEN DE RECOMENDACIONES")
print("=" * 70)


for recomendacion in [

    "COMPRA TOP",
    "COMPRAR",
    "MANTENER",
    "NO PRIORITARIO",
    "VENDER",

]:

    print(

        f"{recomendacion:<20}"

        f"{conteo[recomendacion]:>5}"
    )


# ================================================================
# CONTROL DE CALIDAD
# ================================================================

print()
print("=" * 70)
print("CONTROL DE CALIDAD")
print("=" * 70)


posiciones_desconocidas = [

    r
    for r in resultados
    if r["position"]
    == "Desconocida"
]


print(
    f"Registros finales: "
    f"{len(resultados)}"
)


print(
    f"Jugadores con posición desconocida: "
    f"{len(posiciones_desconocidas)}"
)


entrenadores_detectados = [

    r
    for r in resultados
    if r["position"]
    not in (
        "Portero",
        "Defensa",
        "Centrocampista",
        "Delantero"
    )
]


if entrenadores_detectados:

    print(
        "ERROR: hay registros sin posición válida."
    )

else:

    print(
        "OK: ningún entrenador/registro sin posición "
        "ha entrado en el ranking."
    )


# ------------------------------------------------------------
# Participación
# ------------------------------------------------------------

participaciones_bajas = [

    r
    for r in resultados
    if r["participacion"]
    <
    MIN_PARTICIPACION
]


print(
    f"Jugadores finales con participación "
    f"< {MIN_PARTICIPACION * 100:.0f}%: "
    f"{len(participaciones_bajas)}"
)


# ------------------------------------------------------------
# Precios
# ------------------------------------------------------------

print(
    f"Precios anómalos detectados: "
    f"{len(precios_anomalos)}"
)


# ------------------------------------------------------------
# Compra TOP
# ------------------------------------------------------------

print(
    f"COMPRA TOP: "
    f"{conteo['COMPRA TOP']}"
)


print(
    f"COMPRAR: "
    f"{conteo['COMPRAR']}"
)


# ================================================================
# CSV GENERADO
# ================================================================

print()
print("=" * 70)
print("CSV GENERADO")
print("=" * 70)

print(
    OUTPUT_CSV
)


# ================================================================
# FINAL
# ================================================================

conn.close()


print()
print("=" * 70)
print("RANKING DE FICHAJES AVANZADO TERMINADO")
print("=" * 70)