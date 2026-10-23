from __future__ import annotations

import re
import sys

VERSION = "v4.2 (Múltiples Proposiciones y Conectores Compuestos)"

# Reglas almacenadas: "001" -> {"original", "proposiciones", "negadas", "conector", "esquema"}
reglas = {}

# Diccionario de proposiciones atómicas
indice_proposiciones = {}


# ---------------------------------------------------------------- análisis y conectores
def normalizar(texto: str) -> str:
    """Minúsculas y sin espacios al inicio y al final."""
    return texto.strip().lower()


def detectar_negacion(proposicion: str) -> tuple[str, bool]:
    """Devuelve (proposición sin 'no', negada). Usa el símbolo '¬' lógicamente."""
    patron = r"\bno\b"
    cantidad = len(re.findall(patron, proposicion))
    limpia = re.sub(patron, "", proposicion)
    limpia = re.sub(r"\s+", " ", limpia).strip()
    return limpia, cantidad % 2 == 1


def interpretar_oracion(texto: str) -> tuple[list[str], list[bool], str, str]:
    """
    Analiza textos con múltiples proposiciones y conectores compuestos o simples.
    Retorna: (proposiciones, negaciones, tipo_conector, esquema_logico)
    """
    t = normalizar(texto)
    t_limpio = re.sub(r"^si\s+", "", t)
    
    conector_principal = "Atómica / Negación"
    simbolo_principal = ""
    
    partes_antecedente = []
    partes_consecuente = []
    
    # 1. Bicondicional: "si y solo si"
    if "si y solo si" in t_limpio:
        partes = t_limpio.split("si y solo si")
        conector_principal = "Bicondicional"
        simbolo_principal = "↔"
        raw_proposiciones = [p.strip() for p in partes if p.strip()]
    
    # 2. Condicional: Contiene "entonces" (puede tener varias proposiciones antes y/o después)
    elif "entonces" in t_limpio:
        partes = t_limpio.split("entonces")
        conector_principal = "Condicional"
        simbolo_principal = "⇒"
        
        antecedente_str = partes[0].strip()
        consecuente_str = partes[1].strip() if len(partes) > 1 else ""
        
        # Desglosar antecedente por sub-conectores ('y' o 'o')
        if " y " in f" {antecedente_str} ":
            partes_antecedente = [p.strip() for p in antecedente_str.split(" y ") if p.strip()]
        elif " o " in f" {antecedente_str} ":
            partes_antecedente = [p.strip() for p in antecedente_str.split(" o ") if p.strip()]
        else:
            partes_antecedente = [antecedente_str] if antecedente_str else []
            
        # Desglosar consecuente por sub-conectores ('y' o 'o')
        if " y " in f" {consecuente_str} ":
            partes_consecuente = [p.strip() for p in consecuente_str.split(" y ") if p.strip()]
        elif " o " in f" {consecuente_str} ":
            partes_consecuente = [p.strip() for p in consecuente_str.split(" o ") if p.strip()]
        else:
            partes_consecuente = [consecuente_str] if consecuente_str else []
            
        raw_proposiciones = partes_antecedente + partes_consecuente

    # 3. Conjunción general multiple ("y")
    elif " y " in f" {t_limpio} ":
        raw_proposiciones = [p.strip() for p in t_limpio.split(" y ") if p.strip()]
        conector_principal = "Conjunción"
        simbolo_principal = "∧"
        
    # 4. Disyunción general multiple ("o")
    elif " o " in f" {t_limpio} ":
        raw_proposiciones = [p.strip() for p in t_limpio.split(" o ") if p.strip()]
        conector_principal = "Disyunción"
        simbolo_principal = "∨"
        
    # 5. Proposición atómica simple
    else:
        raw_proposiciones = [t_limpio] if t_limpio else []
        conector_principal = "Negación / Atómica"
        simbolo_principal = ""

    proposiciones = []
    negadas = []
    
    for p in raw_proposiciones:
        p_limpia, negada = detectar_negacion(p)
        if p_limpia:
            proposiciones.append(p_limpia)
            negadas.append(negada)

    # Asignación dinámica de variables lógicas (p, q, r, s, t, ...)
    variables_base = ["p", "q", "r", "s", "t", "u", "v", "w"]
    vars_asignadas = []
    for idx, neg in enumerate(negadas):
        v_letra = variables_base[idx % len(variables_base)]
        if idx >= len(variables_base):
            v_letra = f"p{idx+1}"
        v_str = f"¬{v_letra}" if neg else v_letra
        vars_asignadas.append(v_str)

    # Construir esquema lógico formal adaptado a múltiples proposiciones
    if len(proposiciones) == 1:
        esquema = vars_asignadas[0]
    elif conector_principal == "Condicional":
        num_ant = len(partes_antecedente) if partes_antecedente else 1
        ant_vars = vars_asignadas[:num_ant]
        cons_vars = vars_asignadas[num_ant:]
        
        # Operador interno del antecedente
        op_ant = " ∧ " if any(" y " in f" {p} " for p in [partes[0]]) else (" ∨ " if any(" o " in f" {p} " for p in [partes[0]]) else " ∧ ")
        ant_str = op_ant.join(ant_vars)
        if len(ant_vars) > 1:
            ant_str = f"({ant_str})"
            
        # Operador interno del consecuente
        consecuente_str_raw = partes[1].strip() if len(partes) > 1 else ""
        op_cons = " ∧ " if " y " in f" {consecuente_str_raw} " else (" ∨ " if " o " in f" {consecuente_str_raw} " else " ∧ ")
        cons_str = op_cons.join(cons_vars)
        if len(cons_vars) > 1:
            cons_str = f"({cons_str})"
            
        esquema = f"{ant_str} ⇒ {cons_str}"
    else:
        op = f" {simbolo_principal} "
        esquema = op.join(vars_asignadas)

    return proposiciones, negadas, conector_principal, esquema


