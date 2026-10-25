"""
Interfaz gráfica (tkinter) del motor de inferencia.
Necesita estar en la MISMA carpeta que motor_inferencia.py.
Ejecutar:  python gui_motor.py
"""
from __future__ import annotations

import sys
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

import motor_inferencia as m

EJEMPLO = [
    "si llueve entonces hay nubes",
    "no hay nubes",
    "si hace frio o llueve entonces me quedo en casa",
]

# Medidas del dibujo del árbol
ALTO_CAJA = 30
ALTO_NIVEL = 58
PAD_X = 10
SEP_X = 22

ESTILOS = {  # relleno, borde, color del texto
    "original": ("#dbeafe", "#1d4ed8", "#0f172a"),
    "derivada": ("#f8fafc", "#64748b", "#0f172a"),
    "cerrada": ("#fee2e2", "#b91c1c", "#7f1d1d"),
    "abierta": ("#dcfce7", "#15803d", "#14532d"),
}


# ---------------------------------------------------------------------------
# Disposición del árbol (no depende de tkinter, solo calcula posiciones)
# ---------------------------------------------------------------------------
class Caja:
    def __init__(self, texto: str, estilo: str):
        self.texto = texto
        self.estilo = estilo
        self.hijos: list[Caja] = []
        self.ancho_caja = 0.0
        self.ancho_subarbol = 0.0
        self.cx = 0.0
        self.y = 0.0


def a_cajas(nodo: m.Nodo) -> Caja:
    """Convierte el árbol del tableau en cajas; cada hoja lleva una caja extra ✕ / ○."""
    texto = m.formula_a_texto(nodo.formula)
    if nodo.etiqueta:
        texto = f"{nodo.etiqueta}: {texto}"
    if nodo.aplicado is not None:
        texto += f"  ✓{nodo.aplicado}"
    caja = Caja(texto, "original" if nodo.etiqueta else "derivada")
    if nodo.hijos:
        caja.hijos = [a_cajas(h) for h in nodo.hijos]
    elif nodo.estado == "cerrada":
        caja.hijos = [Caja(f"✕ CERRADA ({nodo.motivo})", "cerrada")]
    else:
        caja.hijos = [Caja(f"○ ABIERTA #{nodo.numero}", "abierta")]
    return caja


def medir(caja: Caja, ancho_texto) -> float:
    caja.ancho_caja = ancho_texto(caja.texto) + 2 * PAD_X
    total = sum(medir(h, ancho_texto) for h in caja.hijos) + SEP_X * max(len(caja.hijos) - 1, 0)
    caja.ancho_subarbol = max(caja.ancho_caja, total)
    return caja.ancho_subarbol


def posicionar(caja: Caja, cx: float, y: float) -> None:
    caja.cx, caja.y = cx, y
    if not caja.hijos:
        return
    total = sum(h.ancho_subarbol for h in caja.hijos) + SEP_X * (len(caja.hijos) - 1)
    x = cx - total / 2
    for h in caja.hijos:
        posicionar(h, x + h.ancho_subarbol / 2, y + ALTO_NIVEL)
        x += h.ancho_subarbol + SEP_X


