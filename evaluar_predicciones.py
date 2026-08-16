# -*- coding: utf-8 -*-

"""
================================================================
EVALUADOR DE PREDICCIONES - FANTASY LALIGA
================================================================

Evalúa las predicciones guardadas por mercado.py.

Horizontes válidos:

    1 día
    3 días
    5 días
    7 días
    14 días

Uso:

    python evaluar_predicciones.py
    python evaluar_predicciones.py Pedri
    python evaluar_predicciones.py "Lamine Yamal"
    python evaluar_predicciones.py 133609
"""

import sqlite3
import sys


# ================================================================
# CONFIGURACIÓN
# ================================================================

DB_PATH = r"C:\Users\Usuario\Desktop\fantasy_laliga\fantasy_laliga_v2.db"

HORIZONTES = [1, 3, 5, 7, 14]


# ================================================================
# CONEXIÓN
# ================================================================

def conectar():
    return sqlite3.connect(DB_PATH)


# ================================================================
# FORMATO
# ================================================================

def millones(valor):
    if valor is None:
        return "N/D"

    valor = float(valor) / 1_000_000

    return (
        f"{valor:,.2f}M"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def porcentaje(valor):
    if valor is None:
        return "N/D"

    return f"{float(valor):.2f}%"


# ================================================================
# COMPROBAR TABLA
# ================================================================

def comprobar_tabla(conn):

    cur = conn.cursor()

    cur.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name = 'prediction_history'
    """)

    if not cur.fetchone():

        raise RuntimeError(
            "No existe la tabla prediction_history."
        )


# ================================================================
# COLUMNAS
# ================================================================

def obtener_columnas(conn):

    cur = conn.cursor()

    cur.execute(
        'PRAGMA table_info("prediction_history")'
    )

    return [
        fila[1]
        for fila in cur.fetchall()
    ]


# ================================================================
# COMPROBAR ESTRUCTURA
# ================================================================

def comprobar_estructura(conn):

    columnas = obtener_columnas(conn)

    necesarias = [
        "id",
        "fecha_prediccion",
        "fecha_objetivo",
        "player_key",
        "master_player_id",
        "nickname",
        "horizonte_dias",
        "precio_inicial",
        "precio_predicho",
        "variacion_predicha",
        "probabilidad_subida",
        "confianza",
        "precio_real",
        "error",
        "error_absoluto",
        "error_porcentual",
        "evaluada"
    ]

    faltan = [
        columna
        for columna in necesarias
        if columna not in columnas
    ]

    if faltan:

        raise RuntimeError(
            "Faltan columnas en prediction_history: "
            + ", ".join(faltan)
        )


# ================================================================
# OBTENER PREDICCIONES
# ================================================================

def obtener_predicciones(
    conn,
    jugador=None
):
    """
    Obtiene únicamente predicciones válidas.

    IMPORTANTE:

    Se ignoran registros antiguos o incompletos
    que no tengan horizonte_dias válido.
    """

    cur = conn.cursor()

    columnas = obtener_columnas(conn)

    # ------------------------------------------------------------
    # Jugador
    # ------------------------------------------------------------

    if jugador:

        texto = str(jugador).strip()

        if texto.isdigit():

            cur.execute(
                """
                SELECT *
                FROM prediction_history
                WHERE master_player_id = ?
                  AND horizonte_dias IN (1, 3, 5, 7, 14)
                  AND fecha_objetivo IS NOT NULL
                ORDER BY fecha_prediccion ASC,
                         horizonte_dias ASC
                """,
                (int(texto),)
            )

        else:

            cur.execute(
                """
                SELECT *
                FROM prediction_history
                WHERE LOWER(TRIM(nickname))
                      LIKE LOWER(TRIM(?))
                  AND horizonte_dias IN (1, 3, 5, 7, 14)
                  AND fecha_objetivo IS NOT NULL
                ORDER BY fecha_prediccion ASC,
                         horizonte_dias ASC
                """,
                ("%" + texto + "%",)
            )

    # ------------------------------------------------------------
    # Todos
    # ------------------------------------------------------------

    else:

        cur.execute(
            """
            SELECT *
            FROM prediction_history
            WHERE horizonte_dias IN (1, 3, 5, 7, 14)
              AND fecha_objetivo IS NOT NULL
            ORDER BY fecha_prediccion ASC,
                     horizonte_dias ASC
            """
        )

    filas = cur.fetchall()

    resultado = []

    for fila in filas:

        registro = dict(
            zip(
                columnas,
                fila
            )
        )

        # --------------------------------------------------------
        # Seguridad adicional
        # --------------------------------------------------------

        try:

            horizonte = int(
                registro["horizonte_dias"]
            )

        except (
            TypeError,
            ValueError
        ):

            continue

        if horizonte not in HORIZONTES:
            continue

        if not registro.get(
            "fecha_objetivo"
        ):
            continue

        resultado.append(
            registro
        )

    return resultado


# ================================================================
# OBTENER PRECIO REAL
# ================================================================

def obtener_precio_real(
    conn,
    prediccion
):

    fecha_objetivo = prediccion[
        "fecha_objetivo"
    ]

    master_id = prediccion.get(
        "master_player_id"
    )

    player_key = prediccion.get(
        "player_key"
    )

    nickname = prediccion.get(
        "nickname"
    )

    cur = conn.cursor()

    # ------------------------------------------------------------
    # MASTER PLAYER ID
    # ------------------------------------------------------------

    if master_id is not None:

        cur.execute(
            """
            SELECT market_value
            FROM market_history
            WHERE master_player_id = ?
              AND fecha = ?
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            (
                master_id,
                fecha_objetivo
            )
        )

        fila = cur.fetchone()

        if fila:
            return float(fila[0])

    # ------------------------------------------------------------
    # PLAYER KEY
    # ------------------------------------------------------------

    if player_key is not None:

        cur.execute(
            """
            SELECT market_value
            FROM market_history
            WHERE player_key = ?
              AND fecha = ?
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            (
                player_key,
                fecha_objetivo
            )
        )

        fila = cur.fetchone()

        if fila:
            return float(fila[0])

    # ------------------------------------------------------------
    # NICKNAME
    # ------------------------------------------------------------

    cur.execute(
        """
        SELECT market_value
        FROM market_history
        WHERE LOWER(TRIM(nickname))
              = LOWER(TRIM(?))
          AND fecha = ?
        ORDER BY timestamp DESC
        LIMIT 1
        """,
        (
            nickname,
            fecha_objetivo
        )
    )

    fila = cur.fetchone()

    if fila:
        return float(fila[0])

    return None


# ================================================================
# CALCULAR ERROR
# ================================================================

def calcular_error(
    precio_predicho,
    precio_real
):

    error = (
        precio_real
        -
        precio_predicho
    )

    error_absoluto = abs(error)

    if precio_real != 0:

        error_porcentual = (
            error_absoluto
            /
            abs(precio_real)
        ) * 100

    else:

        error_porcentual = None

    return (
        error,
        error_absoluto,
        error_porcentual
    )


# ================================================================
# DIRECCIÓN
# ================================================================

def direccion_acertada(
    precio_inicial,
    precio_predicho,
    precio_real
):

    movimiento_predicho = (
        precio_predicho
        -
        precio_inicial
    )

    movimiento_real = (
        precio_real
        -
        precio_inicial
    )

    if (
        movimiento_predicho > 0
        and movimiento_real > 0
    ):
        return True

    if (
        movimiento_predicho < 0
        and movimiento_real < 0
    ):
        return True

    if (
        abs(movimiento_predicho) < 0.000001
        and
        abs(movimiento_real) < 0.000001
    ):
        return True

    return False


# ================================================================
# EVALUAR PREDICCIÓN
# ================================================================

def evaluar_prediccion(
    conn,
    prediccion
):

    if prediccion.get(
        "evaluada"
    ) == 1:

        return False

    precio_real = obtener_precio_real(
        conn,
        prediccion
    )

    # Todavía no ha llegado la fecha
    if precio_real is None:

        return False

    precio_predicho = float(
        prediccion["precio_predicho"]
    )

    precio_inicial = float(
        prediccion["precio_inicial"]
    )

    (
        error,
        error_absoluto,
        error_porcentual
    ) = calcular_error(
        precio_predicho,
        precio_real
    )

    cur = conn.cursor()

    cur.execute(
        """
        UPDATE prediction_history

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
            prediccion["id"]
        )
    )

    conn.commit()

    prediccion[
        "precio_real"
    ] = precio_real

    prediccion[
        "error"
    ] = error

    prediccion[
        "error_absoluto"
    ] = error_absoluto

    prediccion[
        "error_porcentual"
    ] = error_porcentual

    prediccion[
        "direccion_acertada"
    ] = direccion_acertada(
        precio_inicial,
        precio_predicho,
        precio_real
    )

    prediccion[
        "evaluada"
    ] = 1

    return True


