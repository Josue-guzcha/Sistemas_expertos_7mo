from __future__ import annotations

import re
import sys
import unicodedata

VERSION = "v6.0 (Tableaux semánticos y ramas abiertas/cerradas)"

# ---------------------------------------------------------------------------
# Estructuras de datos
# ---------------------------------------------------------------------------
# Una fórmula es una tupla (inmutable, comparable y lista para los tableaux):
#   ("atom", "p")                 átomo
#   ("not",  f)                   ¬f
#   ("and",  (f1, f2, ...))       f1 ∧ f2 ∧ ...
#   ("or",   (f1, f2, ...))       f1 ∨ f2 ∨ ...
#   ("imp",  f1, f2)              f1 → f2
#   ("iff",  f1, f2)              f1 ↔ f2

# Base de conocimiento: "R1" -> {"original", "formula", "formula_texto", "conector", "tipo"}
reglas: dict[str, dict] = {}

# Tabla de átomos: letra -> significado (texto de la proposición simple)
atomos: dict[str, str] = {}

# Índice para reconocer la misma idea escrita igual: texto normalizado -> letra
indice_atomos: dict[str, str] = {}

LETRAS = list("pqrstuvwxyz")  # después de la 'z' sigue p1, q1, r1, ...

SIMBOLOS = {"and": " ∧ ", "or": " ∨ ", "imp": " → ", "iff": " ↔ "}
NOMBRES_CONECTOR = {
    "atom": "Atómica",
    "not": "Negación",
    "and": "Conjunción",
    "or": "Disyunción",
    "imp": "Condicional",
    "iff": "Bicondicional",
}

# Conectores del español (aceptan con o sin acento)
RE_BICONDICIONAL = re.compile(r"\s+s[ií]\s+y\s+s[oó]lo\s+s[ií]\s+")
RE_ENTONCES = re.compile(r"\s+entonces\s+")
RE_SI_INICIAL = re.compile(r"^s[ií]\s+")
RE_Y = re.compile(r"\s+y\s+")
RE_O = re.compile(r"\s+o\s+")
RE_NO = re.compile(r"\bno\b")


# ---------------------------------------------------------------------------
# Átomos globales
# ---------------------------------------------------------------------------
def quitar_acentos(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")


def siguiente_letra() -> str:
    i = len(atomos)
    if i < len(LETRAS):
        return LETRAS[i]
    return f"{LETRAS[i % len(LETRAS)]}{i // len(LETRAS)}"


def registrar_atomo(texto: str) -> tuple[str, bool]:
    """
    Devuelve (letra, es_nuevo). La misma proposición (ignorando mayúsculas,
    acentos y espacios extra) SIEMPRE recibe la misma letra.
    """
    clave = quitar_acentos(texto)
    if clave in indice_atomos:
        return indice_atomos[clave], False
    letra = siguiente_letra()
    indice_atomos[clave] = letra
    atomos[letra] = texto
    return letra, True


# ---------------------------------------------------------------------------
# Análisis del lenguaje natural -> fórmula
# ---------------------------------------------------------------------------
def normalizar(texto: str) -> str:
    t = texto.strip().lower()
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"\s*,\s*entonces\b", " entonces", t)  # "si llueve, entonces ..."
    return t.strip(" .;!?¡¿")


def _literal(t: str, apariciones: list) -> tuple:
    """Proposición simple, con o sin 'no' (cada 'no' invierte la negación)."""
    cantidad_no = len(RE_NO.findall(t))
    limpia = re.sub(r"\s+", " ", RE_NO.sub("", t)).strip(" ,")
    if not limpia:
        raise ValueError("hay una proposición vacía (revisa los conectores o un 'no' suelto)")
    letra, nuevo = registrar_atomo(limpia)
    negada = cantidad_no % 2 == 1
    apariciones.append({"texto": limpia, "letra": letra, "negada": negada, "nuevo": nuevo})
    nodo = ("atom", letra)
    return ("not", nodo) if negada else nodo


def _conjuncion(t: str, apariciones: list) -> tuple:
    partes = RE_Y.split(t)
    if len(partes) == 1:
        return _literal(t, apariciones)
    return ("and", tuple(_literal(p, apariciones) for p in partes))


def _disyuncion(t: str, apariciones: list) -> tuple:
    # La 'y' liga más fuerte que la 'o':  a y b o c  =  (a ∧ b) ∨ c
    partes = RE_O.split(t)
    if len(partes) == 1:
        return _conjuncion(t, apariciones)
    return ("or", tuple(_conjuncion(p, apariciones) for p in partes))


