# -*- coding: utf-8 -*-

"""
============================================================
             FANTASY LALIGA - MOTOR PRINCIPAL
============================================================

Módulo integrador del proyecto.

Utiliza los motores existentes:
    - analisis_fantasy.py
    - ranking_fichajes.py

Comandos directos:

    python fantasy.py jugador Pedri
    python fantasy.py jugador 133609
    python fantasy.py puja Pedri
    python fantasy.py oportunidad
    python fantasy.py fichajes

También dispone de un menú interactivo:
    python fantasy.py
"""

import sys
import os
import subprocess


# ============================================================
# CONFIGURACIÓN
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ANALISIS_SCRIPT = os.path.join(
    BASE_DIR,
    "analisis_fantasy.py"
)

RANKING_SCRIPT = os.path.join(
    BASE_DIR,
    "ranking_fichajes.py"
)


# ============================================================
# UTILIDADES
# ============================================================

def limpiar_pantalla():
    """Limpia la consola de Windows/Linux."""
    os.system("cls" if os.name == "nt" else "clear")


def pausa():
    """Espera a que el usuario pulse Enter."""
    input("\nPulsa ENTER para continuar...")


def comprobar_archivo(ruta, nombre):
    """Comprueba que existe un script necesario."""
    if not os.path.isfile(ruta):
        print()
        print("=" * 60)
        print("ERROR")
        print("=" * 60)
        print(f"No se encuentra: {nombre}")
        print(f"Ruta esperada:")
        print(ruta)
        print()
        return False

    return True


def ejecutar_script(script, argumentos=None):
    """
    Ejecuta otro script Python utilizando el mismo intérprete
    con el que se ha ejecutado fantasy.py.
    """

    if argumentos is None:
        argumentos = []

    if not os.path.isfile(script):
        print(f"\nERROR: no existe el archivo:")
        print(script)
        return 1

    comando = [
        sys.executable,
        script
    ] + argumentos

    print()
    print("-" * 70)

    try:
        resultado = subprocess.run(
            comando,
            cwd=BASE_DIR
        )

        print("-" * 70)

        return resultado.returncode

    except KeyboardInterrupt:
        print("\n\nOperación cancelada por el usuario.")
        return 130

    except Exception as e:
        print()
        print(f"ERROR ejecutando el módulo: {e}")
        return 1


# ============================================================
# CABECERA
# ============================================================

def mostrar_cabecera():
    print("=" * 70)
    print("              FANTASY LALIGA - MOTOR PRINCIPAL")
    print("=" * 70)
    print()


# ============================================================
# ANÁLISIS DE JUGADOR
# ============================================================

def analizar_jugador(jugador):
    """Lanza el análisis individual."""

    if not comprobar_archivo(
        ANALISIS_SCRIPT,
        "analisis_fantasy.py"
    ):
        return

    print()
    print(f"Analizando jugador: {jugador}")
    print()

    ejecutar_script(
        ANALISIS_SCRIPT,
        ["jugador", jugador]
    )


# ============================================================
# PUJA
# ============================================================

def calcular_puja(jugador):
    """Calcula la puja recomendada."""

    if not comprobar_archivo(
        ANALISIS_SCRIPT,
        "analisis_fantasy.py"
    ):
        return

    print()
    print(f"Calculando puja recomendada para: {jugador}")
    print()

    ejecutar_script(
        ANALISIS_SCRIPT,
        ["puja", jugador]
    )


# ============================================================
# OPORTUNIDADES
# ============================================================

def mostrar_oportunidades():
    """Muestra el ranking de oportunidades."""

    if not comprobar_archivo(
        ANALISIS_SCRIPT,
        "analisis_fantasy.py"
    ):
        return

    print()
    print("GENERANDO RANKING DE OPORTUNIDADES")
    print()

    ejecutar_script(
        ANALISIS_SCRIPT,
        ["oportunidad"]
    )


# ============================================================
# RANKING DE FICHAJES
# ============================================================

def generar_ranking_fichajes():
    """Ejecuta el ranking avanzado de fichajes."""

    if not comprobar_archivo(
        RANKING_SCRIPT,
        "ranking_fichajes.py"
    ):
        return

    print()
    print("GENERANDO RANKING DE FICHAJES AVANZADO")
    print()

    ejecutar_script(
        RANKING_SCRIPT
    )


# ============================================================
# MENÚ
# ============================================================

