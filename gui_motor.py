"""
Interfaz retro (tkinter) del motor de inferencia: barra lateral fija a la izquierda
y el contenido de cada sección a la derecha.
Necesita estar en la MISMA carpeta que motor_inferencia.py.
Ejecutar:  python gui_retro.py
"""
from __future__ import annotations

import sys
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

try:
    import motor_inferencia as m
except ModuleNotFoundError:  # por si guardaste el motor con otro nombre
    import proposiciones_gui as m

# ---------------------------------------------------------------------------
# Colores (estilo terminal ámbar)
# ---------------------------------------------------------------------------
BG = "#0d0800"
BG2 = "#160d00"
BARRA_ACTIVA = "#2e1c00"
AMBAR = "#ffa31a"
TENUE = "#b8760f"
BORDE = "#d98a00"
ROJO = "#ff5a36"
VERDE = "#9be34a"

EJEMPLO = [
    "si llueve entonces hay nubes",
    "no hay nubes",
    "si hace frio o llueve entonces me quedo en casa",
]

SECCIONES = [
    ("agregar", "Agregar regla"),
    ("reglas", "Reglas"),
    ("atomos", "Átomos"),
    ("tableau", "Tableau"),
    ("resultado", "Resultado"),
]

# Árbol del tableau: medidas y paleta (relleno, borde, texto)
ALTO_CAJA = 30
ALTO_NIVEL = 58
PAD_X = 10
SEP_X = 22
ESTILOS = {
    "original": ("#2e1c00", "#ffa31a", "#ffa31a"),
    "derivada": ("#160d00", "#a86a00", "#e0a030"),
    "cerrada": ("#2e0e00", "#ff5a36", "#ff7a5a"),
    "abierta": ("#142200", "#9be34a", "#9be34a"),
}


# ---------------------------------------------------------------------------
# Disposición del árbol (solo calcula posiciones)
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


def a_cajas(nodo) -> Caja:
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
# Elemento de la barra lateral
# ---------------------------------------------------------------------------
class ItemNav(tk.Frame):
    def __init__(self, padre, texto: str, comando, fuente):
        super().__init__(padre, bg=BG, cursor="hand2")
        self.texto = texto
        self.activo = False
        self.lbl = tk.Label(self, bg=BG, fg=TENUE, font=fuente, anchor="w", padx=14, pady=7)
        self.cnt = tk.Label(self, bg=BG, fg=TENUE, font=fuente, padx=12)
        self.lbl.pack(side="left", fill="x", expand=True)
        self.cnt.pack(side="right")
        for w in (self, self.lbl, self.cnt):
            w.bind("<Button-1>", lambda _e: comando())
            w.bind("<Enter>", lambda _e: self._pintar(True))
            w.bind("<Leave>", lambda _e: self._pintar(False))
        self._pintar(False)

    def _pintar(self, encima: bool) -> None:
        bg = BARRA_ACTIVA if (self.activo or encima) else BG
        fg = AMBAR if (self.activo or encima) else TENUE
        for w in (self, self.lbl, self.cnt):
            w.configure(bg=bg)
        self.lbl.configure(fg=fg, text=("▸ " if self.activo else "  ") + self.texto)
        self.cnt.configure(fg=fg)

    def activar(self, si: bool) -> None:
        self.activo = si
        self._pintar(False)

    def contador(self, n: int | None) -> None:
        self.cnt.configure(text="" if not n else str(n))


