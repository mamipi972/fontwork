# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Miguel
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
Moteur de rendu du greffon « Texte Fontwork » pour GIMP 3.

Indépendant de GIMP : n'utilise que pycairo + Pango (via PyGObject).
  1. Le texte est converti en contours vectoriels (Pango -> chemin cairo).
  2. Chaque contour est aplati puis subdivisé en petits segments.
  3. Chaque point est déformé par une fonction de forme (arc, vague, entonnoir...).
  4. Le résultat est dessiné avec relief 3D, ombre, contour et remplissage.
"""
import math
import cairo

# --------------------------------------------------------------------------
# Paramètres
# --------------------------------------------------------------------------
DEFAULTS = {
    "text": "Fontwork",
    "font": "Sans-serif Bold",    # nom de police GIMP (famille + style)
    "size": 120,                   # taille en pixels
    "spacing": 0.0,                # espacement des lettres (px)
    "line_spacing": 1.0,           # interligne (facteur)
    "align": "center",             # left / center / right
    "width": 100.0,                # étirement horizontal (%)
    "shape": "arc_haut",
    "amount": 50.0,                # intensité de la déformation (-100..100)
    "freq": 1.0,                   # nombre de vagues
    "phase": 0.0,                  # décalage des vagues (degrés)
    "arc": 180.0,                  # angle de l'arc / de la spirale (degrés)
    "rotation": 0.0,               # rotation finale (degrés)
    "fill_mode": "gradient",       # none / solid / gradient
    "fill1": [1.0, 0.55, 0.0, 1.0],
    "fill2": [1.0, 0.85, 0.1, 1.0],
    "grad_angle": 90.0,            # 90 = de haut en bas
    "outline_w": 3.0,
    "outline_col": [0.35, 0.15, 0.0, 1.0],
    "shadow": True,
    "shadow_dx": 8.0,
    "shadow_dy": 8.0,
    "shadow_blur": 6.0,
    "shadow_col": [0.0, 0.0, 0.0, 0.5],
    "extrude": 0.0,                # profondeur du relief (px)
    "extrude_angle": 45.0,
    "extrude_col": [0.55, 0.25, 0.05, 1.0],
}

# (clé, libellé, paramètres utiles)
SHAPES = [
    ("droit",       "Droit",        ()),
    ("arc_haut",    "Arc haut",     ("arc",)),
    ("arc_bas",     "Arc bas",      ("arc",)),
    ("cercle",      "Cercle",       ()),
    ("spirale",     "Spirale",      ("amount", "arc")),
    ("vague",       "Vague",        ("amount", "freq", "phase")),
    ("ondulation",  "Ondulation",   ("amount", "freq", "phase")),
    ("gonfle",      "Gonflé",       ("amount",)),
    ("pince",       "Pincé",        ("amount",)),
    ("dome",        "Dôme",         ("amount",)),
    ("cuvette",     "Cuvette",      ("amount",)),
    ("entonnoir",   "Entonnoir",    ("amount",)),
    ("pyramide",    "Pyramide",     ("amount",)),
    ("perspective", "Perspective",  ("amount",)),
    ("inclinaison", "Montée",       ("amount",)),
    ("chevron",     "Chevron",      ("amount",)),
]
SHAPE_KEYS = [s[0] for s in SHAPES]
SHAPE_PARAMS = {s[0]: set(s[2]) for s in SHAPES}

GEOMETRY_KEYS = ("text", "font", "size", "spacing", "line_spacing", "align",
                 "width", "shape", "amount", "freq", "phase", "arc", "rotation")


def normalize(p):
    """Complète un dictionnaire de paramètres avec les valeurs par défaut."""
    out = dict(DEFAULTS)
    if p:
        out.update({k: v for k, v in p.items() if k in DEFAULTS or k.startswith("_")})
    if out["shape"] not in SHAPE_KEYS:
        out["shape"] = "droit"
    return out


# --------------------------------------------------------------------------
# Texte -> contours
# --------------------------------------------------------------------------
def _pango_layout_path(ctx, p):
    """Ajoute le chemin du texte au contexte. Renvoie (ink, logical) en px."""
    import gi
    gi.require_version("Pango", "1.0")
    gi.require_version("PangoCairo", "1.0")
    from gi.repository import Pango, PangoCairo

    layout = PangoCairo.create_layout(ctx)
    desc = Pango.FontDescription.from_string(p["font"] or "Sans")
    desc.set_absolute_size(max(1.0, float(p["size"])) * Pango.SCALE)
    layout.set_font_description(desc)
    layout.set_text(p["text"] or " ", -1)
    layout.set_alignment({"left": Pango.Alignment.LEFT,
                          "right": Pango.Alignment.RIGHT}.get(p["align"], Pango.Alignment.CENTER))
    if abs(p["line_spacing"] - 1.0) > 1e-3:
        layout.set_line_spacing(float(p["line_spacing"]))
    attrs = Pango.AttrList()
    if p["spacing"]:
        attrs.insert(Pango.attr_letter_spacing_new(int(p["spacing"] * Pango.SCALE)))
    layout.set_attributes(attrs)
    PangoCairo.layout_path(ctx, layout)
    ink, logical = layout.get_pixel_extents()
    return ((ink.x, ink.y, ink.width, ink.height),
            (logical.x, logical.y, logical.width, logical.height))


# Remplaçable (tests hors GIMP)
layout_path = _pango_layout_path


def _text_polygons(p):
    # Surface d'enregistrement non bornée : sinon les glyphes situés hors de
    # la surface seraient ignorés par Pango/cairo.
    surf = cairo.RecordingSurface(cairo.CONTENT_COLOR_ALPHA, None)
    ctx = cairo.Context(surf)
    ctx.set_tolerance(0.05)
    ink, logical = layout_path(ctx, p)
    polys = flatten(ctx)
    if ink is None:
        if not polys:
            return [], (0, 0, 1, 1), logical
        xs = [x for q in polys for x, _ in q]
        ink = (min(xs), 0, max(xs) - min(xs), 0)
    return polys, ink, logical


def flatten(ctx):
    """Chemin courant du contexte -> liste de polygones."""
    polys, cur = [], None
    for kind, pts in ctx.copy_path_flat():
        if kind == cairo.PATH_MOVE_TO:
            cur = [(pts[0], pts[1])]
            polys.append(cur)
        elif kind == cairo.PATH_LINE_TO and cur is not None:
            cur.append((pts[0], pts[1]))
    return [q for q in polys if len(q) > 2]


def _subdivide(poly, maxlen):
    out = []
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        out.append((x0, y0))
        d = math.hypot(x1 - x0, y1 - y0)
        if d > maxlen:
            k = int(d / maxlen)
            for j in range(1, k + 1):
                t = j / (k + 1)
                out.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))
    return out


# --------------------------------------------------------------------------
# Formes (u, v normalisés 0..1 -> x, y)
# --------------------------------------------------------------------------
def _make_warp(p, w, h, nchars):
    W = w * max(5.0, p["width"]) / 100.0
    H = h
    a = max(-100.0, min(100.0, p["amount"])) / 100.0
    f = p["freq"]
    ph = math.radians(p["phase"])
    s = p["shape"]
    sin, cos, pi = math.sin, math.cos, math.pi

    if s == "vague":
        return lambda u, v: (u * W, v * H + a * H * 0.6 * sin(2 * pi * f * u + ph))
    if s == "ondulation":
        def warp(u, v):
            o = a * H * 0.4 * sin(2 * pi * f * u + ph)
            return u * W, o + v * (H - 2 * o)
        return warp
    if s == "gonfle":
        def warp(u, v):
            b = a * H * 0.5 * sin(pi * u)
            return u * W, -b + v * (H + 2 * b)
        return warp
    if s == "pince":
        def warp(u, v):
            b = min(a * H * 0.45 * sin(pi * u), 0.45 * H)
            return u * W, b + v * (H - 2 * b)
        return warp
    if s == "dome":
        def warp(u, v):
            b = a * H * 0.8 * sin(pi * u)
            return u * W, -b + v * (H + b)
        return warp
    if s == "cuvette":
        def warp(u, v):
            b = a * H * 0.8 * sin(pi * u)
            return u * W, v * (H + b)
        return warp
    if s == "entonnoir":
        k = max(-0.95, min(0.95, a))
        return lambda u, v: (W / 2 + (u - 0.5) * W * (1 - k * v), v * H)
    if s == "pyramide":
        k = max(-0.95, min(0.95, a))
        return lambda u, v: (W / 2 + (u - 0.5) * W * (1 - k * (1 - v)), v * H)
    if s == "perspective":
        k = max(-0.9, min(0.9, a))
        def warp(u, v):
            sh = k * H * (u - 0.5)
            return u * W, -sh + v * (H + 2 * sh)
        return warp
    if s == "inclinaison":
        return lambda u, v: (u * W, v * H - a * H * 1.5 * (u - 0.5))
    if s == "chevron":
        return lambda u, v: (u * W, v * H - a * H * 0.6 * (1 - abs(2 * u - 1)))
    if s in ("arc_haut", "cercle"):
        if s == "cercle":
            n = max(1, nchars)
            sweep = 2 * pi * n / (n + 1.0)
        else:
            sweep = math.radians(max(5.0, min(360.0, p["arc"])))
        R = W / sweep
        def warp(u, v):
            t = -pi / 2 + (u - 0.5) * sweep
            r = R + (1 - v) * H
            return r * cos(t), r * sin(t)
        return warp
    if s == "arc_bas":
        sweep = math.radians(max(5.0, min(360.0, p["arc"])))
        R = W / sweep
        def warp(u, v):
            t = pi / 2 - (u - 0.5) * sweep
            r = R + v * H
            return r * cos(t), r * sin(t)
        return warp
    if s == "spirale":
        # spirale d'Archimède : le rayon diminue d'un « pas » à chaque tour
        total = math.radians(max(30.0, p["arc"]))
        pitch = H * max(0.8, 1.1 + 0.6 * a)
        k = pitch / (2 * pi)
        # texte court : on limite l'angle pour garder un rayon intérieur >= r_min
        r_min = H * 0.3
        t_max = (-r_min + math.sqrt(r_min * r_min + 2 * k * W)) / k
        total = min(total, t_max)
        R0 = (W + k * total * total / 2) / total   # longueur de la ligne de base ~ W
        def warp(u, v):
            t = u * total
            r = R0 - k * t
            rr = r + (1 - v) * H
            return rr * cos(t - pi / 2), rr * sin(t - pi / 2)
        return warp
    # droit
    return lambda u, v: (u * W, v * H)


def geometry(p):
    """Renvoie (polygones déformés, bbox=(x0, y0, x1, y1))."""
    p = normalize(p)
    polys, ink, logical = _text_polygons(p)
    if not polys:
        return [], (0.0, 0.0, 1.0, 1.0)
    x0 = ink[0]
    w = max(1.0, ink[2])
    y0 = logical[1]
    h = max(1.0, logical[3])
    nchars = len("".join((p["text"] or "").split()))
    warp = _make_warp(p, w, h, nchars)
    maxlen = max(0.5, h / 40.0)

    out = []
    for poly in polys:
        pts = _subdivide(poly, maxlen)
        out.append([warp((x - x0) / w, (y - y0) / h) for x, y in pts])

    bbox = _bbox(out)
    rot = math.radians(p["rotation"])
    if abs(rot) > 1e-6:
        cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
        c, s = math.cos(rot), math.sin(rot)
        out = [[(cx + (x - cx) * c - (y - cy) * s, cy + (x - cx) * s + (y - cy) * c)
                for x, y in poly] for poly in out]
        bbox = _bbox(out)
    return out, bbox


def _bbox(polys):
    xs = [x for poly in polys for x, _ in poly]
    ys = [y for poly in polys for _, y in poly]
    return min(xs), min(ys), max(xs), max(ys)


# --------------------------------------------------------------------------
# Rendu
# --------------------------------------------------------------------------
def _stroke_width(p):
    if p["outline_w"] <= 0 or p["outline_col"][3] <= 0:
        return 0.0
    # contour extérieur (le remplissage recouvre la moitié intérieure)
    return p["outline_w"] * 2 if p["fill_mode"] != "none" else p["outline_w"]


def extents(bbox, p):
    """Zone totale occupée (contour, relief, ombre compris), en px pleine taille."""
    p = normalize(p)
    half = _stroke_width(p) / 2 + 1
    ea = math.radians(p["extrude_angle"])
    ex, ey = p["extrude"] * math.cos(ea), p["extrude"] * math.sin(ea)
    x0 = bbox[0] - half + min(0, ex)
    y0 = bbox[1] - half + min(0, ey)
    x1 = bbox[2] + half + max(0, ex)
    y1 = bbox[3] + half + max(0, ey)
    if p["shadow"] and p["shadow_col"][3] > 0:
        b = p["shadow_blur"] * 2 + 2
        x0 = min(x0, x0 + p["shadow_dx"] - b)
        y0 = min(y0, y0 + p["shadow_dy"] - b)
        x1 = max(x1, x1 + p["shadow_dx"] + b)
        y1 = max(y1, y1 + p["shadow_dy"] + b)
    return math.floor(x0), math.floor(y0), math.ceil(x1), math.ceil(y1)


def _darken(c, f):
    return [c[0] * f, c[1] * f, c[2] * f, c[3]]


def _lerp(c1, c2, t):
    return [c1[i] + (c2[i] - c1[i]) * t for i in range(4)]


def _trace(ctx, polys):
    ctx.new_path()
    for poly in polys:
        ctx.move_to(*poly[0])
        for pt in poly[1:]:
            ctx.line_to(*pt)
        ctx.close_path()


def _fill_source(p, bbox):
    if p["fill_mode"] == "solid":
        return cairo.SolidPattern(*p["fill1"])
    cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
    t = math.radians(p["grad_angle"])
    dx, dy = math.cos(t), math.sin(t)
    d = abs((bbox[2] - bbox[0]) / 2 * dx) + abs((bbox[3] - bbox[1]) / 2 * dy)
    g = cairo.LinearGradient(cx - dx * d, cy - dy * d, cx + dx * d, cy + dy * d)
    g.add_color_stop_rgba(0, *p["fill1"])
    g.add_color_stop_rgba(1, *p["fill2"])
    return g


def _draw_body(ctx, path, p, bbox, scale, mono=None):
    """Relief 3D + contour + remplissage. mono = couleur unique (silhouette)."""
    sw = _stroke_width(p)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    ctx.set_line_width(sw)
    ctx.set_fill_rule(cairo.FILL_RULE_WINDING)

    # Relief : empilement de copies décalées, de l'arrière vers l'avant
    depth = p["extrude"]
    if depth > 0:
        ea = math.radians(p["extrude_angle"])
        ex, ey = depth * math.cos(ea), depth * math.sin(ea)
        steps = int(min(400, max(1, math.ceil(depth * scale))))
        front, back = p["extrude_col"], _darken(p["extrude_col"], 0.45)
        for i in range(steps, 0, -1):
            t = i / steps
            ctx.save()
            ctx.translate(ex * t, ey * t)
            ctx.new_path()
            ctx.append_path(path)
            ctx.set_source_rgba(*(mono or _lerp(front, back, t)))
            if sw > 0:
                ctx.fill_preserve()
                ctx.stroke()
            else:
                ctx.fill()
            ctx.restore()

    # Contour
    if sw > 0:
        ctx.new_path()
        ctx.append_path(path)
        ctx.set_source_rgba(*(mono or p["outline_col"]))
        ctx.stroke()

    # Remplissage
    if p["fill_mode"] != "none":
        ctx.new_path()
        ctx.append_path(path)
        if mono:
            ctx.set_source_rgba(*mono)
        else:
            ctx.set_source(_fill_source(p, bbox))
        ctx.fill()


def _blur(src, radius):
    """Flou approché rapide (réduction + moyenne 3x3 + agrandissement)."""
    if radius < 1:
        return src
    w, h = src.get_width(), src.get_height()
    k = max(1.0, radius / 1.5)
    sw, sh = max(1, int(w / k)), max(1, int(h / k))
    small = cairo.ImageSurface(cairo.FORMAT_ARGB32, sw, sh)
    c = cairo.Context(small)
    c.scale(sw / w, sh / h)
    c.set_source_surface(src, 0, 0)
    c.get_source().set_filter(cairo.FILTER_GOOD)
    c.paint()
    for _ in range(2):
        acc = cairo.ImageSurface(cairo.FORMAT_ARGB32, sw, sh)
        c = cairo.Context(acc)
        c.set_operator(cairo.OPERATOR_ADD)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                c.set_source_surface(small, dx, dy)
                c.paint_with_alpha(1 / 9.0)
        small = acc
    out = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    c = cairo.Context(out)
    c.scale(w / sw, h / sh)
    c.set_source_surface(small, 0, 0)
    c.get_source().set_filter(cairo.FILTER_BILINEAR)
    c.paint()
    return out


def render(polys, bbox, p, scale=1.0):
    """
    Dessine le texte. Renvoie (surface ARGB32, (x0, y0)) où (x0, y0) est
    l'origine de la surface dans le repère de la géométrie (pleine taille).
    """
    p = normalize(p)
    x0, y0, x1, y1 = extents(bbox, p)
    W = max(1, int(math.ceil((x1 - x0) * scale)))
    H = max(1, int(math.ceil((y1 - y0) * scale)))
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    if not polys:
        return surf, (x0, y0)

    def prepared(target):
        c = cairo.Context(target)
        c.scale(scale, scale)
        c.translate(-x0, -y0)
        _trace(c, polys)
        return c, c.copy_path()

    # Ombre portée
    if p["shadow"] and p["shadow_col"][3] > 0:
        sil = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
        c, path = prepared(sil)
        col = list(p["shadow_col"][:3]) + [1.0]
        _draw_body(c, path, p, bbox, scale, mono=col)
        sil = _blur(sil, p["shadow_blur"] * scale)
        c = cairo.Context(surf)
        c.set_source_surface(sil, p["shadow_dx"] * scale, p["shadow_dy"] * scale)
        c.paint_with_alpha(p["shadow_col"][3])

    c, path = prepared(surf)
    _draw_body(c, path, p, bbox, scale)
    surf.flush()
    return surf, (x0, y0)


def render_full(p, scale=1.0):
    polys, bbox = geometry(p)
    surf, origin = render(polys, bbox, p, scale)
    return surf, origin, polys, bbox


# --------------------------------------------------------------------------
# Styles prédéfinis (inspirés de la galerie Fontwork, noms originaux)
# --------------------------------------------------------------------------
def _c(h, a=1.0):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)] + [a]


NO_SHADOW = {"shadow": False}
PRESETS = [
    ("Simple", dict(shape="droit", fill_mode="solid", fill1=_c("202020"),
                    outline_w=0, shadow=False, extrude=0)),
    ("Arc doré", dict(shape="arc_haut", arc=160, fill_mode="gradient", fill1=_c("fff3a0"),
                      fill2=_c("c88a00"), grad_angle=90, outline_w=3, outline_col=_c("6b4300"),
                      shadow=True, shadow_dx=5, shadow_dy=6, shadow_blur=5,
                      shadow_col=_c("000000", 0.45), extrude=0)),
    ("Sourire", dict(shape="arc_bas", arc=150, fill_mode="gradient", fill1=_c("ff5fa2"),
                     fill2=_c("8a2be2"), grad_angle=0, outline_w=2, outline_col=_c("ffffff"),
                     shadow=True, shadow_dx=4, shadow_dy=5, shadow_blur=4,
                     shadow_col=_c("30003a", 0.5), extrude=0)),
    ("Vague océan", dict(shape="vague", amount=45, freq=1.0, phase=0, fill_mode="gradient",
                         fill1=_c("7fe3ff"), fill2=_c("0b3d91"), grad_angle=90,
                         outline_w=3, outline_col=_c("ffffff"), shadow=True, shadow_dx=6,
                         shadow_dy=8, shadow_blur=6, shadow_col=_c("001a33", 0.5), extrude=0)),
    ("Rétro", dict(shape="gonfle", amount=45, fill_mode="gradient", fill1=_c("ffe066"),
                   fill2=_c("ff6b00"), grad_angle=90, outline_w=3, outline_col=_c("3b1300"),
                   extrude=22, extrude_angle=50, extrude_col=_c("b33c00"),
                   shadow=True, shadow_dx=10, shadow_dy=12, shadow_blur=8,
                   shadow_col=_c("000000", 0.35))),
    ("Entonnoir", dict(shape="entonnoir", amount=55, fill_mode="gradient", fill1=_c("ffef5a"),
                       fill2=_c("e0161b"), grad_angle=90, outline_w=2, outline_col=_c("5a0000"),
                       extrude=0, shadow=True, shadow_dx=6, shadow_dy=8,
                       shadow_blur=6, shadow_col=_c("000000", 0.4))),
    ("Pierre", dict(shape="dome", amount=35, fill_mode="gradient", fill1=_c("d9d9d9"),
                    fill2=_c("5c5c5c"), grad_angle=70, outline_w=2, outline_col=_c("2a2a2a"),
                    extrude=18, extrude_angle=40, extrude_col=_c("555555"),
                    shadow=True, shadow_dx=12, shadow_dy=14, shadow_blur=10,
                    shadow_col=_c("000000", 0.4))),
    ("Contour bleu", dict(shape="droit", fill_mode="none", outline_w=4,
                          outline_col=_c("2f6fd6"), shadow=False, extrude=0)),
    ("Néon", dict(shape="droit", fill_mode="solid", fill1=_c("ffffff"), outline_w=4,
                  outline_col=_c("ff2bd6"), shadow=True, shadow_dx=0, shadow_dy=0,
                  shadow_blur=18, shadow_col=_c("ff2bd6", 0.9), extrude=0)),
    ("Anneau", dict(shape="cercle", fill_mode="gradient", fill1=_c("ffb347"),
                    fill2=_c("e06400"), grad_angle=45, outline_w=2, outline_col=_c("7a3300"),
                    shadow=True, shadow_dx=4, shadow_dy=4, shadow_blur=4,
                    shadow_col=_c("000000", 0.35), extrude=0)),
    ("Pop BD", dict(shape="chevron", amount=35, fill_mode="solid", fill1=_c("ffd400"),
                    outline_w=6, outline_col=_c("111111"), extrude=16, extrude_angle=35,
                    extrude_col=_c("e0161b"), shadow=False)),
    ("Glace", dict(shape="pince", amount=40, fill_mode="gradient", fill1=_c("ffffff"),
                   fill2=_c("8fd3ff"), grad_angle=90, outline_w=3, outline_col=_c("1d6fb8"),
                   shadow=True, shadow_dx=6, shadow_dy=6, shadow_blur=6,
                   shadow_col=_c("003366", 0.4), extrude=0)),
    ("Feu", dict(shape="perspective", amount=55, fill_mode="gradient", fill1=_c("fff200"),
                 fill2=_c("d10000"), grad_angle=90, outline_w=0, shadow=True, shadow_dx=0,
                 shadow_dy=0, shadow_blur=14, shadow_col=_c("ff4000", 0.85), extrude=0)),
    ("Montée verte", dict(shape="inclinaison", amount=25, fill_mode="gradient",
                          fill1=_c("c6ff4d"), fill2=_c("2e8b00"), grad_angle=90,
                          outline_w=3, outline_col=_c("0f3300"), extrude=12,
                          extrude_angle=60, extrude_col=_c("1f5c00"), shadow=False)),
    ("Spirale", dict(shape="spirale", amount=60, arc=540, fill_mode="gradient",
                     fill1=_c("6a5acd"), fill2=_c("00c2a8"), grad_angle=0, outline_w=0,
                     shadow=False, extrude=0)),
]
PRESET_KEYS = set(DEFAULTS) - {"text", "font", "size", "spacing", "line_spacing", "align"}


def apply_preset(p, preset):
    """Applique un style en conservant le texte et la police."""
    out = normalize(p)
    base = {k: DEFAULTS[k] for k in PRESET_KEYS}
    base.update(preset)
    out.update(base)
    return out