# ================================================================
# EVALUAR TODAS
# ================================================================

def evaluar_todas(
    conn,
    jugador=None
):

    predicciones = obtener_predicciones(
        conn,
        jugador
    )

    nuevas = []

    for prediccion in predicciones:

        if evaluar_prediccion(
            conn,
            prediccion
        ):

            nuevas.append(
                prediccion
            )

    return (
        predicciones,
        nuevas
    )


# ================================================================
# ESTADÍSTICAS
# ================================================================

def calcular_estadisticas(
    predicciones
):

    resultado = {}

    for horizonte in HORIZONTES:

        datos = [
            p
            for p in predicciones
            if p.get(
                "horizonte_dias"
            ) == horizonte
            and p.get(
                "evaluada"
            ) == 1
            and p.get(
                "error_porcentual"
            ) is not None
        ]

        if not datos:

            resultado[horizonte] = None
            continue

        errores = [
            float(
                p["error_absoluto"]
            )
            for p in datos
        ]

        errores_porcentuales = [
            float(
                p["error_porcentual"]
            )
            for p in datos
        ]

        aciertos = 0

        for p in datos:

            if "direccion_acertada" in p:

                if p[
                    "direccion_acertada"
                ]:
                    aciertos += 1

            else:

                if direccion_acertada(
                    float(p["precio_inicial"]),
                    float(p["precio_predicho"]),
                    float(p["precio_real"])
                ):
                    aciertos += 1

        resultado[horizonte] = {

            "muestra":
                len(datos),

            "error_medio":
                sum(errores)
                /
                len(errores),

            "error_porcentual_medio":
                sum(errores_porcentuales)
                /
                len(errores_porcentuales),

            "acierto_direccion":
                (
                    aciertos
                    /
                    len(datos)
                ) * 100
        }

    return resultado