def _condicional(t: str, apariciones: list) -> tuple:
    partes = RE_ENTONCES.split(t)
    if len(partes) == 1:
        if RE_SI_INICIAL.match(t):
            raise ValueError("falta la palabra 'entonces' en el condicional")
        return _disyuncion(t, apariciones)
    if len(partes) > 2:
        raise ValueError("solo se permite un 'entonces' por regla")
    antecedente = RE_SI_INICIAL.sub("", partes[0])
    consecuente = partes[1]
    return ("imp", _disyuncion(antecedente, apariciones), _disyuncion(consecuente, apariciones))


def _bicondicional(t: str, apariciones: list) -> tuple:
    partes = RE_BICONDICIONAL.split(t)
    if len(partes) == 1:
        return _condicional(t, apariciones)
    if len(partes) > 2:
        raise ValueError("solo se permite un 'si y solo si' por regla")
    return ("iff", _condicional(partes[0], apariciones), _condicional(partes[1], apariciones))


def interpretar_oracion(texto: str) -> tuple[tuple, list[dict]]:
    """
    Convierte una oración en español en (fórmula, apariciones).
    Prioridad de menor a mayor ligadura:  ↔  →  ∨  ∧  ¬
    Si falla, deshace los átomos que se hubieran registrado a medias.
    """
    t = normalizar(texto)
    if not t:
        raise ValueError("el texto está vacío")

    respaldo = (dict(atomos), dict(indice_atomos))
    apariciones: list[dict] = []
    try:
        formula = _bicondicional(t, apariciones)
    except ValueError:
        atomos.clear()
        atomos.update(respaldo[0])
        indice_atomos.clear()
        indice_atomos.update(respaldo[1])
        raise
    return formula, apariciones


# ---------------------------------------------------------------------------
# Utilidades sobre fórmulas
# ---------------------------------------------------------------------------
def formula_a_texto(f: tuple) -> str:
    """Fórmula bien formada, con paréntesis cuando hace falta."""
    tipo = f[0]
    if tipo == "atom":
        return f[1]

    def envolver(h: tuple) -> str:
        s = formula_a_texto(h)
        return f"({s})" if h[0] in SIMBOLOS else s

    if tipo == "not":
        return "¬" + envolver(f[1])
    if tipo in ("and", "or"):
        return SIMBOLOS[tipo].join(envolver(h) for h in f[1])
    return envolver(f[1]) + SIMBOLOS[tipo] + envolver(f[2])  # imp / iff


def atomos_de(f: tuple) -> set[str]:
    tipo = f[0]
    if tipo == "atom":
        return {f[1]}
    if tipo == "not":
        return atomos_de(f[1])
    if tipo in ("and", "or"):
        res: set[str] = set()
        for h in f[1]:
            res |= atomos_de(h)
        return res
    return atomos_de(f[1]) | atomos_de(f[2])


def es_literal(f: tuple) -> bool:
    return f[0] == "atom" or (f[0] == "not" and f[1][0] == "atom")


def comparar_regla(formula: tuple) -> list[str]:
    """IDs de reglas con exactamente la misma fórmula (mismo conector incluido)."""
    return [id_regla for id_regla, r in reglas.items() if r["formula"] == formula]


# ---------------------------------------------------------------------------
# Almacenamiento
# ---------------------------------------------------------------------------
def generar_id() -> str:
    return f"R{len(reglas) + 1}"


def almacenar_regla(id_regla: str, original: str, formula: tuple) -> None:
    reglas[id_regla] = {
        "original": original,
        "formula": formula,
        "formula_texto": formula_a_texto(formula),
        "conector": NOMBRES_CONECTOR[formula[0]],
        "tipo": "Hecho" if es_literal(formula) else "Regla",
    }


