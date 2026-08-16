# -*- coding: utf-8 -*-

"""
================================================================
PREDICTOR DE MERCADO - FANTASY LALIGA
================================================================

Predice la evolución del valor de mercado de un jugador a:

    1 día
    3 días
    5 días
    7 días
    14 días

Además:

    - Guarda cada predicción realizada.
    - Guarda fecha y hora de la predicción.
    - Guarda la versión del modelo.
    - Evalúa automáticamente predicciones anteriores.
    - Compara precio predicho vs precio real.
    - Calcula error absoluto y porcentual.
    - Evita duplicar predicciones del mismo día.
    - Utiliza market_history como histórico real.

Uso:

    python mercado.py Pedri
    python mercado.py "Lamine Yamal"
    python mercado.py 133609

También puede ser llamado desde:

    python analisis_fantasy.py mercado Pedri
"""


import sqlite3
import sys
import math
import statistics

from datetime import datetime, timedelta


# ================================================================
# CONFIGURACIÓN
# ================================================================

DB_PATH = r"C:\Users\Usuario\Desktop\fantasy_laliga\fantasy_laliga_v2.db"

HORIZONTES = [1, 3, 5, 7, 14]

TABLA_MERCADO = "market_history"

TABLA_PREDICCIONES = "prediction_history"

MIN_OBSERVACIONES = 2

MODEL_VERSION = "mercado_v1.1"


# ================================================================
# CONEXIÓN
# ================================================================

def conectar():

    return sqlite3.connect(DB_PATH)


# ================================================================
# UTILIDADES
# ================================================================

def convertir_precio(valor):
    """
    Convierte euros a millones.

    Ejemplo:

        88276911 -> 88.276911
    """

    if valor is None:
        return None

    try:
        return float(valor) / 1_000_000

    except (ValueError, TypeError):

        return None