def mostrar_menu():
    limpiar_pantalla()
    mostrar_cabecera()

    print("1. Analizar jugador")
    print("2. Calcular puja recomendada")
    print("3. Ranking de oportunidades")
    print("4. Ranking de fichajes avanzado")
    print("5. Salir")
    print()


def menu_interactivo():

    while True:

        mostrar_menu()

        opcion = input("Selecciona una opción: ").strip()

        # ----------------------------------------------------
        # 1. ANALIZAR JUGADOR
        # ----------------------------------------------------

        if opcion == "1":

            print()
            jugador = input(
                "Introduce nombre o ID del jugador: "
            ).strip()

            if not jugador:
                print("No has introducido ningún jugador.")
                pausa()
                continue

            analizar_jugador(jugador)
            pausa()

        # ----------------------------------------------------
        # 2. PUJA
        # ----------------------------------------------------

        elif opcion == "2":

            print()
            jugador = input(
                "Introduce nombre o ID del jugador: "
            ).strip()

            if not jugador:
                print("No has introducido ningún jugador.")
                pausa()
                continue

            calcular_puja(jugador)
            pausa()

        # ----------------------------------------------------
        # 3. OPORTUNIDADES
        # ----------------------------------------------------

        elif opcion == "3":

            mostrar_oportunidades()
            pausa()

        # ----------------------------------------------------
        # 4. RANKING DE FICHAJES
        # ----------------------------------------------------

        elif opcion == "4":

            generar_ranking_fichajes()
            pausa()

        # ----------------------------------------------------
        # 5. SALIR
        # ----------------------------------------------------

        elif opcion == "5":

            print()
            print("Saliendo del motor Fantasy LaLiga...")
            print()
            break

        else:

            print()
            print("Opción no válida.")
            pausa()


# ============================================================
# AYUDA
# ============================================================

def mostrar_ayuda():

    print("""
======================================================================
                 FANTASY LALIGA - MOTOR PRINCIPAL
======================================================================

USO:

    python fantasy.py

        Abre el menú interactivo.


ANÁLISIS DE JUGADOR:

    python fantasy.py jugador Pedri

    python fantasy.py jugador 133609


PUJA RECOMENDADA:

    python fantasy.py puja Pedri


RANKING DE OPORTUNIDADES:

    python fantasy.py oportunidad


RANKING DE FICHAJES:

    python fantasy.py fichajes


======================================================================
""")


# ============================================================
# PROGRAMA PRINCIPAL
# ============================================================

def main():

    argumentos = sys.argv[1:]

    # Sin argumentos -> menú
    if not argumentos:
        menu_interactivo()
        return

    comando = argumentos[0].lower()

    # --------------------------------------------------------
    # AYUDA
    # --------------------------------------------------------

    if comando in ("-h", "--help", "ayuda", "help"):
        mostrar_ayuda()
        return

    # --------------------------------------------------------
    # JUGADOR
    # --------------------------------------------------------

    if comando == "jugador":

        if len(argumentos) < 2:
            print()
            print("ERROR: falta el jugador.")
            print()
            print("Ejemplo:")
            print("python fantasy.py jugador Pedri")
            return

        jugador = " ".join(argumentos[1:])
        analizar_jugador(jugador)
        return

    # --------------------------------------------------------
    # PUJA
    # --------------------------------------------------------

    if comando == "puja":

        if len(argumentos) < 2:
            print()
            print("ERROR: falta el jugador.")
            print()
            print("Ejemplo:")
            print("python fantasy.py puja Pedri")
            return

        jugador = " ".join(argumentos[1:])
        calcular_puja(jugador)
        return

    # --------------------------------------------------------
    # OPORTUNIDAD
    # --------------------------------------------------------

    if comando in ("oportunidad", "oportunidades"):

        mostrar_oportunidades()
        return

    # --------------------------------------------------------
    # FICHAJES
    # --------------------------------------------------------

    if comando in (
        "fichajes",
        "ranking",
        "ranking_fichajes"
    ):

        generar_ranking_fichajes()
        return

    # --------------------------------------------------------
    # COMANDO DESCONOCIDO
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("COMANDO NO RECONOCIDO")
    print("=" * 70)
    print()
    print("Usa:")
    print()
    print("  python fantasy.py")
    print()
    print("o:")
    print()
    print("  python fantasy.py jugador Pedri")
    print("  python fantasy.py puja Pedri")
    print("  python fantasy.py oportunidad")
    print("  python fantasy.py fichajes")
    print()


# ============================================================
# ENTRADA
# ============================================================

if __name__ == "__main__":
    main()