# ---------------------------------------------------------------------------
# Acciones del menú
# ---------------------------------------------------------------------------
def agregar_reglas() -> None:
    print("\n" + "=" * 70)
    print(f"{'MÓDULO DE INGRESO DE REGLAS Y HECHOS':^70}")
    print("=" * 70)
    print("Ejemplos permitidos de escritura:")
    print("  - es de dia                                (hecho)")
    print("  - no voy a trabajar                        (hecho negado)")
    print("  - llueve y hace frio")
    print("  - estudio o trabajo")
    print("  - si llueve entonces no salgo")
    print("  - si llego temprano y hay asistencia entonces salgo temprano")
    print("  - apruebo si y solo si estudio")
    print("Prioridad: ↔ (menor), →, ∨, ∧ y ¬ (mayor). Ej.: 'a y b o c' = (a ∧ b) ∨ c")
    print("* Escribe 'salir' para regresar al menú principal.")
    print("-" * 70)

    while True:
        texto = input("\nIngresa la regla o el hecho: ").strip()
        if not texto:
            print("  [!] El texto no puede estar vacío.")
            continue
        if normalizar(texto) == "salir":
            print("\nSaliendo al menú principal...")
            break

        try:
            formula, apariciones = interpretar_oracion(texto)
        except ValueError as error:
            print(f"  [!] No se pudo interpretar: {error}.")
            continue

        iguales = comparar_regla(formula)
        id_regla = generar_id()
        almacenar_regla(id_regla, texto, formula)
        datos = reglas[id_regla]

        terminacion = "o" if datos["tipo"] == "Hecho" else "a"
        print(f"\n=== {datos['tipo']} {id_regla} almacenad{terminacion} con éxito ===")
        print(f"Texto original:   {texto}")
        print(f"Conector lógico:  {datos['conector']}")
        print(f"Fórmula:          {id_regla}: {datos['formula_texto']}")

        print(f"\nProposiciones simples detectadas ({len(apariciones)}):")
        for i, a in enumerate(apariciones, start=1):
            estado = f"negada → ¬{a['letra']}" if a["negada"] else "afirmada"
            origen = "átomo nuevo" if a["nuevo"] else f"misma idea que ya era '{a['letra']}'"
            print(f"  P{i}: '{a['texto']}'  =  {a['letra']}  ({estado}; {origen})")

        if iguales:
            print(f"\n>> ¡ATENCIÓN! Esta fórmula es IDÉNTICA a: {', '.join(iguales)}")
        print("-" * 50)


def _imprimir_tabla(titulo: str, encabezados: list[str], filas: list[list[str]]) -> None:
    anchos = [max(len(encabezados[i]), *(len(f[i]) for f in filas)) for i in range(len(encabezados))]
    total = sum(anchos) + 3 * (len(anchos) - 1)
    total = max(total, len(titulo))
    print("\n" + "=" * total)
    print(f"{titulo:^{total}}")
    print("=" * total)
    print(" | ".join(h.ljust(anchos[i]) for i, h in enumerate(encabezados)))
    print("-" * total)
    for fila in filas:
        print(" | ".join(c.ljust(anchos[i]) for i, c in enumerate(fila)))
    print("=" * total)


def mostrar_tabla_reglas() -> None:
    if not reglas:
        print("\n  [!] Aún no hay reglas ni hechos almacenados.\n")
        return
    filas = [
        [id_regla, d["tipo"], d["conector"], d["formula_texto"], d["original"]]
        for id_regla, d in reglas.items()
    ]
    _imprimir_tabla(
        "BASE DE CONOCIMIENTO: REGLAS Y FÓRMULAS",
        ["ID", "Tipo", "Conector", "Fórmula", "Texto original"],
        filas,
    )
    print("\nFórmulas:")
    for id_regla, d in reglas.items():
        print(f"  {id_regla}: {d['formula_texto']}")
    print(f"\nTotal: {len(reglas)} | Átomos distintos: {len(atomos)}\n")


def mostrar_tabla_atomos() -> None:
    if not atomos:
        print("\n  [!] Aún no hay átomos registrados.\n")
        return
    filas = []
    for letra, significado in atomos.items():
        donde = [i for i, d in reglas.items() if letra in atomos_de(d["formula"])]
        filas.append([letra, f'"{significado}"', ", ".join(donde)])
    _imprimir_tabla("TABLA DE ÁTOMOS", ["Letra", "Significado", "Aparece en"], filas)
    print()


# ---------------------------------------------------------------------------
# Tableaux semánticos (árboles de refutación)
# ---------------------------------------------------------------------------
MAX_NODOS = 3000


class Nodo:
    """Un nodo del árbol: una fórmula, sus hijos y, si es hoja, el estado de su rama."""

    def __init__(self, formula: tuple, etiqueta: str = "", padre: "Nodo | None" = None):
        self.formula = formula
        self.etiqueta = etiqueta   # "R1", "R2"... solo en las fórmulas originales
        self.padre = padre
        self.hijos: list[Nodo] = []
        self.aplicado = None       # número de paso en que se desarrolló (✓)
        self.regla = ""
        self.estado = None         # en las hojas: None (activa), "cerrada" o "abierta"
        self.motivo = ""           # por qué se cerró la rama
        self.numero = 0            # número de rama abierta


def neg(f: tuple) -> tuple:
    return ("not", f)


def info_literal(f: tuple) -> tuple[str, bool]:
    """(letra, es_positivo) de un átomo o un átomo negado."""
    return (f[1], True) if f[0] == "atom" else (f[1][1], False)