# ================================================================
# MOSTRAR EVALUACIONES
# ================================================================

def imprimir_evaluaciones(
    evaluadas
):

    if not evaluadas:
        return

    print()
    print("=" * 72)
    print("PREDICCIONES EVALUADAS")
    print("=" * 72)

    for p in evaluadas:

        print()

        print(
            f"Jugador: {p['nickname']}"
        )

        print(
            f"Fecha predicción: "
            f"{p['fecha_prediccion']}"
        )

        print(
            f"Horizonte: "
            f"{p['horizonte_dias']} días"
        )

        print(
            f"Predicho: "
            f"{millones(p['precio_predicho'])}"
        )

        print(
            f"Real:     "
            f"{millones(p['precio_real'])}"
        )

        signo = (
            "+"
            if p["error"] >= 0
            else ""
        )

        print(
            f"Error:    "
            f"{signo}"
            f"{millones(p['error'])}"
        )

        print(
            f"Error absoluto: "
            f"{millones(p['error_absoluto'])}"
        )

        print(
            f"Error porcentual: "
            f"{porcentaje(p['error_porcentual'])}"
        )

        print(
            "Dirección: "
            +
            (
                "ACERTADA"
                if p["direccion_acertada"]
                else "FALLADA"
            )
        )


# ================================================================
# MOSTRAR ESTADÍSTICAS
# ================================================================