# ---------------------------------------------------------------------------
# Ventana principal
# ---------------------------------------------------------------------------
class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Motor de inferencia - Tableaux semánticos")
        self.geometry("1180x720")
        self.minsize(900, 560)
        self.fuente_arbol = tkfont.nametofont("TkDefaultFont").copy()
        self.fuente_arbol.configure(size=10)
        self._crear_widgets()
        self.estado("Escribe una regla o un hecho en español y presiona Enter.", "info")

    # ----------------------------------------------------------- construcción
    def _crear_widgets(self) -> None:
        barra = ttk.Frame(self, padding=(10, 10, 10, 4))
        barra.pack(fill="x")
        ttk.Label(barra, text="Regla o hecho:").pack(side="left")
        self.entrada = ttk.Entry(barra)
        self.entrada.pack(side="left", fill="x", expand=True, padx=8)
        self.entrada.bind("<Return>", lambda _e: self.agregar())
        self.entrada.focus_set()
        ttk.Button(barra, text="Agregar", command=self.agregar).pack(side="left", padx=2)
        ttk.Button(barra, text="Cargar ejemplo", command=self.cargar_ejemplo).pack(side="left", padx=2)
        ttk.Button(barra, text="Resolver (tableau)", command=self.resolver).pack(side="left", padx=2)
        ttk.Button(barra, text="Limpiar todo", command=self.limpiar).pack(side="left", padx=2)

        self.var_estado = tk.StringVar()
        self.lbl_estado = tk.Label(self, textvariable=self.var_estado, anchor="w", padx=12)
        self.lbl_estado.pack(fill="x")

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=8)

        # Pestaña 1: reglas y fórmulas
        self.tab_reglas = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_reglas, text="Reglas y fórmulas")
        self.tabla_reglas = self._crear_tabla(
            self.tab_reglas,
            [("id", "ID", 60), ("tipo", "Tipo", 70), ("conector", "Conector", 110),
             ("formula", "Fórmula", 230), ("texto", "Texto original", 560)],
        )

        # Pestaña 2: átomos
        self.tab_atomos = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_atomos, text="Tabla de átomos")
        self.tabla_atomos = self._crear_tabla(
            self.tab_atomos,
            [("letra", "Letra", 70), ("significado", "Significado", 480), ("donde", "Aparece en", 400)],
        )

        # Pestaña 3: tableau
        self.tab_tableau = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_tableau, text="Tableau")
        self._crear_canvas(self.tab_tableau)

        # Pestaña 4: resultado
        self.tab_resultado = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_resultado, text="Resultado")
        self.texto = tk.Text(self.tab_resultado, wrap="word", padx=12, pady=10, state="disabled")
        sb = ttk.Scrollbar(self.tab_resultado, command=self.texto.yview)
        self.texto.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.texto.pack(fill="both", expand=True)
        fuente_b = tkfont.nametofont("TkDefaultFont").copy()
        fuente_b.configure(size=12, weight="bold")
        self.texto.tag_configure("titulo", font=fuente_b)
        self.texto.tag_configure("bien", foreground="#15803d", font=fuente_b)
        self.texto.tag_configure("mal", foreground="#b91c1c", font=fuente_b)

    def _crear_tabla(self, padre, columnas) -> ttk.Treeview:
        tabla = ttk.Treeview(padre, columns=[c[0] for c in columnas], show="headings")
        for clave, titulo, ancho in columnas:
            tabla.heading(clave, text=titulo)
            tabla.column(clave, width=ancho, anchor="w")
        sb = ttk.Scrollbar(padre, command=tabla.yview)
        tabla.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tabla.pack(fill="both", expand=True)
        return tabla

    def _crear_canvas(self, padre) -> None:
        ttk.Label(
            padre,
            text="Arrastra con el mouse para moverte. Azul = reglas originales, "
                 "✓n = fórmula desarrollada en el paso n, rojo ✕ = rama cerrada, verde ○ = rama abierta.",
        ).pack(side="bottom", anchor="w", padx=6, pady=2)
        marco = ttk.Frame(padre)
        marco.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(marco, bg="white", highlightthickness=0)
        sb_y = ttk.Scrollbar(marco, orient="vertical", command=self.canvas.yview)
        sb_x = ttk.Scrollbar(marco, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(xscrollcommand=sb_x.set, yscrollcommand=sb_y.set)
        sb_y.pack(side="right", fill="y")
        sb_x.pack(side="bottom", fill="x")
        self.canvas.pack(fill="both", expand=True)

        self.canvas.bind("<ButtonPress-1>", lambda e: self.canvas.scan_mark(e.x, e.y))
        self.canvas.bind("<B1-Motion>", lambda e: self.canvas.scan_dragto(e.x, e.y, gain=1))
        self.canvas.bind("<MouseWheel>", lambda e: self.canvas.yview_scroll(-1 if e.delta > 0 else 1, "units"))
        self.canvas.bind("<Shift-MouseWheel>", lambda e: self.canvas.xview_scroll(-1 if e.delta > 0 else 1, "units"))
        self.canvas.bind("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))
        self.canvas.bind("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))

    # ----------------------------------------------------------------- estado
    def estado(self, mensaje: str, tipo: str = "info") -> None:
        colores = {"info": "#334155", "ok": "#15803d", "aviso": "#b45309", "error": "#b91c1c"}
        self.var_estado.set(mensaje)
        self.lbl_estado.configure(fg=colores.get(tipo, "#334155"))

    # ---------------------------------------------------------------- acciones
    def agregar(self, texto: str | None = None) -> bool:
        texto = (self.entrada.get() if texto is None else texto).strip()
        if not texto:
            self.estado("Escribe una regla o un hecho.", "error")
            return False
        try:
            formula, apariciones = m.interpretar_oracion(texto)
        except ValueError as error:
            self.estado(f"No se pudo interpretar: {error}.", "error")
            return False

        iguales = m.comparar_regla(formula)
        id_regla = m.generar_id()
        m.almacenar_regla(id_regla, texto, formula)
        self.entrada.delete(0, tk.END)
        self.refrescar()

        mensaje = f"{id_regla}: {m.reglas[id_regla]['formula_texto']}"
        nuevos = [a["letra"] for a in apariciones if a["nuevo"]]
        if nuevos:
            mensaje += f"   |   átomos nuevos: {', '.join(nuevos)}"
        if iguales:
            mensaje += f"   |   ¡idéntica a {', '.join(iguales)}!"
        self.estado(mensaje, "aviso" if iguales else "ok")
        return True

    def cargar_ejemplo(self) -> None:
        for frase in EJEMPLO:
            self.agregar(frase)
        self.estado("Ejemplo cargado. Presiona «Resolver (tableau)».", "ok")

    def limpiar(self) -> None:
        m.reglas.clear()
        m.atomos.clear()
        m.indice_atomos.clear()
        self.refrescar()
        self.canvas.delete("all")
        self._escribir([("", "")])
        self.estado("Se borraron todas las reglas, los átomos y el tableau.", "info")

    def refrescar(self) -> None:
        for tabla in (self.tabla_reglas, self.tabla_atomos):
            tabla.delete(*tabla.get_children())
        for id_regla, d in m.reglas.items():
            self.tabla_reglas.insert(
                "", "end", values=(id_regla, d["tipo"], d["conector"], d["formula_texto"], d["original"])
            )
        for letra, significado in m.atomos.items():
            donde = [i for i, d in m.reglas.items() if letra in m.atomos_de(d["formula"])]
            self.tabla_atomos.insert("", "end", values=(letra, f'"{significado}"', ", ".join(donde)))

    def resolver(self) -> None:
        if not m.reglas:
            self.estado("Primero agrega reglas o hechos.", "error")
            return
        base = {i: d["formula"] for i, d in m.reglas.items()}
        try:
            res = m.resolver_base(base)
        except RuntimeError as error:
            self.estado(f"{error}.", "error")
            return
        self.dibujar(res["raiz"])
        self.mostrar_resultado(res)
        self.notebook.select(self.tab_tableau)
        n_ab, n_ce = len(res["abiertas"]), res["n_cerradas"]
        self.estado(f"Tableau listo: {n_ab} rama(s) abierta(s), {n_ce} cerrada(s). Revisa la pestaña «Resultado».", "ok")

    # ---------------------------------------------------------------- dibujo
    def dibujar(self, raiz: m.Nodo) -> None:
        self.canvas.delete("all")
        arbol = a_cajas(raiz)
        medir(arbol, self.fuente_arbol.measure)
        margen = 30
        posicionar(arbol, margen + arbol.ancho_subarbol / 2, margen)

        pila = [arbol]
        while pila:
            c = pila.pop()
            for h in c.hijos:
                self.canvas.create_line(c.cx, c.y + ALTO_CAJA, h.cx, h.y, fill="#94a3b8", width=1.5)
            pila.extend(c.hijos)
        pila = [arbol]
        while pila:
            c = pila.pop()
            relleno, borde, texto = ESTILOS[c.estilo]
            x1, x2 = c.cx - c.ancho_caja / 2, c.cx + c.ancho_caja / 2
            self.canvas.create_rectangle(x1, c.y, x2, c.y + ALTO_CAJA, fill=relleno, outline=borde, width=1.5)
            self.canvas.create_text(c.cx, c.y + ALTO_CAJA / 2, text=c.texto, fill=texto, font=self.fuente_arbol)
            pila.extend(c.hijos)

        x0, y0, x1, y1 = self.canvas.bbox("all")
        self.canvas.configure(scrollregion=(x0 - margen, y0 - margen, x1 + margen, y1 + margen))
        self.update_idletasks()
        total = (x1 - x0) + 2 * margen
        ancho_vista = max(self.canvas.winfo_width(), 1)
        self.canvas.xview_moveto(max(0.0, min(1.0, (arbol.cx - ancho_vista / 2 - (x0 - margen)) / total)))
        self.canvas.yview_moveto(0)

    # ------------------------------------------------------------- resultado
    def _escribir(self, trozos: list[tuple[str, str]]) -> None:
        self.texto.configure(state="normal")
        self.texto.delete("1.0", tk.END)
        for contenido, etiqueta in trozos:
            self.texto.insert(tk.END, contenido, etiqueta)
        self.texto.configure(state="disabled")

    def mostrar_resultado(self, res: dict) -> None:
        abiertas = res["abiertas"]
        t: list[tuple[str, str]] = [
            ("Se parte suponiendo que TODAS las reglas y hechos son verdaderos.\n", ""),
            (f"Ramas abiertas: {len(abiertas)}   |   Ramas cerradas: {res['n_cerradas']}\n\n", ""),
        ]
        if abiertas:
            t.append(("La base de conocimiento es CONSISTENTE\n", "bien"))
            t.append(("Todas las reglas se cumplen a la vez en estas condiciones (una por rama abierta):\n\n", ""))
            for a in abiertas:
                v = a["valores"]
                texto = ", ".join(f"{x} = {'V' if v[x] else 'F'}" for x in m.atomos if x in v)
                libres = [x for x in m.atomos if x not in v]
                extra = f"     (libres, pueden ser V o F: {', '.join(libres)})" if libres else ""
                t.append((f"  Rama {a['numero']}:  {texto}{extra}\n", ""))
        else:
            t.append(("La base de conocimiento es CONTRADICTORIA\n", "mal"))
            t.append(("Todas las ramas se cerraron: no existe ninguna asignación que haga verdaderas "
                      "todas las reglas a la vez.\n", ""))

        t.append(("\nTabla de átomos\n", "titulo"))
        for letra, significado in m.atomos.items():
            t.append((f'  {letra} = "{significado}"\n', ""))

        t.append(("\nPasos de desarrollo\n", "titulo"))
        if not res["pasos"]:
            t.append(("  (no hubo que desarrollar ninguna fórmula: solo hay letras o letras negadas)\n", ""))
        for p in res["pasos"]:
            n = p["nodo"]
            tipo = f"ramifica en {p['ramas']} ramas" if p["ramas"] > 1 else "no ramifica"
            t.append((f"  Paso {p['paso']}: {n.etiqueta or 'derivada'} «{m.formula_a_texto(n.formula)}» "
                      f"con la regla {p['regla']} ({tipo})\n", ""))
        self._escribir(t)


def main() -> None:
    sys.setrecursionlimit(10000)
    App().mainloop()


if __name__ == "__main__":
    main()