def regla_de_expansion(f: tuple):
    """
    Devuelve (nombre_regla, ramas) o None si f es un literal.
    'ramas' es una lista de listas de fórmulas: una sola lista = no ramifica (α);
    varias listas = ramifica (β).
    """
    t = f[0]
    if t == "and":
        return "∧", [list(f[1])]
    if t == "or":
        return "∨", [[h] for h in f[1]]
    if t == "imp":
        return "→", [[neg(f[1])], [f[2]]]
    if t == "iff":
        return "↔", [[f[1], f[2]], [neg(f[1]), neg(f[2])]]
    if t == "not":
        g = f[1]
        u = g[0]
        if u == "not":
            return "¬¬", [[g[1]]]
        if u == "or":
            return "¬∨", [[neg(h) for h in g[1]]]
        if u == "imp":
            return "¬→", [[g[1], neg(g[2])]]
        if u == "and":
            return "¬∧", [[neg(h)] for h in g[1]]
        if u == "iff":
            return "¬↔", [[g[1], neg(g[2])], [neg(g[1]), g[2]]]
    return None


def _camino(hoja: Nodo) -> list[Nodo]:
    camino = []
    n = hoja
    while n is not None:
        camino.append(n)
        n = n.padre
    return camino[::-1]


def _hojas(nodo: Nodo, solo_activas: bool = True) -> list[Nodo]:
    if not nodo.hijos:
        return [nodo] if (nodo.estado is None or not solo_activas) else []
    res: list[Nodo] = []
    for h in nodo.hijos:
        res += _hojas(h, solo_activas)
    return res


def _revisar_cierre(hoja: Nodo) -> bool:
    """Cierra la rama (✕) si contiene un átomo y su negación."""
    vistos: dict[str, bool] = {}
    for n in _camino(hoja):
        if es_literal(n.formula):
            atomo, positivo = info_literal(n.formula)
            if atomo in vistos and vistos[atomo] != positivo:
                hoja.estado = "cerrada"
                hoja.motivo = f"{atomo} y ¬{atomo}"
                return True
            vistos[atomo] = positivo
    return False


def _buscar_candidato(raiz: Nodo):
    """Primera fórmula sin desarrollar con ramas abiertas debajo; prefiere las que no ramifican."""
    pila = [raiz]
    primera_beta = None
    while pila:
        n = pila.pop()
        if n.aplicado is None and not es_literal(n.formula) and _hojas(n):
            _, ramas = regla_de_expansion(n.formula)
            if len(ramas) == 1:
                return n
            if primera_beta is None:
                primera_beta = n
        pila.extend(reversed(n.hijos))
    return primera_beta


def resolver_base(base: dict[str, tuple]) -> dict:
    """
    Tableau semántico de {"R1": fórmula, ...} suponiendo todas verdaderas.
    Devuelve {"raiz", "pasos", "abiertas", "n_cerradas"}.
    """
    raiz = ultimo = None
    nodos = 0
    for etiqueta, f in base.items():
        n = Nodo(f, etiqueta, ultimo)
        if ultimo is None:
            raiz = n
        else:
            ultimo.hijos.append(n)
        ultimo = n
        nodos += 1
    _revisar_cierre(ultimo)

    pasos = []
    while True:
        cand = _buscar_candidato(raiz)
        if cand is None:
            break
        regla, ramas = regla_de_expansion(cand.formula)
        cand.aplicado = len(pasos) + 1
        cand.regla = regla
        for hoja in _hojas(cand):
            for formulas in ramas:
                actual = hoja
                for f in formulas:
                    nuevo = Nodo(f, "", actual)
                    actual.hijos.append(nuevo)
                    actual = nuevo
                    nodos += 1
                _revisar_cierre(actual)
        if nodos > MAX_NODOS:
            raise RuntimeError("el tableau es demasiado grande para mostrarlo")
        pasos.append({"paso": cand.aplicado, "nodo": cand, "regla": regla, "ramas": len(ramas)})

    abiertas = []
    for k, hoja in enumerate(_hojas(raiz), start=1):
        hoja.estado = "abierta"
        hoja.numero = k
        valores = {}
        for n in _camino(hoja):
            if es_literal(n.formula):
                atomo, positivo = info_literal(n.formula)
                valores[atomo] = positivo
        abiertas.append({"numero": k, "valores": valores})
    n_cerradas = len(_hojas(raiz, solo_activas=False)) - len(abiertas)
    return {"raiz": raiz, "pasos": pasos, "abiertas": abiertas, "n_cerradas": n_cerradas}