def millones(valor):

    return (
        f"{valor:,.2f}M"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def euros(valor):

    return int(
        round(valor * 1_000_000)
    )


def porcentaje(valor):

    return f"{valor:.0f}%"


def parsear_fecha(valor):
    """
    Convierte fechas almacenadas en SQLite.
    """

    if valor is None:

        return None

    if isinstance(valor, datetime):

        return valor

    texto = str(valor).strip()

    formatos = [

        "%Y-%m-%dT%H:%M:%S.%f",

        "%Y-%m-%dT%H:%M:%S",

        "%Y-%m-%d %H:%M:%S.%f",

        "%Y-%m-%d %H:%M:%S",

        "%Y-%m-%d",

    ]

    for formato in formatos:

        try:

            return datetime.strptime(
                texto,
                formato
            )

        except ValueError:

            continue

    return None


# ================================================================
# BUSCAR JUGADOR
# ================================================================

def buscar_jugador(conn, jugador):

    texto = str(jugador).strip()

    cur = conn.cursor()

    # ------------------------------------------------------------
    # ID
    # ------------------------------------------------------------

    if texto.isdigit():

        cur.execute(
            """
            SELECT
                master_player_id,
                nickname,
                player_key,
                team_name
            FROM market_history
            WHERE master_player_id = ?
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            (int(texto),)
        )

        fila = cur.fetchone()

        if fila:

            return {

                "master_player_id": fila[0],

                "nickname": fila[1],

                "player_key": fila[2],

                "team_name": fila[3]

            }

        # --------------------------------------------------------
        # player_key
        # --------------------------------------------------------

        cur.execute(
            """
            SELECT
                master_player_id,
                nickname,
                player_key,
                team_name
            FROM market_history
            WHERE player_key = ?
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            (texto,)
        )

        fila = cur.fetchone()

        if fila:

            return {

                "master_player_id": fila[0],

                "nickname": fila[1],

                "player_key": fila[2],

                "team_name": fila[3]

            }

    # ------------------------------------------------------------
    # NOMBRE EXACTO
    # ------------------------------------------------------------

    cur.execute(
        """
        SELECT
            master_player_id,
            nickname,
            player_key,
            team_name
        FROM market_history
        WHERE LOWER(TRIM(nickname))
              =
              LOWER(TRIM(?))
        ORDER BY timestamp DESC
        LIMIT 1
        """,
        (texto,)
    )

    fila = cur.fetchone()

    if fila:

        return {

            "master_player_id": fila[0],

            "nickname": fila[1],

            "player_key": fila[2],

            "team_name": fila[3]

        }

    # ------------------------------------------------------------
    # NOMBRE PARCIAL
    # ------------------------------------------------------------

    cur.execute(
        """
        SELECT
            master_player_id,
            nickname,
            player_key,
            team_name
        FROM market_history
        WHERE LOWER(nickname)
              LIKE LOWER(?)
        ORDER BY timestamp DESC
        LIMIT 1
        """,
        ("%" + texto + "%",)
    )

    fila = cur.fetchone()

    if fila:

        return {

            "master_player_id": fila[0],

            "nickname": fila[1],

            "player_key": fila[2],

            "team_name": fila[3]

        }

    return None


# ================================================================
# OBTENER HISTÓRICO
# ================================================================

def obtener_historico(conn, jugador):

    cur = conn.cursor()

    master_id = jugador.get(
        "master_player_id"
    )

    player_key = jugador.get(
        "player_key"
    )

    nickname = jugador.get(
        "nickname"
    )

    # ------------------------------------------------------------
    # MASTER ID
    # ------------------------------------------------------------

    if master_id is not None:

        cur.execute(
            """
            SELECT
                fecha,
                timestamp,
                market_value,
                subida,
                frenada,
                titularity_percent
            FROM market_history
            WHERE master_player_id = ?
            ORDER BY timestamp ASC
            """,
            (master_id,)
        )

    # ------------------------------------------------------------
    # PLAYER KEY
    # ------------------------------------------------------------

    elif player_key is not None:

        cur.execute(
            """
            SELECT
                fecha,
                timestamp,
                market_value,
                subida,
                frenada,
                titularity_percent
            FROM market_history
            WHERE player_key = ?
            ORDER BY timestamp ASC
            """,
            (player_key,)
        )

    # ------------------------------------------------------------
    # NICKNAME
    # ------------------------------------------------------------

    else:

        cur.execute(
            """
            SELECT
                fecha,
                timestamp,
                market_value,
                subida,
                frenada,
                titularity_percent
            FROM market_history
            WHERE LOWER(TRIM(nickname))
                  =
                  LOWER(TRIM(?))
            ORDER BY timestamp ASC
            """,
            (nickname,)
        )

    filas = cur.fetchall()

    historico = []

    for fila in filas:

        fecha = parsear_fecha(
            fila[0]
        )

        timestamp = parsear_fecha(
            fila[1]
        )

        precio = convertir_precio(
            fila[2]
        )

        if precio is None:

            continue

        historico.append({

            "fecha": fecha,

            "timestamp": timestamp,

            "precio": precio,

            "subida": fila[3],

            "frenada": fila[4],

            "titularity": fila[5]

        })

    return historico


# ================================================================
# SERIE DIARIA
# ================================================================

def preparar_serie_diaria(historico):

    if not historico:

        return []

    dias = {}

    for registro in historico:

        fecha = registro["fecha"]

        if fecha is None:

            fecha = registro["timestamp"]

        if fecha is None:

            continue

        clave = fecha.date()

        # --------------------------------------------------------
        # Última captura del día
        # --------------------------------------------------------

        if clave not in dias:

            dias[clave] = registro

        else:

            anterior = dias[clave]

            ts_actual = registro["timestamp"]

            ts_anterior = anterior["timestamp"]

            if (
                ts_actual is not None
                and
                (
                    ts_anterior is None
                    or
                    ts_actual > ts_anterior
                )
            ):

                dias[clave] = registro

    serie = list(
        dias.values()
    )

    serie.sort(
        key=lambda x:
        (
            x["fecha"]
            if x["fecha"] is not None
            else x["timestamp"]
        )
    )

    return serie


# ================================================================
# VARIACIONES
# ================================================================

def calcular_variaciones(serie):

    if len(serie) < 2:

        return []

    variaciones = []

    for i in range(
        1,
        len(serie)
    ):

        anterior = serie[
            i - 1
        ]["precio"]

        actual = serie[
            i
        ]["precio"]

        variaciones.append(
            actual - anterior
        )

    return variaciones


# ================================================================
# MEDIA PONDERADA
# ================================================================

def media_ponderada(valores):

    if not valores:

        return 0.0

    pesos = list(
        range(
            1,
            len(valores) + 1
        )
    )

    numerador = sum(

        valor * peso

        for valor, peso
        in zip(
            valores,
            pesos
        )
    )

    denominador = sum(
        pesos
    )

    return (
        numerador
        /
        denominador
    )


# ================================================================
# TENDENCIA
# ================================================================

def calcular_tendencia(
    variaciones
):

    if not variaciones:

        return {

            "nombre":
                "SIN DATOS",

            "factor":
                0.0

        }

    recientes = (
        variaciones[-14:]
    )

    media = media_ponderada(
        recientes
    )

    mediana = statistics.median(
        recientes
    )

    factor = (

        media * 0.65

        +

        mediana * 0.35

    )

    if factor > 0.15:

        nombre = "ALCISTA"

    elif factor < -0.15:

        nombre = "BAJISTA"

    else:

        nombre = "ESTABLE"

    return {

        "nombre":
            nombre,

        "factor":
            factor

    }


# ================================================================
# VOLATILIDAD
# ================================================================

def calcular_volatilidad(
    variaciones
):

    if len(variaciones) < 2:

        return 0.0

    recientes = (
        variaciones[-14:]
    )

    try:

        return statistics.stdev(
            recientes
        )

    except statistics.StatisticsError:

        return 0.0


# ================================================================
# CONFIANZA
# ================================================================

def calcular_confianza(
    numero_observaciones,
    volatilidad,
    precio
):

    if numero_observaciones < 3:

        return "MUY BAJA"

    if numero_observaciones < 5:

        base = 35

    elif numero_observaciones < 10:

        base = 45

    elif numero_observaciones < 20:

        base = 60

    elif numero_observaciones < 40:

        base = 72

    else:

        base = 82

    if precio > 0:

        volatilidad_relativa = (

            volatilidad
            /
            precio

        )

        if volatilidad_relativa > 0.10:

            base -= 20

        elif volatilidad_relativa > 0.05:

            base -= 10

        elif volatilidad_relativa < 0.02:

            base += 5

    base = max(
        0,
        min(
            100,
            base
        )
    )

    if base >= 75:

        return "ALTA"

    if base >= 50:

        return "MEDIA"

    if base >= 30:

        return "BAJA"

    return "MUY BAJA"


# ================================================================
# PREDICCIÓN
# ================================================================

def predecir(serie):

    if len(serie) < MIN_OBSERVACIONES:

        raise RuntimeError(
            "No hay suficientes observaciones "
            "para realizar una predicción."
        )

    precio_actual = serie[-1][
        "precio"
    ]

    variaciones = calcular_variaciones(
        serie
    )

    if not variaciones:

        raise RuntimeError(
            "No hay suficientes cambios "
            "de precio para realizar "
            "una predicción."
        )

    tendencia = calcular_tendencia(
        variaciones
    )

    volatilidad = calcular_volatilidad(
        variaciones
    )

    corto = variaciones[-3:]

    medio = variaciones[-7:]

    largo = variaciones[-14:]

    if not corto:

        corto = variaciones

    if not medio:

        medio = variaciones

    if not largo:

        largo = variaciones

    media_corto = media_ponderada(
        corto
    )

    media_medio = media_ponderada(
        medio
    )

    media_largo = media_ponderada(
        largo
    )

    # ------------------------------------------------------------
    # ESTIMACIÓN DIARIA
    # ------------------------------------------------------------

    diaria = (

        media_corto * 0.50

        +

        media_medio * 0.30

        +

        media_largo * 0.20

    )

    diaria += (
        tendencia["factor"]
        * 0.20
    )

    # ------------------------------------------------------------
    # LÍMITE DE SEGURIDAD
    # ------------------------------------------------------------

    if precio_actual > 0:

        limite_diario = max(

            0.25,

            precio_actual * 0.04

        )

        diaria = max(

            -limite_diario,

            min(
                limite_diario,
                diaria
            )

        )

    # ------------------------------------------------------------
    # PREDICCIONES
    # ------------------------------------------------------------

    predicciones = {}

    for dias in HORIZONTES:

        if dias <= 3:

            factor = 1.00

        elif dias <= 7:

            factor = 0.88

        else:

            factor = 0.72

        variacion = (

            diaria
            *
            dias
            *
            factor

        )

        precio_futuro = (

            precio_actual
            +
            variacion

        )

        precio_futuro = max(
            0.01,
            precio_futuro
        )

        # --------------------------------------------------------
        # INCERTIDUMBRE
        # --------------------------------------------------------

        incertidumbre = (

            volatilidad
            *
            math.sqrt(dias)
            *
            1.65

        )

        bajo = max(

            0.01,

            precio_futuro
            -
            incertidumbre

        )

        alto = (

            precio_futuro
            +
            incertidumbre

        )

        # --------------------------------------------------------
        # PROBABILIDAD
        # --------------------------------------------------------

        if volatilidad > 0:

            z = (

                variacion
                /
                (
                    volatilidad
                    *
                    math.sqrt(dias)
                )

            )

            prob_subida = (

                50
                +
                50
                *
                math.tanh(
                    z / 2
                )

            )

        else:

            if variacion > 0:

                prob_subida = 75

            elif variacion < 0:

                prob_subida = 25

            else:

                prob_subida = 50

        prob_subida = max(

            1,

            min(
                99,
                prob_subida
            )

        )

        predicciones[dias] = {

            "variacion":
                variacion,

            "precio":
                precio_futuro,

            "bajo":
                bajo,

            "alto":
                alto,

            "probabilidad_subida":
                prob_subida

        }

    confianza = calcular_confianza(

        len(serie),

        volatilidad,

        precio_actual

    )

    return {

        "precio_actual":
            precio_actual,

        "tendencia":
            tendencia["nombre"],

        "variacion_diaria":
            diaria,

        "volatilidad":
            volatilidad,

        "confianza":
            confianza,

        "predicciones":
            predicciones,

        "observaciones":
            len(serie),

        "ultima_fecha":
            serie[-1]["fecha"],

        "primera_fecha":
            serie[0]["fecha"]

    }


# ================================================================
# CREAR / ACTUALIZAR TABLA DE PREDICCIONES
# ================================================================

def crear_tabla_predicciones(conn):

    cur = conn.cursor()

    # ------------------------------------------------------------
    # Crear tabla si no existe
    # ------------------------------------------------------------

    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {TABLA_PREDICCIONES} (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            fecha_prediccion TEXT NOT NULL,

            timestamp_prediccion TEXT NOT NULL,

            fecha_objetivo TEXT NOT NULL,

            player_key TEXT,

            master_player_id INTEGER,

            nickname TEXT NOT NULL,

            horizonte_dias INTEGER NOT NULL,

            precio_inicial REAL NOT NULL,

            precio_predicho REAL NOT NULL,

            variacion_predicha REAL NOT NULL,

            probabilidad_subida REAL,

            confianza TEXT,

            model_version TEXT NOT NULL,

            precio_real REAL,

            error REAL,

            error_absoluto REAL,

            error_porcentual REAL,

            evaluada INTEGER DEFAULT 0

        )
        """
    )

    conn.commit()

    # ------------------------------------------------------------
    # Comprobar columnas existentes
    # ------------------------------------------------------------

    cur.execute(
        f"""
        PRAGMA table_info(
            {TABLA_PREDICCIONES}
        )
        """
    )

    columnas = {
        fila[1]
        for fila in cur.fetchall()
    }

    # ------------------------------------------------------------
    # Añadir columnas que puedan faltar
    # ------------------------------------------------------------

    columnas_nuevas = {

        "timestamp_prediccion":
            "TEXT",

        "fecha_objetivo":
            "TEXT",

        "horizonte_dias":
            "INTEGER",

        "precio_inicial":
            "REAL",

        "precio_predicho":
            "REAL",

        "variacion_predicha":
            "REAL",

        "probabilidad_subida":
            "REAL",

        "confianza":
            "TEXT",

        "model_version":
            "TEXT",

        "precio_real":
            "REAL",

        "error":
            "REAL",

        "error_absoluto":
            "REAL",

        "error_porcentual":
            "REAL",

        "evaluada":
            "INTEGER DEFAULT 0"

    }

    for nombre, tipo in columnas_nuevas.items():

        if nombre not in columnas:

            try:

                cur.execute(
                    f"""
                    ALTER TABLE
                    {TABLA_PREDICCIONES}
                    ADD COLUMN
                    {nombre}
                    {tipo}
                    """
                )

                print(
                    f"Columna añadida: "
                    f"{nombre}"
                )

            except sqlite3.OperationalError:

                pass

    conn.commit()


# ================================================================
# BUSCAR PRECIO REAL
# ================================================================

def obtener_precio_real(
    conn,
    jugador,
    fecha_objetivo
):

    cur = conn.cursor()

    master_id = jugador.get(
        "master_player_id"
    )

    player_key = jugador.get(
        "player_key"
    )

    nickname = jugador.get(
        "nickname"
    )

    fecha_texto = (
        fecha_objetivo.isoformat()
    )

    # ------------------------------------------------------------
    # MASTER ID
    # ------------------------------------------------------------

    if master_id is not None:

        cur.execute(
            """
            SELECT
                market_value
            FROM market_history
            WHERE master_player_id = ?
              AND fecha = ?
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            (
                master_id,
                fecha_texto
            )
        )

        fila = cur.fetchone()

        if fila:

            return convertir_precio(
                fila[0]
            )

    # ------------------------------------------------------------
    # PLAYER KEY
    # ------------------------------------------------------------

    if player_key is not None:

        cur.execute(
            """
            SELECT
                market_value
            FROM market_history
            WHERE player_key = ?
              AND fecha = ?
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            (
                player_key,
                fecha_texto
            )
        )

        fila = cur.fetchone()

        if fila:

            return convertir_precio(
                fila[0]
            )

    # ------------------------------------------------------------
    # NICKNAME
    # ------------------------------------------------------------

    cur.execute(
        """
        SELECT
            market_value
        FROM market_history
        WHERE LOWER(TRIM(nickname))
              =
              LOWER(TRIM(?))
          AND fecha = ?
        ORDER BY timestamp DESC
        LIMIT 1
        """,
        (
            nickname,
            fecha_texto
        )
    )

    fila = cur.fetchone()

    if fila:

        return convertir_precio(
            fila[0]
        )

    return None


# ================================================================
# EVALUAR PREDICCIONES ANTERIORES
# ================================================================

def evaluar_predicciones(
    conn,
    jugador
):
    """
    Busca predicciones antiguas cuyo día objetivo
    ya ha llegado y las compara con el precio real.

    Esto permite que el sistema empiece a construir
    un histórico de aciertos y errores.
    """

    crear_tabla_predicciones(
        conn
    )

    cur = conn.cursor()

    master_id = jugador.get(
        "master_player_id"
    )

    player_key = jugador.get(
        "player_key"
    )

    nickname = jugador.get(
        "nickname"
    )

    # ------------------------------------------------------------
    # Buscar predicciones pendientes
    # ------------------------------------------------------------

    if master_id is not None:

        cur.execute(
            f"""
            SELECT
                id,
                fecha_objetivo,
                precio_predicho
            FROM {TABLA_PREDICCIONES}
            WHERE master_player_id = ?
              AND evaluada = 0
            ORDER BY fecha_objetivo ASC
            """,
            (master_id,)
        )

    elif player_key is not None:

        cur.execute(
            f"""
            SELECT
                id,
                fecha_objetivo,
                precio_predicho
            FROM {TABLA_PREDICCIONES}
            WHERE player_key = ?
              AND evaluada = 0
            ORDER BY fecha_objetivo ASC
            """,
            (player_key,)
        )

    else:

        cur.execute(
            f"""
            SELECT
                id,
                fecha_objetivo,
                precio_predicho
            FROM {TABLA_PREDICCIONES}
            WHERE LOWER(TRIM(nickname))
                  =
                  LOWER(TRIM(?))
              AND evaluada = 0
            ORDER BY fecha_objetivo ASC
            """,
            (nickname,)
        )

    predicciones = cur.fetchall()

    evaluadas = 0

    hoy = datetime.now().date()

    for fila in predicciones:

        prediction_id = fila[0]

        fecha_objetivo = parsear_fecha(
            fila[1]
        )

        precio_predicho = fila[2]

        if fecha_objetivo is None:

            continue

        fecha_objetivo = (
            fecha_objetivo.date()
        )

        # --------------------------------------------------------
        # Todavía no toca evaluarla
        # --------------------------------------------------------

        if fecha_objetivo > hoy:

            continue

        # --------------------------------------------------------
        # Buscar precio real
        # --------------------------------------------------------

        precio_real = obtener_precio_real(

            conn,

            jugador,

            fecha_objetivo

        )

        if precio_real is None:

            continue

        # --------------------------------------------------------
        # Errores
        # --------------------------------------------------------

        error = (

            precio_real
            -
            precio_predicho

        )

        error_absoluto = abs(
            error
        )

        if precio_real != 0:

            error_porcentual = (

                error_absoluto
                /
                precio_real
                *
                100

            )

        else:

            error_porcentual = 0

        # --------------------------------------------------------
        # Actualizar
        # --------------------------------------------------------

        cur.execute(
            f"""
            UPDATE {TABLA_PREDICCIONES}

            SET

                precio_real = ?,

                error = ?,

                error_absoluto = ?,

                error_porcentual = ?,

                evaluada = 1

            WHERE id = ?
            """,
            (
                precio_real,

                error,

                error_absoluto,

                error_porcentual,

                prediction_id

            )
        )

        evaluadas += 1

    conn.commit()

    return evaluadas


# ================================================================
# GUARDAR NUEVAS PREDICCIONES
# ================================================================

def guardar_predicciones(
    conn,
    jugador,
    resultado
):

    crear_tabla_predicciones(
        conn
    )

    ahora = datetime.now()

    fecha_prediccion = (
        ahora.date().isoformat()
    )

    timestamp_prediccion = (
        ahora.isoformat()
    )

    cur = conn.cursor()

    guardadas = 0

    for dias in HORIZONTES:

        prediccion = resultado[
            "predicciones"
        ][dias]

        fecha_objetivo = (

            ahora.date()
            +
            timedelta(
                days=dias
            )

        )

        # --------------------------------------------------------
        # Comprobar duplicado
        # --------------------------------------------------------

        cur.execute(
            f"""
            SELECT id
            FROM {TABLA_PREDICCIONES}

            WHERE nickname = ?

              AND fecha_prediccion = ?

              AND horizonte_dias = ?

            LIMIT 1
            """,
            (
                jugador["nickname"],

                fecha_prediccion,

                dias

            )
        )

        existente = cur.fetchone()

        if existente:

            continue

        # --------------------------------------------------------
        # Insertar
        # --------------------------------------------------------

        cur.execute(
            f"""
            INSERT INTO {TABLA_PREDICCIONES} (

                fecha_prediccion,

                timestamp_prediccion,

                fecha_objetivo,

                player_key,

                master_player_id,

                nickname,

                horizonte_dias,

                precio_inicial,

                precio_predicho,

                variacion_predicha,

                probabilidad_subida,

                confianza,

                model_version,

                evaluada

            )

            VALUES (

                ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, 0

            )
            """,
            (

                fecha_prediccion,

                timestamp_prediccion,

                fecha_objetivo.isoformat(),

                jugador.get(
                    "player_key"
                ),

                jugador.get(
                    "master_player_id"
                ),

                jugador["nickname"],

                dias,

                resultado[
                    "precio_actual"
                ],

                prediccion[
                    "precio"
                ],

                prediccion[
                    "variacion"
                ],

                prediccion[
                    "probabilidad_subida"
                ],

                resultado[
                    "confianza"
                ],

                MODEL_VERSION

            )
        )

        guardadas += 1

    conn.commit()

    return guardadas


# ================================================================
# MOSTRAR RESULTADO
# ================================================================

def imprimir_resultado(
    jugador,
    resultado
):

    print()

    print("=" * 72)
    print("PREDICTOR DE MERCADO")
    print("=" * 72)

    print()

    print(
        f"Jugador: {jugador}"
    )

    print(
        "Precio actual: "
        f"{millones(resultado['precio_actual'])}"
    )

    print(
        "Variación diaria estimada: "
        f"{resultado['variacion_diaria']:+.2f}M"
    )

    print(
        "Tendencia: "
        f"{resultado['tendencia']}"
    )

    print(
        "Confianza: "
        f"{resultado['confianza']}"
    )

    print(
        "Observaciones históricas: "
        f"{resultado['observaciones']}"
    )

    if resultado[
        "primera_fecha"
    ]:

        print(
            "Desde: "
            +
            resultado[
                "primera_fecha"
            ].strftime(
                "%Y-%m-%d"
            )
        )

    if resultado[
        "ultima_fecha"
    ]:

        print(
            "Hasta: "
            +
            resultado[
                "ultima_fecha"
            ].strftime(
                "%Y-%m-%d"
            )
        )

    print()

    print("=" * 72)
    print("PREDICCIÓN DE VALOR")
    print("=" * 72)

    print()

    print(
        f"{'Horizonte':<12}"
        f"{'Variación':>14}"
        f"{'Precio previsto':>20}"
        f"{'Prob. subida':>16}"
    )

    print("-" * 72)

    for dias in HORIZONTES:

        p = resultado[
            "predicciones"
        ][dias]

        etiqueta = (
            "día"
            if dias == 1
            else "días"
        )

        print(

            f"{dias} {etiqueta:<9}"

            f"{p['variacion']:>+13.2f}M"

            f"{millones(p['precio']):>20}"

            f"{porcentaje(p['probabilidad_subida']):>16}"

        )

    print()

    print("=" * 72)
    print("INTERVALOS ESTIMADOS")
    print("=" * 72)

    print()

    for dias in HORIZONTES:

        p = resultado[
            "predicciones"
        ][dias]

        print(

            f"{dias:>2} días: "

            f"{millones(p['bajo'])}"

            " - "

            f"{millones(p['alto'])}"

        )

    print()

    print("=" * 72)
    print("CONCLUSIÓN")
    print("=" * 72)

    print()

    p7 = resultado[
        "predicciones"
    ][7]

    p14 = resultado[
        "predicciones"
    ][14]

    if resultado[
        "tendencia"
    ] == "ALCISTA":

        print(
            "El modelo detecta una "
            "tendencia ALCISTA."
        )

        print()

        print(
            "Revalorización estimada a 7 días: "
            f"{p7['variacion']:+.2f}M"
        )

        print(
            "Revalorización estimada a 14 días: "
            f"{p14['variacion']:+.2f}M"
        )

        if p7[
            "probabilidad_subida"
        ] >= 70:

            print()

            print(
                "RECOMENDACIÓN: INTERESANTE "
                "COMO INVERSIÓN DE MERCADO"
            )

        else:

            print()

            print(
                "RECOMENDACIÓN: TENDENCIA "
                "POSITIVA, PERO CON CAUTELA"
            )

    elif resultado[
        "tendencia"
    ] == "BAJISTA":

        print(
            "El modelo detecta una "
            "tendencia BAJISTA."
        )

        print()

        print(
            "Variación estimada a 7 días: "
            f"{p7['variacion']:+.2f}M"
        )

        print(
            "Variación estimada a 14 días: "
            f"{p14['variacion']:+.2f}M"
        )

        print()

        print(
            "RECOMENDACIÓN: EVITAR COMPRA "
            "COMO INVERSIÓN DE MERCADO"
        )

    else:

        print(
            "El mercado del jugador presenta "
            "una tendencia ESTABLE."
        )

        print()

        print(
            "RECOMENDACIÓN: NO SE DETECTA "
            "UNA REVALORIZACIÓN CLARA."
        )

    print()


# ================================================================
# ANALIZAR MERCADO
# ================================================================

def analizar_mercado(jugador):

    conn = conectar()

    try:

        # --------------------------------------------------------
        # Preparar sistema de predicciones
        # --------------------------------------------------------

        crear_tabla_predicciones(
            conn
        )

        # --------------------------------------------------------
        # Buscar jugador
        # --------------------------------------------------------

        datos_jugador = buscar_jugador(
            conn,
            jugador
        )

        if not datos_jugador:

            print()

            print(
                f"No se encontró el jugador: "
                f"{jugador}"
            )

            return False

        nombre_real = datos_jugador[
            "nickname"
        ]

        # --------------------------------------------------------
        # Histórico
        # --------------------------------------------------------

        historico = obtener_historico(
            conn,
            datos_jugador
        )

        serie = preparar_serie_diaria(
            historico
        )

        print()

        print(
            f"Histórico encontrado para "
            f"{nombre_real}: "
            f"{len(serie)} días"
        )

        # --------------------------------------------------------
        # Evaluar predicciones anteriores
        # --------------------------------------------------------

        evaluadas = evaluar_predicciones(

            conn,

            datos_jugador

        )

        if evaluadas > 0:

            print()

            print(
                f"Predicciones anteriores "
                f"evaluadas: {evaluadas}"
            )

        # --------------------------------------------------------
        # Comprobar histórico
        # --------------------------------------------------------

        if len(serie) < 2:

            print()

            print(
                f"No hay suficiente histórico "
                f"de precios para "
                f"{nombre_real}."
            )

            print()

            print(
                "Se necesitan al menos "
                "2 días con valores de mercado."
            )

            return False

        # --------------------------------------------------------
        # Crear predicción
        # --------------------------------------------------------

        resultado = predecir(
            serie
        )

        # --------------------------------------------------------
        # Guardar predicciones
        # --------------------------------------------------------

        guardadas = guardar_predicciones(

            conn,

            datos_jugador,

            resultado

        )

        # --------------------------------------------------------
        # Mostrar resultado
        # --------------------------------------------------------

        imprimir_resultado(

            nombre_real,

            resultado

        )

        print()

        print(
            f"Predicciones guardadas: "
            f"{guardadas}"
        )

        print(
            f"Versión del modelo: "
            f"{MODEL_VERSION}"
        )

        return True

    finally:

        conn.close()


# ================================================================
# CLI
# ================================================================

def main():

    if len(sys.argv) < 2:

        print()

        print(
            "Uso:"
        )

        print()

        print(
            "  python mercado.py Pedri"
        )

        print(
            '  python mercado.py "Lamine Yamal"'
        )

        print(
            "  python mercado.py 133609"
        )

        print()

        return

    jugador = " ".join(
        sys.argv[1:]
    )

    try:

        analizar_mercado(
            jugador
        )

    except Exception as e:

        print()

        print("=" * 72)
        print(
            "ERROR EN EL PREDICTOR DE MERCADO"
        )
        print("=" * 72)

        print()

        print(
            str(e)
        )

        print()


# ================================================================
# EJECUCIÓN
# ================================================================

if __name__ == "__main__":

    main()