# ------------------------------------------------------------ comparadores
def comparar_proposicion(proposicion: str, negada: bool) -> list[dict]:
    coincidencias = []
    for c in indice_proposiciones.get(proposicion, []):
        coincidencias.append({**c, "misma_negacion": c["negada"] == negada})
    return coincidencias


def comparar_regla(proposiciones: list[str], negadas: list[bool]) -> list[str]:
    firma = list(zip(proposiciones, negadas))
    return [
        id_regla
        for id_regla, r in reglas.items()
        if list(zip(r["proposiciones"], r["negadas"])) == firma
    ]


# ------------------------------------------------------------ almacenamiento
def generar_id() -> str:
    return f"{len(reglas) + 1:03d}"


def almacenar_regla(id_regla, original, proposiciones, negadas, conector, esquema):
    reglas[id_regla] = {
        "original": original,
        "proposiciones": proposiciones,
        "negadas": negadas,
        "conector": conector,
        "esquema": esquema,
    }
    for pos, (p, n) in enumerate(zip(proposiciones, negadas), start=1):
        indice_proposiciones.setdefault(p, []).append(
            {"regla": id_regla, "posicion": pos, "negada": n}
        )


# ----------------------------------------------------------------- acciones del menú
def agregar_reglas() -> None:
    print("\n" + "=" * 65)
    print(f"{'MÓDULO DE INGRESO DE REGLAS (Múltiples Proposiciones)':^65}")
    print("=" * 65)
    print("Ejemplos permitidos de escritura:")
    print("  - llueve y hace frio")
    print("  - estudio o trabajo")
    print("  - si llueve entonces no hace frio")
    print("  - si quiero llegar temprano y tener asistencia entonces salgo mas temprano")
    print("  - apruebo el examen si y solo si estudio")
    print("  * Escribe 'salir' cuando desees regresar al menú principal.")
    print("-" * 65)
    
    while True:
        texto = input("\nIngresa el texto o proposición: ").strip()
        if not texto:
            print("  [!] El texto no puede estar vacío.")
            continue

        if normalizar(texto) == "salir":
            print("\nSaliendo al menú principal...")
            break

        proposiciones, negadas, conector, esquema = interpretar_oracion(texto)
        if not proposiciones:
            print("  [!] No se pudieron extraer proposiciones válidas.")
            continue

        reglas_iguales = comparar_regla(proposiciones, negadas)
        coincidencias = [
            comparar_proposicion(p, n) for p, n in zip(proposiciones, negadas)
        ]

        id_regla = generar_id()
        almacenar_regla(id_regla, texto, proposiciones, negadas, conector, esquema)

        print(f"\n=== Regla {id_regla} almacenada con éxito ===")
        print(f"Texto original:    {texto}")
        print(f"Conector lógico:   {conector}")
        print(f"Esquema generado:  {esquema}")
        print(f"Proposiciones ({len(proposiciones)} detectadas): {proposiciones}")
        
        print("\nDetalle de proposiciones:")
        for i, (p, n, coincide) in enumerate(
            zip(proposiciones, negadas, coincidencias), start=1
        ):
            estado = f"¬{p}" if n else p
            print(f"  P{i}: '{p}' -> {'NEGADA (' + estado + ')' if n else 'afirmada'}")
            if not coincide:
                print("      (proposición nueva)")
            for c in coincide:
                if c["misma_negacion"]:
                    print(f"      = Igual a P{c['posicion']} de la regla {c['regla']}")
                else:
                    print(f"      ~ Mismo enunciado que P{c['posicion']} de la regla {c['regla']}, pero con negación opuesta")

        if reglas_iguales:
            print(f"\n>> ¡ATENCIÓN! La regla completa es IDÉNTICA a la regla: {', '.join(reglas_iguales)}")
        print("-" * 50)


def mostrar_tabla_reglas() -> None:
    print("\n" + "=" * 105)
    print(f"{'TABLA DE REGLAS Y ESQUEMAS LÓGICOS':^105}")
    print("=" * 105)
    
    if not reglas:
        print("  [!] Aún no hay reglas almacenadas en el sistema.\n")
        print("=" * 105)
        return

    print(f"{'ID':<6} | {'Conector':<18} | {'Esquema Lógico':<22} | {'Texto Original':<50}")
    print("-" * 105)

    for id_regla, datos in reglas.items():
        conector = datos["conector"]
        esquema = datos["esquema"]
        original = datos["original"]
        print(f"{id_regla:<6} | {conector:<18} | {esquema:<22} | {original:<50}")

    print("=" * 105)
    print(f"Total de reglas: {len(reglas)} | Proposiciones atómicas distintas: {len(indice_proposiciones)}\n")


# ----------------------------------------------------------------- menú principal
def main() -> None:
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass

    print(f"--- {VERSION} ---")

    while True:
        print("\n=== MENÚ PRINCIPAL ===")
        print("1. Agregar nuevas reglas / proposiciones (Modo continuo)")
        print("2. Mostrar tabla de reglas y esquemas lógicos")
        print("3. Salir del programa")
        
        opcion = input("\nSelecciona una opción (1-3): ").strip()

        if opcion == "1":
            agregar_reglas()
        elif opcion == "2":
            mostrar_tabla_reglas()
        elif opcion == "3":
            print("\n¡Hasta luego!")
            break
        else:
            print("  [!] Opción inválida. Por favor ingresa 1, 2 o 3.\n")


if __name__ == "__main__":
    main()