def imprimir_estadisticas(
    estadisticas,
    jugador=None
):

    print()
    print("=" * 72)
    print("PRECISIÓN DEL MODELO")
    print("=" * 72)

    if jugador:

        print()
        print(
            f"Jugador: {jugador}"
        )

    print()

    print(
        f"{'Horizonte':<12}"
        f"{'Muestra':>10}"
        f"{'Error medio':>18}"
        f"{'Error %':>14}"
        f"{'Dirección':>16}"
    )

    print("-" * 72)

    total_muestras = 0
    total_aciertos = 0

    for horizonte in HORIZONTES:

        datos = estadisticas[
            horizonte
        ]

        if not datos:

            print(
                f"{horizonte} días"
                f"{'N/D':>10}"
                f"{'N/D':>18}"
                f"{'N/D':>14}"
                f"{'N/D':>16}"
            )

            continue

        muestra = datos[
            "muestra"
        ]

        acierto = datos[
            "acierto_direccion"
        ]

        total_muestras += muestra

        total_aciertos += (
            acierto
            *
            muestra
            /
            100
        )

        print(
            f"{horizonte} días"
            f"{muestra:>10}"
            f"{millones(datos['error_medio']):>18}"
            f"{porcentaje(datos['error_porcentual_medio']):>14}"
            f"{porcentaje(acierto):>16}"
        )

    print()

    if total_muestras > 0:

        precision_global = (
            total_aciertos
            /
            total_muestras
        ) * 100

        print(
            "Precisión global de dirección: "
            f"{precision_global:.2f}%"
        )

    else:

        print(
            "Todavía no existen suficientes "
            "predicciones evaluadas."
        )

    print()


# ================================================================
# PENDIENTES
# ================================================================

def imprimir_pendientes(
    predicciones
):

    pendientes = [
        p
        for p in predicciones
        if p.get("evaluada") != 1
    ]

    if not pendientes:
        return

    print()
    print("=" * 72)
    print("PREDICCIONES PENDIENTES")
    print("=" * 72)

    print()

    for p in pendientes:

        print(
            f"{p['nickname']:<25}"
            f"{p['fecha_prediccion']}"
            f"  +{p['horizonte_dias']} días"
            f"  objetivo: {p['fecha_objetivo']}"
        )

    print()

    print(
        "Estas predicciones todavía no tienen "
        "precio real disponible."
    )

    print()


# ================================================================
# ANALIZAR
# ================================================================

def analizar(
    jugador=None
):

    conn = conectar()

    try:

        comprobar_tabla(
            conn
        )

        comprobar_estructura(
            conn
        )

        print()
        print("=" * 72)
        print(
            "EVALUADOR DE PREDICCIONES - "
            "FANTASY LALIGA"
        )
        print("=" * 72)

        print()

        print(
            f"Base de datos: {DB_PATH}"
        )

        if jugador:

            print(
                f"Jugador: {jugador}"
            )

        (
            predicciones,
            nuevas
        ) = evaluar_todas(
            conn,
            jugador
        )

        if not predicciones:

            print()

            print(
                "No existen predicciones "
                "válidas guardadas."
            )

            return

        print()

        print(
            f"Predicciones válidas: "
            f"{len(predicciones)}"
        )

        print(
            f"Nuevas evaluaciones realizadas: "
            f"{len(nuevas)}"
        )

        # --------------------------------------------------------
        # Evaluaciones
        # --------------------------------------------------------

        imprimir_evaluaciones(
            nuevas
        )

        # --------------------------------------------------------
        # Estadísticas
        # --------------------------------------------------------

        estadisticas = calcular_estadisticas(
            predicciones
        )

        imprimir_estadisticas(
            estadisticas,
            jugador
        )

        # --------------------------------------------------------
        # Pendientes actualizadas
        # --------------------------------------------------------

        predicciones_actualizadas = obtener_predicciones(
            conn,
            jugador
        )

        imprimir_pendientes(
            predicciones_actualizadas
        )

    finally:

        conn.close()


# ================================================================
# MAIN
# ================================================================

def main():

    if len(sys.argv) > 1:

        jugador = " ".join(
            sys.argv[1:]
        )

    else:

        jugador = None

    try:

        analizar(
            jugador
        )

    except Exception as e:

        print()

        print("=" * 72)
        print("ERROR EN EL EVALUADOR")
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