def _texto_nodo(n: Nodo) -> str:
    t = formula_a_texto(n.formula)
    if n.etiqueta:
        t = f"{n.etiqueta}: {t}"
    if n.aplicado is not None:
        t += f"   ✓{n.aplicado}"
    return t


def dibujar_tableau(raiz: Nodo) -> list[str]:
    """Árbol en texto: las ramas abiertas y cerradas quedan marcadas al final de cada hoja."""
    lineas: list[str] = []

    def rec(n: Nodo, prefijo: str, conector: str) -> None:
        lineas.append(prefijo + conector + _texto_nodo(n))
        sig = prefijo + ("│   " if conector == "├── " else "    " if conector == "└── " else "")
        if not n.hijos:
            if n.estado == "cerrada":
                lineas.append(sig + f"✕ RAMA CERRADA ({n.motivo})")
            else:
                lineas.append(sig + f"○ RAMA ABIERTA #{n.numero}")
        elif len(n.hijos) == 1:
            rec(n.hijos[0], sig, "")
        else:
            for i, h in enumerate(n.hijos):
                rec(h, sig, "└── " if i == len(n.hijos) - 1 else "├── ")

    rec(raiz, "", "")
    return lineas


def resolver_tableau() -> None:
    if not reglas:
        print("\n  [!] Primero agrega reglas o hechos (opción 1).\n")
        return
    base = {i: d["formula"] for i, d in reglas.items()}
    try:
        res = resolver_base(base)
    except RuntimeError as error:
        print(f"\n  [!] {error}.\n")
        return

    print("\n" + "=" * 70)
    print(f"{'TABLEAUX SEMÁNTICOS (ÁRBOL DE REFUTACIÓN)':^70}")
    print("=" * 70)
    print("Se parte suponiendo que TODAS las reglas y hechos son verdaderos.")
    print("Leyenda: ✓n = fórmula desarrollada en el paso n | ✕ = rama cerrada | ○ = rama abierta\n")
    for linea in dibujar_tableau(res["raiz"]):
        print(linea)

    print("\n--- Pasos de desarrollo ---")
    if not res["pasos"]:
        print("  (no hubo que desarrollar ninguna fórmula: solo hay letras o letras negadas)")
    for p in res["pasos"]:
        n = p["nodo"]
        origen = n.etiqueta or "derivada"
        tipo = f"ramifica en {p['ramas']} ramas" if p["ramas"] > 1 else "no ramifica"
        print(f"  Paso {p['paso']}: {origen} «{formula_a_texto(n.formula)}» con la regla {p['regla']} ({tipo})")

    abiertas = res["abiertas"]
    print("\n--- Resultado ---")
    print(f"Ramas abiertas: {len(abiertas)} | Ramas cerradas: {res['n_cerradas']}")
    if abiertas:
        print("\nLa base de conocimiento es CONSISTENTE. Todas las reglas se cumplen")
        print("a la vez en las siguientes condiciones (una por rama abierta):")
        for a in abiertas:
            valores = a["valores"]
            texto = ", ".join(f"{x} = {'V' if valores[x] else 'F'}" for x in atomos if x in valores)
            libres = [x for x in atomos if x not in valores]
            extra = f"   (libres, pueden ser V o F: {', '.join(libres)})" if libres else ""
            print(f"  Rama {a['numero']}: {texto}{extra}")
    else:
        print("\nLa base de conocimiento es CONTRADICTORIA: todas las ramas se cerraron,")
        print("no existe ninguna asignación que haga verdaderas todas las reglas a la vez.")
    print()


# ---------------------------------------------------------------------------
# Menú principal
# ---------------------------------------------------------------------------
def main() -> None:
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass
    sys.setrecursionlimit(10000)

    print(f"--- {VERSION} ---")

    while True:
        print("\n=== MENÚ PRINCIPAL ===")
        print("1. Agregar reglas y hechos (modo continuo)")
        print("2. Mostrar reglas y fórmulas")
        print("3. Mostrar tabla de átomos")
        print("4. Resolver con tableaux semánticos")
        print("5. Salir del programa")

        opcion = input("\nSelecciona una opción (1-5): ").strip()

        if opcion == "1":
            agregar_reglas()
        elif opcion == "2":
            mostrar_tabla_reglas()
        elif opcion == "3":
            mostrar_tabla_atomos()
        elif opcion == "4":
            resolver_tableau()
        elif opcion == "5":
            print("\n¡Hasta luego!")
            break
        else:
            print("  [!] Opción inválida. Por favor ingresa 1, 2, 3, 4 o 5.\n")


if __name__ == "__main__":
    main()