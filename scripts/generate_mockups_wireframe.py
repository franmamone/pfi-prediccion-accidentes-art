"""Genera mockups esquemáticos (pre-app) a partir del layout actual de Prevex.

No copia capturas ni datos reales: usa placeholders, bloques grises y tipografía
simple para documentar el diseño previo al prototipo.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "docs" / "figures" / "mockups"

W, H = 1280, 780
SIDE = 200
TOP = 52

# Paleta wireframe (gris + acento azul suave)
BG = (245, 247, 250)
PANEL = (255, 255, 255)
STROKE = (180, 188, 198)
STROKE_SOFT = (210, 216, 224)
TEXT = (55, 65, 80)
TEXT_MUTED = (120, 130, 145)
ACCENT = (70, 120, 200)
ACCENT_SOFT = (210, 225, 245)
BADGE_RED = (200, 100, 100)
BADGE_ORANGE = (210, 150, 80)
BADGE_GREEN = (100, 160, 120)
BADGE_BLUE = (100, 140, 190)
SIDEBAR_BG = (250, 251, 252)
PLACEHOLDER = (230, 234, 240)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\calibri.ttf",
    ]
    bold_c = [
        r"C:\Windows\Fonts\segoeuib.ttf",
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\calibrib.ttf",
    ]
    paths = bold_c if bold else candidates
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


F14 = None
F12 = None
F11 = None
F16 = None
F20 = None
F10 = None


def init_fonts() -> None:
    global F14, F12, F11, F16, F20, F10
    F10 = font(10)
    F11 = font(11)
    F12 = font(12)
    F14 = font(14)
    F16 = font(16, bold=True)
    F20 = font(20, bold=True)


def rr(draw: ImageDraw.ImageDraw, box, fill=None, outline=STROKE, width=1, radius=8):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def text(draw, xy, s, f=None, fill=TEXT):
    draw.text(xy, s, font=f or F12, fill=fill)


def shell(active: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # Sidebar
    d.rectangle([0, 0, SIDE, H], fill=SIDEBAR_BG)
    d.line([(SIDE, 0), (SIDE, H)], fill=STROKE, width=1)
    text(d, (18, 18), "PREVEX", F16, ACCENT)
    text(d, (18, 42), "mockup", F10, TEXT_MUTED)

    nav = [
        ("OPERACIÓN", [("Priorización", "prio"), ("Agenda", "agenda")]),
        ("ANÁLISIS", [("Estadísticas", "stats")]),
        ("SISTEMA", [("Perfil", "perfil")]),
    ]
    y = 78
    for group, items in nav:
        text(d, (18, y), group, F10, TEXT_MUTED)
        y += 22
        for label, key in items:
            box = (12, y - 4, SIDE - 12, y + 26)
            if key == active:
                rr(d, box, fill=ACCENT_SOFT, outline=ACCENT, radius=6)
                text(d, (24, y + 2), label, F12, ACCENT)
            else:
                text(d, (24, y + 2), label, F12, TEXT)
            y += 34
        y += 10

    # Topbar
    d.rectangle([SIDE, 0, W, TOP], fill=PANEL)
    d.line([(SIDE, TOP), (W, TOP)], fill=STROKE, width=1)
    text(d, (SIDE + 18, 16), "☰", F14, TEXT_MUTED)
    text(d, (W - 210, 16), "Tema  ·  Usuario  ·  Salir", F11, TEXT_MUTED)

    return img, d


def content_box():
    return SIDE + 20, TOP + 16, W - 20, H - 16


def draw_login() -> Image.Image:
    img = Image.new("RGB", (W, H), (236, 242, 248))
    d = ImageDraw.Draw(img)
    # subtle circles
    for r in (180, 280, 400):
        d.ellipse([W // 2 - r, H // 2 - r - 40, W // 2 + r, H // 2 + r - 40], outline=STROKE_SOFT)
    cw, ch = 360, 380
    x0, y0 = (W - cw) // 2, (H - ch) // 2 - 10
    rr(d, (x0, y0, x0 + cw, y0 + ch), fill=PANEL, outline=STROKE, radius=14)
    text(d, (x0 + cw // 2 - 40, y0 + 36), "PREVEX", F20, ACCENT)
    text(d, (x0 + cw // 2 - 70, y0 + 66), "Acceso al sistema", F12, TEXT_MUTED)
    # fields
    for i, lab in enumerate(["Email", "Contraseña"]):
        fy = y0 + 110 + i * 78
        text(d, (x0 + 36, fy), lab, F11, TEXT_MUTED)
        rr(d, (x0 + 36, fy + 22, x0 + cw - 36, fy + 58), fill=PLACEHOLDER, outline=STROKE, radius=8)
        text(d, (x0 + 48, fy + 32), "••••••••" if i else "usuario@empresa.com", F11, TEXT_MUTED)
    rr(d, (x0 + 36, y0 + 290, x0 + cw - 36, y0 + 334), fill=ACCENT, outline=ACCENT, radius=8)
    text(d, (x0 + cw // 2 - 30, y0 + 302), "Ingresar", F14, (255, 255, 255))
    return img


def draw_priorizacion() -> Image.Image:
    img, d = shell("prio")
    x0, y0, x1, y1 = content_box()
    text(d, (x0, y0), "Priorización", F20)
    # horizon toggle
    rr(d, (x1 - 170, y0, x1 - 95, y0 + 28), fill=PLACEHOLDER, outline=STROKE, radius=6)
    text(d, (x1 - 155, y0 + 6), "Mes", F11, TEXT_MUTED)
    rr(d, (x1 - 90, y0, x1, y0 + 28), fill=ACCENT, outline=ACCENT, radius=6)
    text(d, (x1 - 78, y0 + 6), "Trimestre", F11, (255, 255, 255))

    # filters
    fy = y0 + 48
    rr(d, (x0, fy, x1, fy + 64), fill=PANEL, outline=STROKE, radius=10)
    labels = ["Riesgo", "Actividad", "Estado", "PRS", "Buscar…"]
    fw = (x1 - x0 - 40) // 5
    for i, lab in enumerate(labels):
        fx = x0 + 12 + i * (fw + 4)
        text(d, (fx, fy + 8), lab, F10, TEXT_MUTED)
        rr(d, (fx, fy + 26, fx + fw - 8, fy + 52), fill=PLACEHOLDER, outline=STROKE_SOFT, radius=6)

    # table
    ty = fy + 80
    rr(d, (x0, ty, x1, y1 - 40), fill=PANEL, outline=STROKE, radius=10)
    cols = ["#", "Establec.", "Efectividad", "Riesgo", "Actividad", "Estado", "Acción"]
    widths = [40, 120, 160, 90, 220, 110, 90]
    cx = x0 + 12
    for lab, w in zip(cols, widths):
        text(d, (cx, ty + 12), lab, F10, TEXT_MUTED)
        cx += w
    d.line([(x0 + 8, ty + 34), (x1 - 8, ty + 34)], fill=STROKE_SOFT)

    risks = [BADGE_RED, BADGE_RED, BADGE_ORANGE, BADGE_ORANGE, BADGE_GREEN, BADGE_GREEN, TEXT_MUTED]
    risk_lab = ["Crítico", "Crítico", "Alto", "Alto", "Medio", "Medio", "Bajo"]
    estados = ["Pendiente", "Pendiente", "Programada", "Pendiente", "Realizada", "Pendiente", "Pendiente"]
    est_col = [TEXT_MUTED, TEXT_MUTED, BADGE_BLUE, TEXT_MUTED, BADGE_GREEN, TEXT_MUTED, TEXT_MUTED]

    for r in range(7):
        ry = ty + 44 + r * 42
        text(d, (x0 + 18, ry + 10), str(r + 1), F11, TEXT_MUTED)
        text(d, (x0 + 58, ry + 10), f"EST-{100 + r:03d}", F11, TEXT)
        # fake bar
        bar_x = x0 + 190
        rr(d, (bar_x, ry + 14, bar_x + 90, ry + 24), fill=PLACEHOLDER, outline=None, radius=4)
        rr(d, (bar_x, ry + 14, bar_x + 50 + (r % 4) * 8, ry + 24), fill=ACCENT_SOFT, outline=None, radius=4)
        # risk badge
        bx = x0 + 370
        rr(d, (bx, ry + 8, bx + 72, ry + 28), fill=risks[r], outline=None, radius=10)
        text(d, (bx + 8, ry + 11), risk_lab[r], F10, (255, 255, 255))
        text(d, (x0 + 460, ry + 10), ["Servicios", "Industria", "Comercio", "Construcción", "Agro", "Salud", "Otros"][r], F11, TEXT)
        ex = x0 + 700
        rr(d, (ex, ry + 8, ex + 88, ry + 28), fill=PLACEHOLDER, outline=est_col[r], radius=10)
        text(d, (ex + 8, ry + 11), estados[r], F10, TEXT)
        text(d, (x0 + 820, ry + 10), "[cal] [ver]", F10, ACCENT)
        if r < 6:
            d.line([(x0 + 8, ry + 40), (x1 - 8, ry + 40)], fill=STROKE_SOFT)

    text(d, (x0, y1 - 28), "1–50 de N   ·   « Anterior   Página 1 / K   Siguiente »", F11, TEXT_MUTED)
    return img


def draw_detalle() -> Image.Image:
    img, d = shell("prio")
    x0, y0, x1, y1 = content_box()
    text(d, (x0, y0), "← Priorización", F11, TEXT_MUTED)
    text(d, (x0, y0 + 26), "Establecimiento", F20)
    text(d, (x0, y0 + 54), "EST-###  ·  identificador anonimizado", F11, TEXT_MUTED)

    # badges
    badges = [("Crítico", BADGE_RED), ("Predictivo", BADGE_BLUE), ("Acierto ##%", BADGE_GREEN)]
    bx = x0
    for lab, col in badges:
        rr(d, (bx, y0 + 78, bx + 90, y0 + 100), fill=col, outline=None, radius=10)
        text(d, (bx + 10, y0 + 81), lab, F10, (255, 255, 255))
        bx += 100
    rr(d, (x1 - 150, y0 + 74, x1, y0 + 104), fill=ACCENT, outline=ACCENT, radius=8)
    text(d, (x1 - 138, y0 + 82), "Programar visita", F11, (255, 255, 255))

    # tabs
    tabs = ["Historial", "Resumen IA", "Ficha", "Factores", "Cambios"]
    ty = y0 + 120
    for i, t in enumerate(tabs):
        tx = x0 + i * 110
        if i == 1:
            text(d, (tx, ty), t, F12, ACCENT)
            d.line([(tx, ty + 20), (tx + 70, ty + 20)], fill=ACCENT, width=2)
        else:
            text(d, (tx, ty), t, F12, TEXT_MUTED)

    # content panel
    py = ty + 36
    rr(d, (x0, py, x1, y1), fill=PANEL, outline=STROKE, radius=10)
    rr(d, (x0 + 16, py + 16, x0 + 160, py + 44), fill=ACCENT, outline=ACCENT, radius=6)
    text(d, (x0 + 28, py + 22), "Generar resumen", F11, (255, 255, 255))

    # fake text blocks
    blocks = [
        ("Resumen ejecutivo", 4),
        ("Perfil de riesgo", 3),
        ("Incumplimientos a verificar", 3),
        ("Focos para la próxima visita", 3),
    ]
    by = py + 64
    for title, lines in blocks:
        text(d, (x0 + 20, by), title.upper(), F12, ACCENT)
        by += 22
        for _ in range(lines):
            rr(d, (x0 + 20, by, x1 - 40, by + 10), fill=PLACEHOLDER, outline=None, radius=3)
            by += 16
        by += 12
    return img


def draw_agenda() -> Image.Image:
    img, d = shell("agenda")
    x0, y0, x1, y1 = content_box()
    text(d, (x0, y0), "Agenda de visitas", F20)
    text(d, (x0, y0 + 30), "Vista calendario · período de ejemplo", F11, TEXT_MUTED)

    # view toggle
    for i, lab in enumerate(["Día", "Semana", "Mes"]):
        bx = x1 - 200 + i * 66
        fill = ACCENT if lab == "Mes" else PLACEHOLDER
        fg = (255, 255, 255) if lab == "Mes" else TEXT_MUTED
        rr(d, (bx, y0, bx + 60, y0 + 28), fill=fill, outline=STROKE if lab != "Mes" else ACCENT, radius=6)
        text(d, (bx + 14, y0 + 6), lab, F11, fg)

    # toolbar
    ty = y0 + 56
    text(d, (x0, ty + 4), "‹   Hoy   ›     Mes de ejemplo", F12, TEXT)
    chips = ["Programadas", "Realizadas", "Canceladas", "Todas"]
    cx = x0 + 280
    for i, c in enumerate(chips):
        fill = ACCENT if i == 0 else PLACEHOLDER
        fg = (255, 255, 255) if i == 0 else TEXT
        rr(d, (cx, ty, cx + 88, ty + 26), fill=fill, outline=STROKE_SOFT, radius=12)
        text(d, (cx + 10, ty + 5), c[:10], F10, fg)
        cx += 94

    # calendar grid
    gy = ty + 44
    days = ["LUN", "MAR", "MIÉ", "JUE", "VIE", "SÁB", "DOM"]
    cell_w = (x1 - x0) // 7
    cell_h = (y1 - gy) // 6
    for i, day in enumerate(days):
        text(d, (x0 + i * cell_w + cell_w // 2 - 12, gy), day, F10, TEXT_MUTED)
    gy += 22
    n = 1
    for row in range(5):
        for col in range(7):
            cx0 = x0 + col * cell_w
            cy0 = gy + row * cell_h
            rr(d, (cx0 + 2, cy0 + 2, cx0 + cell_w - 4, cy0 + cell_h - 4), fill=PANEL, outline=STROKE_SOFT, radius=6)
            if n <= 31:
                text(d, (cx0 + 8, cy0 + 6), str(n), F10, TEXT_MUTED)
                # a few fake events
                if n in (5, 12, 18, 23):
                    rr(
                        d,
                        (cx0 + 8, cy0 + 28, cx0 + cell_w - 10, cy0 + 48),
                        fill=ACCENT_SOFT,
                        outline=ACCENT,
                        radius=4,
                    )
                    text(d, (cx0 + 12, cy0 + 32), "Visita EST-…", F10, ACCENT)
                n += 1
    return img


def draw_estadisticas() -> Image.Image:
    img, d = shell("stats")
    x0, y0, x1, y1 = content_box()
    text(d, (x0, y0), "Estadísticas", F20)
    rr(d, (x1 - 170, y0, x1 - 95, y0 + 28), fill=PLACEHOLDER, outline=STROKE, radius=6)
    text(d, (x1 - 155, y0 + 6), "Mes", F11, TEXT_MUTED)
    rr(d, (x1 - 90, y0, x1, y0 + 28), fill=ACCENT, outline=ACCENT, radius=6)
    text(d, (x1 - 78, y0 + 6), "Trimestre", F11, (255, 255, 255))

    tabs = ["Cobertura", "SHAP", "Composición", "Sectores"]
    ty = y0 + 48
    for i, t in enumerate(tabs):
        tx = x0 + i * 130
        if i == 2:
            text(d, (tx, ty), t, F12, ACCENT)
            d.line([(tx, ty + 18), (tx + 90, ty + 18)], fill=ACCENT, width=2)
        else:
            text(d, (tx, ty), t, F12, TEXT_MUTED)

    # 2x2 cards
    gap = 14
    cw = (x1 - x0 - gap) // 2
    ch = (y1 - ty - 40) // 2
    titles = [
        ("Distribución por riesgo", "donut"),
        ("Acierto histórico", "bars"),
        ("Visita reciente", "donut"),
        ("Antigüedad de visitas", "bars"),
    ]
    for i, (title, kind) in enumerate(titles):
        col, row = i % 2, i // 2
        cx0 = x0 + col * (cw + gap)
        cy0 = ty + 36 + row * (ch + gap)
        rr(d, (cx0, cy0, cx0 + cw, cy0 + ch), fill=PANEL, outline=STROKE, radius=10)
        text(d, (cx0 + 14, cy0 + 12), title, F12, TEXT)
        text(d, (cx0 + 14, cy0 + 32), "Esquema ilustrativo", F10, TEXT_MUTED)
        if kind == "donut":
            ox, oy = cx0 + cw // 2, cy0 + ch // 2 + 10
            r = min(cw, ch) // 4
            d.ellipse([ox - r, oy - r, ox + r, oy + r], outline=ACCENT, width=14)
            d.ellipse([ox - r + 18, oy - r + 18, ox + r - 18, oy + r - 18], fill=PANEL, outline=STROKE_SOFT)
            text(d, (ox - 10, oy - 8), "N", F14, TEXT_MUTED)
        else:
            for j in range(5):
                by = cy0 + 58 + j * 28
                text(d, (cx0 + 16, by), f"Cat. {j + 1}", F10, TEXT_MUTED)
                rr(d, (cx0 + 80, by + 2, cx0 + cw - 24, by + 14), fill=PLACEHOLDER, outline=None, radius=3)
                rr(
                    d,
                    (cx0 + 80, by + 2, cx0 + 80 + 40 + j * 28, by + 14),
                    fill=ACCENT_SOFT,
                    outline=None,
                    radius=3,
                )
    return img


def draw_perfil() -> Image.Image:
    img, d = shell("perfil")
    x0, y0, x1, y1 = content_box()
    # hero
    rr(d, (x0, y0, x1, y0 + 100), fill=PANEL, outline=STROKE, radius=12)
    rr(d, (x0 + 20, y0 + 20, x0 + 80, y0 + 80), fill=ACCENT_SOFT, outline=ACCENT, radius=12)
    text(d, (x0 + 40, y0 + 38), "U", F20, ACCENT)
    text(d, (x0 + 100, y0 + 28), "Nombre de usuario", F16)
    rr(d, (x0 + 100, y0 + 56, x0 + 160, y0 + 76), fill=ACCENT, outline=None, radius=8)
    text(d, (x0 + 112, y0 + 58), "Rol", F10, (255, 255, 255))
    text(d, (x0 + 170, y0 + 58), "usuario@empresa.com", F11, TEXT_MUTED)

    gap = 16
    cw = (x1 - x0 - gap) // 2
    cy0 = y0 + 120
    for i, (title, fields, btn) in enumerate(
        [
            ("Datos de la cuenta", ["Email", "Rol", "Nombre visible"], "Guardar perfil"),
            ("Cambiar contraseña", ["Contraseña actual", "Nueva", "Confirmar"], "Actualizar contraseña"),
        ]
    ):
        cx0 = x0 + i * (cw + gap)
        rr(d, (cx0, cy0, cx0 + cw, y1), fill=PANEL, outline=STROKE, radius=12)
        text(d, (cx0 + 20, cy0 + 18), title, F14)
        text(d, (cx0 + 20, cy0 + 42), "Campos de ejemplo (sin datos reales)", F10, TEXT_MUTED)
        fy = cy0 + 70
        for lab in fields:
            text(d, (cx0 + 20, fy), lab, F11, TEXT_MUTED)
            rr(d, (cx0 + 20, fy + 20, cx0 + cw - 20, fy + 52), fill=PLACEHOLDER, outline=STROKE_SOFT, radius=8)
            fy += 70
        rr(d, (cx0 + 20, y1 - 56, cx0 + cw - 20, y1 - 24), fill=ACCENT, outline=ACCENT, radius=8)
        text(d, (cx0 + 40, y1 - 48), btn, F12, (255, 255, 255))
    return img


def main() -> None:
    init_fonts()
    OUT.mkdir(parents=True, exist_ok=True)
    outputs = {
        "login.png": draw_login,
        "riesgo.png": draw_priorizacion,
        "detalle.png": draw_detalle,
        "agenda.png": draw_agenda,
        "estadisticas.png": draw_estadisticas,
        "perfil.png": draw_perfil,
    }
    for name, fn in outputs.items():
        path = OUT / name
        fn().save(path, "PNG", optimize=True)
        print("wrote", path.relative_to(REPO), path.stat().st_size)


if __name__ == "__main__":
    main()