# ---------------------------------------------------------------------------
# Ventana principal
# ---------------------------------------------------------------------------
class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Motor de inferencia")
        self.geometry("1200x740")
        self.minsize(960, 600)
        self.configure(bg=BG)

        self.f_mono = tkfont.Font(family="Consolas", size=11)
        self.f_bold = tkfont.Font(family="Consolas", size=11, weight="bold")
        self.f_titulo = tkfont.Font(family="Consolas", size=16, weight="bold")
        self.f_logo = tkfont.Font(family="Consolas", size=15, weight="bold")
        self.f_chico = tkfont.Font(family="Consolas", size=9)
        self.f_arbol = tkfont.Font(family="Consolas", size=10)

        self.detalle_ultimo = ""
        self.paginas: dict[str, tk.Frame] = {}
        self.items: dict[str, ItemNav] = {}
        self.actual = SECCIONES[0][0]

        self._estilos()
        self._crear_barra_lateral()
        self._crear_contenido()
        self._crear_barra_inferior()
        self._atajos()

        self.refrescar()
        self.mostrar("agregar")
        self.estado("Escribe una regla o un hecho en español y presiona Enter.", "info")

    # ----------------------------------------------------------- construcción
    def _estilos(self) -> None:
        e = ttk.Style(self)
        e.theme_use("clam")
        e.configure("Retro.Treeview", background=BG2, fieldbackground=BG2, foreground=AMBAR,
                    rowheight=28, borderwidth=0, font=self.f_mono)
        e.configure("Retro.Treeview.Heading", background=BARRA_ACTIVA, foreground=AMBAR,
                    relief="flat", font=self.f_bold)
        e.map("Retro.Treeview", background=[("selected", AMBAR)], foreground=[("selected", "#000000")])
        e.map("Retro.Treeview.Heading", background=[("active", "#3f2700")])
        for nombre in ("TScrollbar", "Vertical.TScrollbar", "Horizontal.TScrollbar"):
            e.configure(nombre, background="#5a3a00", troughcolor=BG, arrowcolor=AMBAR,
                        bordercolor=BG, lightcolor="#5a3a00", darkcolor="#5a3a00", gripcount=0)
            e.map(nombre, background=[("active", AMBAR), ("pressed", AMBAR)])

    def _crear_barra_lateral(self) -> None:
        barra = tk.Frame(self, bg=BG, width=210, highlightthickness=0)
        barra.pack(side="left", fill="y")
        barra.pack_propagate(False)
        tk.Label(barra, text="MOTOR·INF", bg=BG, fg=AMBAR, font=self.f_logo, anchor="w",
                 padx=16, pady=(18)).pack(fill="x")
        tk.Label(barra, text="tableaux semánticos", bg=BG, fg=TENUE, font=self.f_chico, anchor="w",
                 padx=16).pack(fill="x", pady=(0, 14))
        for i, (clave, nombre) in enumerate(SECCIONES, start=1):
            item = ItemNav(barra, nombre, lambda c=clave: self.mostrar(c), self.f_mono)
            item.pack(fill="x")
            self.items[clave] = item
        version = getattr(m, "VERSION", "").split(" ")[0]
        tk.Label(barra, text=f"MotorOS {version}", bg=BG, fg=TENUE, font=self.f_chico).pack(
            side="bottom", pady=14)
        # línea vertical de separación
        tk.Frame(self, bg=BORDE, width=1).pack(side="left", fill="y")

    def _crear_contenido(self) -> None:
        self.contenido = tk.Frame(self, bg=BG)
        self.contenido.pack(side="left", fill="both", expand=True, padx=22, pady=(16, 6))
        self.lbl_titulo = tk.Label(self.contenido, bg=BG, fg=AMBAR, font=self.f_titulo, anchor="w")
        self.lbl_titulo.pack(fill="x")
        self.var_estado = tk.StringVar()
        self.lbl_estado = tk.Label(self.contenido, textvariable=self.var_estado, bg=BG, fg=TENUE,
                                   font=self.f_mono, anchor="w", justify="left", wraplength=900)
        self.lbl_estado.pack(fill="x", pady=(2, 10))

        self.pila = tk.Frame(self.contenido, bg=BG)
        self.pila.pack(fill="both", expand=True)
        self.pila.grid_rowconfigure(0, weight=1)
        self.pila.grid_columnconfigure(0, weight=1)

        self._pagina_agregar()
        self._pagina_tabla("reglas", [("id", "ID", 60), ("tipo", "Tipo", 80), ("conector", "Conector", 130),
                                      ("formula", "Fórmula", 260), ("texto", "Texto original", 520)])
        self._pagina_tabla("atomos", [("letra", "Letra", 80), ("significado", "Significado", 520),
                                      ("donde", "Aparece en", 380)])
        self._pagina_tableau()
        self._pagina_resultado()

    def _crear_barra_inferior(self) -> None:
        tk.Label(self.contenido,
                 text="[Enter] Agregar   [Ctrl+Z] Eliminar última   [Ctrl+R] Resolver   [Ctrl+1..5] Secciones",
                 bg=BG, fg=TENUE, font=self.f_chico, anchor="w").pack(fill="x", side="bottom", pady=(4, 2))
        tk.Frame(self.contenido, bg=BORDE, height=1).pack(fill="x", pady=(8, 0), side="bottom")

    def _nueva_pagina(self, clave: str) -> tk.Frame:
        f = tk.Frame(self.pila, bg=BG)
        f.grid(row=0, column=0, sticky="nsew")
        self.paginas[clave] = f
        return f

    def _tarjeta(self, padre) -> tk.Frame:
        return tk.Frame(padre, bg=BG, highlightthickness=1, highlightbackground=BORDE)

    def _boton(self, padre, texto: str, comando) -> tk.Button:
        return tk.Button(padre, text=texto, command=comando, bg=BG2, fg=AMBAR, font=self.f_mono,
                         activebackground=AMBAR, activeforeground="#000000", relief="flat", bd=0,
                         highlightthickness=1, highlightbackground=BORDE, padx=12, pady=5, cursor="hand2")

    # ---- página: agregar regla
    def _pagina_agregar(self) -> None:
        f = self._nueva_pagina("agregar")
        t = self._tarjeta(f)
        t.pack(fill="x", pady=(0, 14))
        tk.Label(t, text="Escribe una regla o un hecho en español:", bg=BG, fg=AMBAR,
                 font=self.f_mono, anchor="w").pack(fill="x", padx=14, pady=(12, 4))
        self.entrada = tk.Entry(t, bg=BG2, fg=AMBAR, insertbackground=AMBAR, relief="flat",
                                font=self.f_mono, highlightthickness=1, highlightbackground=BORDE,
                                highlightcolor=AMBAR)
        self.entrada.pack(fill="x", padx=14, ipady=7)
        self.entrada.bind("<Return>", lambda _e: self.agregar())
        tk.Label(t, text="Ej.:  es de dia  |  llueve y hace frio  |  si llueve entonces no salgo  |  "
                         "apruebo si y solo si estudio", bg=BG, fg=TENUE, font=self.f_chico,
                 anchor="w").pack(fill="x", padx=14, pady=(6, 8))
        fila = tk.Frame(t, bg=BG)
        fila.pack(fill="x", padx=14, pady=(0, 14))
        for texto, cmd in [("[Enter] Agregar", self.agregar),
                           ("[Ctrl+Z] Eliminar última regla", self.eliminar_ultima),
                           ("Cargar ejemplo", self.cargar_ejemplo),
                           ("Limpiar todo", self.limpiar)]:
            self._boton(fila, texto, cmd).pack(side="left", padx=(0, 8))

        u = self._tarjeta(f)
        u.pack(fill="x")
        tk.Label(u, text="ÚLTIMA REGLA AGREGADA", bg=BG, fg=TENUE, font=self.f_chico,
                 anchor="w").pack(fill="x", padx=14, pady=(10, 2))
        self.lbl_ultima = tk.Label(u, bg=BG, fg=AMBAR, font=self.f_titulo, anchor="w", justify="left",
                                   wraplength=860)
        self.lbl_ultima.pack(fill="x", padx=14)
        self.lbl_ultima_texto = tk.Label(u, bg=BG, fg=TENUE, font=self.f_mono, anchor="w",
                                         justify="left", wraplength=860)
        self.lbl_ultima_texto.pack(fill="x", padx=14, pady=(2, 4))
        self.lbl_detalle = tk.Label(u, bg=BG, fg=AMBAR, font=self.f_mono, anchor="w", justify="left",
                                    wraplength=860)
        self.lbl_detalle.pack(fill="x", padx=14, pady=(0, 12))

    # ---- páginas con tabla
    def _pagina_tabla(self, clave: str, columnas) -> None:
        f = self._nueva_pagina(clave)
        t = ttk.Treeview(f, columns=[c[0] for c in columnas], show="headings", style="Retro.Treeview")
        for k, titulo, ancho in columnas:
            t.heading(k, text=titulo)
            t.column(k, width=ancho, anchor="w")
        sb = ttk.Scrollbar(f, command=t.yview)
        t.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        t.pack(fill="both", expand=True)
        setattr(self, f"tabla_{clave}", t)

    # ---- página: tableau
    def _pagina_tableau(self) -> None:
        f = self._nueva_pagina("tableau")
        tk.Label(f, text="Arrastra con el mouse para moverte.  ✓n = paso en que se desarrolló la fórmula  |  "
                         "✕ rama cerrada  |  ○ rama abierta", bg=BG, fg=TENUE, font=self.f_chico,
                 anchor="w").pack(side="bottom", fill="x", pady=(4, 0))
        marco = tk.Frame(f, bg=BG, highlightthickness=1, highlightbackground=BORDE)
        marco.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(marco, bg=BG2, highlightthickness=0)
        sy = ttk.Scrollbar(marco, orient="vertical", command=self.canvas.yview)
        sx = ttk.Scrollbar(marco, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(xscrollcommand=sx.set, yscrollcommand=sy.set)
        sy.pack(side="right", fill="y")
        sx.pack(side="bottom", fill="x")
        self.canvas.pack(fill="both", expand=True)
        c = self.canvas
        c.bind("<ButtonPress-1>", lambda e: c.scan_mark(e.x, e.y))
        c.bind("<B1-Motion>", lambda e: c.scan_dragto(e.x, e.y, gain=1))
        c.bind("<MouseWheel>", lambda e: c.yview_scroll(-1 if e.delta > 0 else 1, "units"))
        c.bind("<Shift-MouseWheel>", lambda e: c.xview_scroll(-1 if e.delta > 0 else 1, "units"))
        c.bind("<Button-4>", lambda e: c.yview_scroll(-1, "units"))
        c.bind("<Button-5>", lambda e: c.yview_scroll(1, "units"))

    # ---- página: resultado
    def _pagina_resultado(self) -> None:
        f = self._nueva_pagina("resultado")
        self.texto = tk.Text(f, wrap="word", bg=BG2, fg=AMBAR, relief="flat", font=self.f_mono,
                             padx=14, pady=12, highlightthickness=1, highlightbackground=BORDE,
                             insertbackground=AMBAR, state="disabled")
        sb = ttk.Scrollbar(f, command=self.texto.yview)
        self.texto.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.texto.pack(fill="both", expand=True)
        self.texto.tag_configure("titulo", font=self.f_bold, foreground=AMBAR)
        self.texto.tag_configure("bien", font=self.f_titulo, foreground=VERDE)
        self.texto.tag_configure("mal", font=self.f_titulo, foreground=ROJO)
        self.texto.tag_configure("tenue", foreground=TENUE)

    # ----------------------------------------------------------------- atajos
    def _atajos(self) -> None:
        for tecla in ("z", "Z"):
            self.bind_all(f"<Control-{tecla}>", lambda _e: self.eliminar_ultima())
        for tecla in ("r", "R"):
            self.bind_all(f"<Control-{tecla}>", lambda _e: self.resolver())
        for i, (clave, _n) in enumerate(SECCIONES, start=1):
            self.bind_all(f"<Control-Key-{i}>", lambda _e, c=clave: self.mostrar(c))
        self.bind_all("<Control-Down>", lambda _e: self._mover(1))
        self.bind_all("<Control-Up>", lambda _e: self._mover(-1))

    def _mover(self, paso: int) -> None:
        claves = [c for c, _n in SECCIONES]
        self.mostrar(claves[(claves.index(self.actual) + paso) % len(claves)])

    # ------------------------------------------------------------- navegación
    def mostrar(self, clave: str) -> None:
        self.actual = clave
        self.paginas[clave].tkraise()
        for c, item in self.items.items():
            item.activar(c == clave)
        self.lbl_titulo.configure(text=dict(SECCIONES)[clave].upper())
        if clave == "agregar":
            self.entrada.focus_set()

    def estado(self, mensaje: str, tipo: str = "info") -> None:
        colores = {"info": TENUE, "ok": VERDE, "aviso": AMBAR, "error": ROJO}
        self.var_estado.set(mensaje)
        self.lbl_estado.configure(fg=colores.get(tipo, TENUE))

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

        lineas = []
        for i, a in enumerate(apariciones, start=1):
            estado = f"negada → ¬{a['letra']}" if a["negada"] else "afirmada"
            origen = "átomo nuevo" if a["nuevo"] else "misma idea que ya existía"
            lineas.append(f"P{i}: '{a['texto']}' = {a['letra']}  ({estado}; {origen})")
        self.detalle_ultimo = "Proposiciones detectadas:\n" + "\n".join(lineas)
        self.refrescar()

        mensaje = f"Agregada {id_regla}: {m.reglas[id_regla]['formula_texto']}"
        if iguales:
            mensaje += f"   ¡idéntica a {', '.join(iguales)}!"
        self.estado(mensaje, "aviso" if iguales else "ok")
        return True

    def eliminar_ultima(self) -> None:
        if not m.reglas:
            self.estado("No hay reglas que eliminar.", "error")
            return
        id_regla, datos = m.reglas.popitem()  # la última que se agregó
        usados: set[str] = set()
        for d in m.reglas.values():
            usados |= m.atomos_de(d["formula"])
        for letra in [l for l in m.atomos if l not in usados]:
            del m.atomos[letra]
        for clave in [k for k, l in m.indice_atomos.items() if l not in m.atomos]:
            del m.indice_atomos[clave]
        self.detalle_ultimo = ""
        self._limpiar_resultados()
        self.refrescar()
        self.estado(f"Se eliminó {id_regla}: {datos['formula_texto']}   («{datos['original']}»)", "aviso")

    def cargar_ejemplo(self) -> None:
        for frase in EJEMPLO:
            self.agregar(frase)
        self.estado("Ejemplo cargado. Presiona Ctrl+R para resolver.", "ok")

    def limpiar(self) -> None:
        m.reglas.clear()
        m.atomos.clear()
        m.indice_atomos.clear()
        self.detalle_ultimo = ""
        self._limpiar_resultados()
        self.refrescar()
        self.estado("Se borraron todas las reglas, los átomos y el tableau.", "info")

    def _limpiar_resultados(self) -> None:
        self.canvas.delete("all")
        self._escribir([("Aún no hay resultados. Presiona Ctrl+R para resolver.\n", "tenue")])

    def refrescar(self) -> None:
        for tabla in (self.tabla_reglas, self.tabla_atomos):
            tabla.delete(*tabla.get_children())
        for id_regla, d in m.reglas.items():
            self.tabla_reglas.insert("", "end", values=(
                id_regla, d["tipo"], d["conector"], d["formula_texto"], d["original"]))
        for letra, significado in m.atomos.items():
            donde = [i for i, d in m.reglas.items() if letra in m.atomos_de(d["formula"])]
            self.tabla_atomos.insert("", "end", values=(letra, f'"{significado}"', ", ".join(donde)))
        self.items["reglas"].contador(len(m.reglas))
        self.items["atomos"].contador(len(m.atomos))
        if m.reglas:
            id_regla, d = list(m.reglas.items())[-1]
            self.lbl_ultima.configure(text=f"{id_regla}: {d['formula_texto']}")
            self.lbl_ultima_texto.configure(text=f"«{d['original']}»")
        else:
            self.lbl_ultima.configure(text="(todavía no hay reglas)")
            self.lbl_ultima_texto.configure(text="")
        self.lbl_detalle.configure(text=self.detalle_ultimo)

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
        self.mostrar("tableau")
        self.estado(f"Tableau listo: {len(res['abiertas'])} rama(s) abierta(s), "
                    f"{res['n_cerradas']} cerrada(s). Detalle en la sección Resultado.", "ok")

    # ------------------------------------------------------------------ dibujo
    def dibujar(self, raiz) -> None:
        self.canvas.delete("all")
        arbol = a_cajas(raiz)
        medir(arbol, self.f_arbol.measure)
        margen = 30
        posicionar(arbol, margen + arbol.ancho_subarbol / 2, margen)

        pila = [arbol]
        while pila:
            c = pila.pop()
            for h in c.hijos:
                self.canvas.create_line(c.cx, c.y + ALTO_CAJA, h.cx, h.y, fill="#7a5200", width=1.5)
            pila.extend(c.hijos)
        pila = [arbol]
        while pila:
            c = pila.pop()
            relleno, borde, texto = ESTILOS[c.estilo]
            x1, x2 = c.cx - c.ancho_caja / 2, c.cx + c.ancho_caja / 2
            self.canvas.create_rectangle(x1, c.y, x2, c.y + ALTO_CAJA, fill=relleno, outline=borde, width=1.5)
            self.canvas.create_text(c.cx, c.y + ALTO_CAJA / 2, text=c.texto, fill=texto, font=self.f_arbol)
            pila.extend(c.hijos)

        x0, y0, x1, y1 = self.canvas.bbox("all")
        self.canvas.configure(scrollregion=(x0 - margen, y0 - margen, x1 + margen, y1 + margen))
        self.update_idletasks()
        total = (x1 - x0) + 2 * margen
        ancho_vista = max(self.canvas.winfo_width(), 1)
        self.canvas.xview_moveto(max(0.0, min(1.0, (arbol.cx - ancho_vista / 2 - (x0 - margen)) / total)))
        self.canvas.yview_moveto(0)

    # --------------------------------------------------------------- resultado
    def _escribir(self, trozos: list[tuple[str, str]]) -> None:
        self.texto.configure(state="normal")
        self.texto.delete("1.0", tk.END)
        for contenido, etiqueta in trozos:
            self.texto.insert(tk.END, contenido, etiqueta)
        self.texto.configure(state="disabled")

    def mostrar_resultado(self, res: dict) -> None:
        abiertas = res["abiertas"]
        t: list[tuple[str, str]] = [
            ("Se parte suponiendo que TODAS las reglas y hechos son verdaderos.\n", "tenue"),
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