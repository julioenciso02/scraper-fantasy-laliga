import requests
import sqlite3
import json
import re
import os
from datetime import datetime


# ================================================================
# CONFIGURACIÓN
# ================================================================

TEMPORADA = 2025

DB_PATH = r"C:\Users\Usuario\Desktop\fantasy_laliga\fantasy_historico.db"

BASE_URL = (
    "https://www.analiticafantasy.com/"
    "puntuaciones-fantasy-jornada/"
    "la-liga-fantasy"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}


# ================================================================
# BASE DE DATOS
# ================================================================

def crear_base_datos():

    conn = sqlite3.connect(DB_PATH)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS fantasy_points_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            temporada INTEGER NOT NULL,
            jornada INTEGER NOT NULL,

            player_id INTEGER,
            master_player_id INTEGER,

            player_name TEXT,
            team_name TEXT,
            position_id INTEGER,

            week_points REAL,
            market_value REAL,
            subida REAL,

            slug TEXT,

            url TEXT,
            fecha_captura TEXT,

            UNIQUE (
                temporada,
                jornada,
                player_id
            )
        )
    """)

    conn.commit()

    return conn


# ================================================================
# DESCARGA
# ================================================================

def descargar_jornada(jornada):

    url = f"{BASE_URL}/{TEMPORADA}/{jornada}"

    print("=" * 70)
    print(f"JORNADA {jornada}")
    print("=" * 70)
    print(url)

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=30
        )

        print(
            f"Status: {response.status_code}"
        )

        print(
            f"Bytes: {len(response.content)}"
        )

        if response.status_code != 200:
            print("✗ HTTP incorrecto")
            return None, url

        return response.text, url

    except Exception as e:

        print(
            f"✗ Error descargando jornada {jornada}: {e}"
        )

        return None, url


# ================================================================
# EXTRACCIÓN DEL SNAPSHOT
# ================================================================

def extraer_players_snapshot(texto):
    import json
    import re

    # El RSC contiene las comillas escapadas:
    #
    # fantasyLiveInitialSnapshot\":{\"players\":[{...}]}
    #
    # Buscamos el comienzo del snapshot.
    marcador = r'fantasyLiveInitialSnapshot\\":\{'

    m = re.search(marcador, texto)

    if not m:
        print("✗ No se encontró fantasyLiveInitialSnapshot")
        return None

    print(f"Snapshot encontrado: {m.start()}")

    # Cogemos todo lo que queda después del comienzo del snapshot
    # y desescapamos las comillas del RSC.
    fragmento = texto[m.start():]

    fragmento = fragmento.replace('\\"', '"')

    # Ahora debería existir literalmente:
    #
    # fantasyLiveInitialSnapshot":{"players":[
    #
    marcador_players = '"players":['

    posicion_players = fragmento.find(marcador_players)

    if posicion_players == -1:
        print("✗ No se encontró el campo players")
        return None

    inicio_array = (
        posicion_players
        + len('"players":')
    )

    print(
        f"Array players encontrado en posición: "
        f"{m.start() + inicio_array}"
    )

    # ------------------------------------------------------------
    # json.JSONDecoder.raw_decode() es ideal aquí.
    #
    # No necesitamos averiguar manualmente dónde termina el array.
    # Python lee exactamente un valor JSON y nos devuelve además
    # dónde termina.
    # ------------------------------------------------------------

    decoder = json.JSONDecoder()

    try:

        players, posicion_final = decoder.raw_decode(
            fragmento[inicio_array:]
        )

    except json.JSONDecodeError as e:

        print(
            f"✗ Error decodificando players: {e}"
        )

        debug_path = (
            r"C:\Users\Usuario\Desktop"
            r"\fantasy_laliga"
            r"\debug_players_error.txt"
        )

        try:

            with open(
                debug_path,
                "w",
                encoding="utf-8"
            ) as f:

                f.write(
                    fragmento[
                        inicio_array:
                    ]
                )

            print(
                f"Fragmento guardado en: "
                f"{debug_path}"
            )

        except Exception as debug_error:

            print(
                f"No se pudo guardar debug: "
                f"{debug_error}"
            )

        return None

    if not isinstance(players, list):

        print(
            "✗ El campo players no es una lista"
        )

        return None

    print(
        f"✓ Players encontrados: "
        f"{len(players)}"
    )

    return players


# ================================================================
# PROCESAR JUGADORES
# ================================================================

def procesar_jugadores(
    conn,
    players,
    jornada,
    url
):

    if not players:

        return 0

    fecha_captura = datetime.now().isoformat(
        timespec="seconds"
    )

    insertados = 0

    for player in players:

        try:

            player_id = player.get(
                "playerId"
            )

            master_player_id = player.get(
                "masterPlayerId"
            )

            player_name = player.get(
                "playerName"
            )

            position_id = player.get(
                "positionId"
            )

            team_name = player.get(
                "teamName"
            )

            week_points = player.get(
                "weekPoints"
            )

            market_value = player.get(
                "marketValue"
            )

            subida = player.get(
                "subida"
            )

            slug = player.get(
                "slug"
            )

            conn.execute(
                """
                INSERT OR REPLACE INTO
                fantasy_points_history
                (
                    temporada,
                    jornada,

                    player_id,
                    master_player_id,

                    player_name,
                    team_name,
                    position_id,

                    week_points,
                    market_value,
                    subida,

                    slug,

                    url,
                    fecha_captura
                )
                VALUES (
                    ?, ?,
                    ?, ?,
                    ?, ?, ?,
                    ?, ?, ?,
                    ?,
                    ?, ?
                )
                """,
                (
                    TEMPORADA,
                    jornada,

                    player_id,
                    master_player_id,

                    player_name,
                    team_name,
                    position_id,

                    week_points,
                    market_value,
                    subida,

                    slug,

                    url,
                    fecha_captura
                )
            )

            insertados += 1

        except Exception as e:

            print(
                "✗ Error procesando jugador:",
                player
            )

            print(
                "  Error:",
                e
            )

    conn.commit()

    return insertados


# ================================================================
# DEBUG
# ================================================================

def guardar_debug(
    texto,
    jornada
):

    debug_path = (
        r"C:\Users\Usuario\Desktop"
        r"\fantasy_laliga"
        f"\\debug_jornada_{jornada}_rsc.txt"
    )

    try:

        with open(
            debug_path,
            "w",
            encoding="utf-8"
        ) as f:

            f.write(texto)

        print(
            f"HTML/RSC guardado en:"
        )

        print(
            debug_path
        )

    except Exception as e:

        print(
            f"No se pudo guardar debug: {e}"
        )


# ================================================================
# RESUMEN
# ================================================================

def mostrar_resumen(conn):

    print()
    print("=" * 70)
    print("RESUMEN")
    print("=" * 70)

    total = conn.execute(
        """
        SELECT COUNT(*)
        FROM fantasy_points_history
        """
    ).fetchone()[0]

    jornadas = conn.execute(
        """
        SELECT
            jornada,
            COUNT(*)
        FROM fantasy_points_history
        GROUP BY jornada
        ORDER BY jornada
        """
    ).fetchall()

    print(
        f"Total registros: {total}"
    )

    print()

    for jornada, cantidad in jornadas:

        print(
            f"Jornada {jornada}: "
            f"{cantidad} jugadores"
        )


# ================================================================
# MAIN
# ================================================================

def main():

    print()
    print("=" * 70)
    print("FANTASY LALIGA - SCRAPER HISTÓRICO")
    print("=" * 70)

    print()
    print(
        f"Temporada: {TEMPORADA}"
    )

    print(
        f"Base de datos: {DB_PATH}"
    )

    print()

    # ------------------------------------------------------------
    # Crear carpeta si no existe
    # ------------------------------------------------------------

    os.makedirs(
        os.path.dirname(DB_PATH),
        exist_ok=True
    )

    conn = crear_base_datos()

    total_procesados = 0

    # ============================================================
    # PRUEBA: SOLO JORNADAS 1 Y 2
    # ============================================================

    for jornada in range(1, 39):

        texto, url = descargar_jornada(
            jornada
        )

        if texto is None:

            print(
                "✗ NO SE PUDO DESCARGAR "
                f"JORNADA {jornada}"
            )

            print()

            continue

        players = extraer_players_snapshot(
            texto
        )

        if players is None:

            print(
                "✗ NO SE PUDO OBTENER "
                f"JORNADA {jornada}"
            )

            guardar_debug(
                texto,
                jornada
            )

            print()

            continue

        cantidad = procesar_jugadores(
            conn,
            players,
            jornada,
            url
        )

        print(
            f"✓ Registros insertados: "
            f"{cantidad}"
        )

        total_procesados += cantidad

        print()

    # ============================================================
    # RESULTADO
    # ============================================================

    mostrar_resumen(
        conn
    )

    print()
    print(
        f"Registros procesados en esta ejecución: "
        f"{total_procesados}"
    )

    print()

    conn.close()


# ================================================================
# EJECUCIÓN
# ================================================================

if __name__ == "__main__":

    main()