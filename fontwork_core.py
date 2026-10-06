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
import os
import random
import re

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
    # --- ajouts v4 (mode texte) ---
    "mode": "texte",               # texte / badge
    "fill3": [1.0, 0.95, 0.6, 1.0],   # couleur du milieu (dégradé 3 couleurs)
    "lines_sep": False,            # déformer chaque ligne séparément
    "line_gap": 10.0,              # écart entre lignes séparées (px)
    "grow_center": 0.0,            # lettres plus grandes au centre (%)
    "grow_right": 0.0,             # lettres plus grandes vers la droite (%)
    "rot_x": 0.0,                  # rotation 3D autour de l'axe horizontal (°)
    "rot_y": 0.0,                  # rotation 3D autour de l'axe vertical (°)
    "persp": 2.0,                  # distance de l'observateur (x la taille)
    "bevel": "none",               # none / relief / grave
    "bevel_depth": 4.0,
    "bevel_soft": 2.0,
    "bevel_angle": 225.0,          # direction de la lumière (225 = haut gauche)
    "bevel_hi": 0.7,
    "bevel_sh": 0.5,
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
                 "width", "shape", "amount", "freq", "phase", "arc", "rotation",
                 "lines_sep", "line_gap", "grow_center", "grow_right",
                 "rot_x", "rot_y", "persp")

FILL_MODES = [("none", "Aucun (contour seul)"), ("solid", "Couleur unie"),
              ("gradient", "Dégradé 2 couleurs"), ("gradient3", "Dégradé 3 couleurs"),
              ("metal_or", "Métal : or"), ("metal_argent", "Métal : argent"),
              ("metal_bronze", "Métal : bronze")]

METALS = {
    "or": [(0, "fff6c2"), (0.25, "e0b53a"), (0.5, "fff0a8"), (0.75, "b8860b"), (1, "f5d76e")],
    "argent": [(0, "ffffff"), (0.3, "b8bcc2"), (0.5, "f4f6f8"), (0.75, "8e939a"), (1, "e0e3e6")],
    "bronze": [(0, "f3c08a"), (0.3, "a4622b"), (0.5, "e6a468"), (0.75, "7a4518"), (1, "c98b50")],
    "cuivre": [(0, "ffc9a8"), (0.3, "b5562a"), (0.5, "f0a27a"), (0.75, "7f3216"), (1, "d9825a")],
}


def normalize(p):
    """Complète un dictionnaire de paramètres avec les valeurs par défaut."""
    out = dict(DEFAULTS)
    if p:
        out.update({k: v for k, v in p.items() if k in DEFAULTS or k.startswith("_")})
    if out["shape"] not in SHAPE_KEYS:
        out["shape"] = "droit"
    if out["mode"] not in ("texte", "badge", "chemin", "interieur"):
        out["mode"] = "texte"
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
        bx0, by0, bx1, by1 = _bbox(polys)
        ink = (bx0, by0, bx1 - bx0, by1 - by0)
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


def _warp_block(p, text):
    """Contours d'un bloc de texte déformés par la forme choisie."""
    polys, ink, logical = _text_polygons(dict(p, text=text))
    if not polys:
        return []
    x0 = ink[0]
    w = max(1.0, ink[2])
    y0 = logical[1]
    h = max(1.0, logical[3])
    nchars = len("".join((text or "").split()))
    warp = _make_warp(p, w, h, nchars)
    maxlen = max(0.5, h / 40.0)
    gc = max(-0.9, min(2.0, p["grow_center"] / 100.0))
    gr = max(-1.8, min(1.8, p["grow_right"] / 100.0))
    grow = abs(gc) > 1e-6 or abs(gr) > 1e-6
    out = []
    for poly in polys:
        q = []
        for x, y in _subdivide(poly, maxlen):
            u = (x - x0) / w
            v = (y - y0) / h
            if grow:
                # hauteur des lettres variable, ligne de base conservée
                f = (1 + gc * math.sin(math.pi * min(1.0, max(0.0, u)))) * max(0.1, 1 + gr * (u - 0.5))
                v = 1 - (1 - v) * f
            q.append(warp(u, v))
        out.append(q)
    return out


def _rotate(polys, deg, cx=0.0, cy=0.0):
    rot = math.radians(deg)
    if abs(rot) < 1e-9:
        return polys
    c, s = math.cos(rot), math.sin(rot)
    return [[(cx + (x - cx) * c - (y - cy) * s, cy + (x - cx) * s + (y - cy) * c)
             for x, y in poly] for poly in polys]


def _rotate3d(polys, bbox, rx, ry, persp):
    """Rotation 3D (axes X puis Y) avec projection en perspective."""
    ax, ay = math.radians(rx), math.radians(ry)
    cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
    D = max(0.8, persp) * max(bbox[2] - bbox[0], bbox[3] - bbox[1], 1.0)
    cay, say, cax, sax = math.cos(ay), math.sin(ay), math.cos(ax), math.sin(ax)
    out = []
    for poly in polys:
        q = []
        for x, y in poly:
            X, Y = x - cx, y - cy
            X1, Z1 = X * cay, -X * say
            Y1, Z2 = Y * cax - Z1 * sax, Y * sax + Z1 * cax
            k = D / max(D + Z2, 0.05 * D)
            q.append((cx + X1 * k, cy + Y1 * k))
        out.append(q)
    return out


def geometry(p):
    """Renvoie (polygones déformés, bbox=(x0, y0, x1, y1))."""
    p = normalize(p)
    text = p["text"] or ""
    lines = text.split("\n")
    if p["lines_sep"] and sum(1 for l in lines if l.strip()) > 1:
        out, ytop = [], None
        for line in lines:
            if not line.strip():
                if ytop is not None:
                    ytop += p["size"] * 0.8
                continue
            lp = _warp_block(p, line)
            if not lp:
                continue
            bx0, by0, bx1, by1 = _bbox(lp)
            cxl = (bx0 + bx1) / 2
            dy = 0 if ytop is None else ytop - by0
            out += [[(x - cxl, y + dy) for x, y in poly] for poly in lp]
            ytop = by1 + dy + p["line_gap"]
    else:
        out = _warp_block(p, text)
    if not out:
        return [], (0.0, 0.0, 1.0, 1.0)

    bbox = _bbox(out)
    if abs(p["rotation"]) > 1e-6:
        out = _rotate(out, p["rotation"], (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)
        bbox = _bbox(out)
    if abs(p["rot_x"]) > 1e-6 or abs(p["rot_y"]) > 1e-6:
        out = _rotate3d(out, bbox, max(-85, min(85, p["rot_x"])),
                        max(-85, min(85, p["rot_y"])), p["persp"])
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


def _gradient(bbox, angle, stops):
    cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
    t = math.radians(angle)
    dx, dy = math.cos(t), math.sin(t)
    d = abs((bbox[2] - bbox[0]) / 2 * dx) + abs((bbox[3] - bbox[1]) / 2 * dy)
    g = cairo.LinearGradient(cx - dx * d, cy - dy * d, cx + dx * d, cy + dy * d)
    for o, c in stops:
        g.add_color_stop_rgba(o, *(c if isinstance(c, (list, tuple)) else _c(c)))
    return g


def _fill_source(p, bbox):
    mode = p["fill_mode"]
    if mode == "solid":
        return cairo.SolidPattern(*p["fill1"])
    if mode.startswith("metal_") and mode[6:] in METALS:
        return _gradient(bbox, p["grad_angle"], METALS[mode[6:]])
    if mode == "gradient3":
        return _gradient(bbox, p["grad_angle"], [(0, p["fill1"]), (0.5, p["fill3"]), (1, p["fill2"])])
    cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
    t = math.radians(p["grad_angle"])
    dx, dy = math.cos(t), math.sin(t)
    d = abs((bbox[2] - bbox[0]) / 2 * dx) + abs((bbox[3] - bbox[1]) / 2 * dy)
    g = cairo.LinearGradient(cx - dx * d, cy - dy * d, cx + dx * d, cy + dy * d)
    g.add_color_stop_rgba(0, *p["fill1"])
    g.add_color_stop_rgba(1, *p["fill2"])
    return g


def _draw_body(ctx, path, p, bbox, scale, mono=None, parts=("extrude", "outline", "fill")):
    """Relief 3D + contour + remplissage. mono = couleur unique (silhouette)."""
    sw = _stroke_width(p)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    ctx.set_line_width(sw)
    ctx.set_fill_rule(cairo.FILL_RULE_WINDING)

    # Relief : empilement de copies décalées, de l'arrière vers l'avant
    depth = p["extrude"]
    if depth > 0 and "extrude" in parts:
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
    if sw > 0 and "outline" in parts:
        ctx.new_path()
        ctx.append_path(path)
        ctx.set_source_rgba(*(mono or p["outline_col"]))
        ctx.stroke()

    # Remplissage
    if p["fill_mode"] != "none" and "fill" in parts:
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


def _copy(surf):
    out = cairo.ImageSurface(cairo.FORMAT_ARGB32, surf.get_width(), surf.get_height())
    c = cairo.Context(out)
    c.set_source_surface(surf, 0, 0)
    c.paint()
    return out


def _bevel(surf, style, depth, soft, angle, hi, sh):
    """
    Biseau (relief) ou gravure sur tout ce que contient la surface :
    bord éclairé en clair, bord opposé en sombre. Modifie la surface.
    """
    if style not in ("relief", "grave") or depth < 0.3:
        return
    a = math.radians(angle)
    lx, ly = math.cos(a) * depth, math.sin(a) * depth
    if style == "grave":
        lx, ly = -lx, -ly

    def band(sx, sy):
        m = _copy(surf)
        c = cairo.Context(m)
        c.set_operator(cairo.OPERATOR_DEST_OUT)
        c.set_source_surface(surf, sx, sy)
        c.paint()
        return _blur(m, soft) if soft >= 1 else m

    lit, dark = band(-lx, -ly), band(lx, ly)
    c = cairo.Context(surf)
    c.set_operator(cairo.OPERATOR_ATOP)
    if hi > 0:
        c.set_source_rgba(1, 1, 1, hi)
        c.mask_surface(lit, 0, 0)
    if sh > 0:
        c.set_source_rgba(0, 0, 0, sh)
        c.mask_surface(dark, 0, 0)


def _apply_metal(surf, pattern, scale, x0, y0):
    """Teinte métal : multiplie les couleurs de la surface par le motif métal."""
    mask = _copy(surf)
    c = cairo.Context(surf)
    c.scale(scale, scale)
    c.translate(-x0, -y0)
    c.set_source(pattern)          # motif exprimé dans le repère du badge
    c.identity_matrix()
    c.set_operator(cairo.OPERATOR_MULTIPLY)
    c.mask_surface(mask, 0, 0)


def _paint_shadow(dest, src, col, dx, dy, blur):
    """Ombre portée de tout le contenu de src, peinte sur dest."""
    sil = cairo.ImageSurface(cairo.FORMAT_ARGB32, src.get_width(), src.get_height())
    c = cairo.Context(sil)
    c.set_source_rgba(col[0], col[1], col[2], 1.0)
    c.mask_surface(src, 0, 0)
    sil = _blur(sil, blur)
    c = cairo.Context(dest)
    c.set_source_surface(sil, dx, dy)
    c.paint_with_alpha(col[3])


def render(polys, bbox, p, scale=1.0, ext=None, underlay=None):
    """
    Dessine le texte. Renvoie (surface ARGB32, (x0, y0)) où (x0, y0) est
    l'origine de la surface dans le repère de la géométrie (pleine taille).
    ext : zone à couvrir (sinon calculée) ; underlay(ctx) : dessin placé dessous.
    """
    p = normalize(p)
    x0, y0, x1, y1 = ext or extents(bbox, p)
    W = max(1, int(math.ceil((x1 - x0) * scale)))
    H = max(1, int(math.ceil((y1 - y0) * scale)))
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    if underlay is not None:
        c = cairo.Context(surf)
        c.scale(scale, scale)
        c.translate(-x0, -y0)
        underlay(c)
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
    if p["bevel"] in ("relief", "grave") and p["fill_mode"] != "none":
        # le biseau s'applique au remplissage, dessiné à part puis posé dessus
        _draw_body(c, path, p, bbox, scale, parts=("extrude", "outline"))
        face = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
        cf, pathf = prepared(face)
        _draw_body(cf, pathf, p, bbox, scale, parts=("fill",))
        _bevel(face, p["bevel"], p["bevel_depth"] * scale, p["bevel_soft"] * scale,
               p["bevel_angle"], p["bevel_hi"], p["bevel_sh"])
        c = cairo.Context(surf)
        c.set_source_surface(face, 0, 0)
        c.paint()
    else:
        _draw_body(c, path, p, bbox, scale)
    surf.flush()
    return surf, (x0, y0)


def render_full(p, scale=1.0):
    polys, bbox = geometry(p)
    surf, origin = render(polys, bbox, p, scale)
    return surf, origin, polys, bbox


# --------------------------------------------------------------------------
# Mode badge / sceau : textes sur un cercle, anneaux, filets, motifs
# --------------------------------------------------------------------------
def _ring_defaults(i, on, r, fill, sw, stroke, metal=True):
    return {"b_r%d_on" % i: on, "b_r%d_r" % i: r, "b_r%d_fill" % i: fill,
            "b_r%d_sw" % i: sw, "b_r%d_stroke" % i: stroke, "b_r%d_metal" % i: metal}


WHITE, BLACK, NONE = [1.0, 1.0, 1.0, 1.0], [0.0, 0.0, 0.0, 1.0], [0.0, 0.0, 0.0, 0.0]
BADGE_DEFAULTS = {
    "b_size": 600.0,              # diamètre du badge (px)
    "b_rotation": 0.0,
    # textes du haut et du bas
    "b_top_text": "NOM DU CLUB", "b_top_font": "Sans-serif Bold", "b_top_size": 56.0,
    "b_top_col": WHITE, "b_top_r": 82.0, "b_top_fit": 0.0, "b_top_sp": 2.0,
    "b_top_sw": 0.0, "b_top_scol": BLACK,
    "b_bot_text": "VILLE", "b_bot_font": "Sans-serif Bold", "b_bot_size": 56.0,
    "b_bot_col": WHITE, "b_bot_r": 82.0, "b_bot_fit": 0.0, "b_bot_sp": 6.0,
    "b_bot_sw": 0.0, "b_bot_scol": BLACK,
    # texte central
    "b_ctr_text": "", "b_ctr_font": "Sans-serif Bold", "b_ctr_size": 48.0,
    "b_ctr_col": WHITE, "b_ctr_ls": 1.0, "b_ctr_dy": 0.0,
    # filets en arc entre les textes
    "b_fil_on": False, "b_fil_r": 82.0, "b_fil_w": 3.0, "b_fil_col": WHITE, "b_fil_gap": 5.0,
    # couronne de motifs
    "b_mot_on": False, "b_mot_char": "★", "b_mot_font": "Sans-serif", "b_mot_n": 24,
    "b_mot_r": 93.0, "b_mot_size": 26.0, "b_mot_col": WHITE, "b_mot_start": 0.0,
    "b_mot_follow": True,
    # effets
    "b_metal": "aucun",           # aucun / or / argent / bronze
    "b_bev_scope": "rien",        # rien / textes / tout
    "b_bev_style": "relief", "b_bev_depth": 3.0, "b_bev_soft": 1.5,
    "b_bev_angle": 225.0, "b_bev_hi": 0.7, "b_bev_sh": 0.55,
    "b_sh_on": False, "b_sh_dx": 6.0, "b_sh_dy": 8.0, "b_sh_blur": 8.0,
    "b_sh_col": [0.0, 0.0, 0.0, 0.45],
    # sélection circulaire créée à la validation (pour une photo, un logo…)
    "b_sel_on": True, "b_sel_r": 62.0,
    "b_sel_mode": "canal",        # canal (enregistré, sans sélection active) / selection
    # bord extérieur (anneau 1)
    "b_edge": "lisse",            # lisse / feston / dents / crans / ebreche
    "b_edge_n": 24, "b_edge_depth": 5.0,
    # cordelette torsadée
    "b_rope_on": False, "b_rope_r": 97.0, "b_rope_w": 14.0, "b_rope_col": [0.96, 0.9, 0.75, 1.0],
    # guillochage
    "b_guil_on": False, "b_guil_r1": 86.0, "b_guil_r2": 99.0, "b_guil_n": 10, "b_guil_waves": 36,
    "b_guil_w": 0.8, "b_guil_col": [0.95, 0.88, 0.6, 1.0],
    # couronne de lauriers
    "b_laur_on": False, "b_laur_r": 108.0, "b_laur_size": 46.0, "b_laur_span": 150.0,
    "b_laur_gap": 30.0, "b_laur_col": [0.95, 0.88, 0.6, 1.0],
    # forme SVG au centre
    "b_icon_on": False, "b_icon_file": "builtin:etoile.svg", "b_icon_size": 30.0,
    "b_icon_dy": 0.0, "b_icon_col": WHITE, "b_icon_metal": True,
    "b_icon_auto": True,          # forme au-dessus du texte central s'il y en a un
    # petite mention en bas
    "b_note_text": "", "b_note_font": "Sans-serif Bold", "b_note_size": 16.0, "b_note_r": 92.0,
    "b_note_col": BLACK,
    # bandeau sous le texte central
    "b_ban_on": False, "b_ban_style": "ruban",   # ruban / plaque
    "b_ban_w": 95.0,              # largeur (% du diamètre)
    "b_ban_h": 170.0,             # hauteur (% de la hauteur du texte central)
    "b_ban_curve": 12.0,          # courbure du ruban (px)
    "b_ban_fill": [0.09, 0.2, 0.38, 1.0], "b_ban_stroke": [0.96, 0.9, 0.72, 1.0],
    "b_ban_sw": 3.0, "b_ban_rivets": True, "b_ban_metal": False,
    # couronne de perles / rivets / diamants
    "b_pearl_on": False, "b_pearl_style": "perle",   # perle / rivet / diamant
    "b_pearl_r": 95.0, "b_pearl_n": 36, "b_pearl_size": 12.0,
    "b_pearl_col": [0.96, 0.9, 0.72, 1.0], "b_pearl_metal": True,
    # texture
    "b_tex": "aucune",            # aucune / brosse / cire / patine / rouille
    "b_tex_amount": 0.5,
}
BADGE_DEFAULTS.update(_ring_defaults(1, True, 100.0, [0.12, 0.43, 0.23, 1.0], 6.0, WHITE))
BADGE_DEFAULTS.update(_ring_defaults(2, True, 64.0, [0.83, 0.16, 0.13, 1.0], 5.0, WHITE))
BADGE_DEFAULTS.update(_ring_defaults(3, False, 90.0, NONE, 3.0, WHITE))
BADGE_DEFAULTS.update(_ring_defaults(4, False, 50.0, NONE, 3.0, WHITE))
DEFAULTS.update(BADGE_DEFAULTS)
BADGE_KEYS = set(BADGE_DEFAULTS)
BADGE_TEXT_KEYS = {"b_top_text", "b_bot_text", "b_ctr_text"}


def _text_params(text, font, size, spacing=0.0, line_spacing=1.0):
    return {"text": text, "font": font, "size": max(1.0, size), "spacing": spacing,
            "line_spacing": line_spacing, "align": "center"}


def _fit_spacing(tp, r_mid, fit_deg):
    """Espacement des lettres pour que le texte occupe fit_deg degrés du cercle."""
    if fit_deg <= 0 or not tp["text"].strip():
        return tp
    polys, ink, logical = _text_polygons(dict(tp, spacing=0.0))
    if not polys:
        return tp
    target = math.radians(min(359.0, fit_deg)) * r_mid
    n = max(1, len(tp["text"]) - 1)
    sp = (target - ink[2]) / n
    # un texte court n'est pas étiré à l'excès : espacement plafonné
    return dict(tp, spacing=min(max(sp, -tp["size"] * 0.4), tp["size"] * 0.45))


def _circle_text(tp, r_mid, center_deg, bottom):
    """
    Texte courbé sur un cercle. Haut : lettres vers l'extérieur, lecture
    dans le sens horaire. Bas : lettres à l'endroit, lecture de gauche à droite.
    Renvoie (polygones, angle occupé en degrés).
    """
    if not tp["text"].strip():
        return [], 0.0
    polys, ink, logical = _text_polygons(tp)
    if not polys:
        return [], 0.0
    x0, w = ink[0], max(1.0, ink[2])
    y0, h = logical[1], max(1.0, logical[3])
    R = max(1.0, r_mid - h / 2)
    sweep = w / (R + h / 2)
    tc = math.radians(center_deg)
    maxlen = max(0.5, h / 40.0)
    out = []
    for poly in polys:
        q = []
        for x, y in _subdivide(poly, maxlen):
            u, v = (x - x0) / w, (y - y0) / h
            if bottom:
                t, r = tc - (u - 0.5) * sweep, R + v * h
            else:
                t, r = tc + (u - 0.5) * sweep, R + (1 - v) * h
            q.append((r * math.cos(t), r * math.sin(t)))
        out.append(q)
    return out, math.degrees(sweep)


def _centered_text(tp):
    polys, ink, logical = _text_polygons(tp)
    if not polys:
        return []
    bx0, by0, bx1, by1 = _bbox(polys)
    cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
    return [[(x - cx, y - cy) for x, y in poly] for poly in polys]


def _max_radius(polys):
    return max((math.hypot(x, y) for poly in polys for x, y in poly), default=0.0)


def badge_geometry(p):
    p = normalize(p)
    R = max(10.0, p["b_size"] / 2.0)
    rot = p["b_rotation"]
    els = []

    for i in range(1, 5):
        if p["b_r%d_on" % i]:
            r = R * p["b_r%d_r" % i] / 100.0
            edge = None
            if i == 1 and p["b_edge"] in EDGE_KEYS and p["b_edge"] != "lisse":
                edge = _edge_points(p["b_edge"], r, int(p["b_edge_n"]), p["b_edge_depth"], rot)
            if p["b_r%d_fill" % i][3] > 0:
                els.append({"kind": "ring_fill", "r": r, "fill": p["b_r%d_fill" % i],
                            "edge": edge, "metal": bool(p["b_r%d_metal" % i])})
            if p["b_r%d_sw" % i] > 0 and p["b_r%d_stroke" % i][3] > 0:
                els.append({"kind": "ring_stroke", "r": r, "sw": p["b_r%d_sw" % i],
                            "stroke": p["b_r%d_stroke" % i], "edge": edge})
    if p["b_guil_on"]:
        els.append({"kind": "guil", "r1": R * p["b_guil_r1"] / 100.0,
                    "r2": R * p["b_guil_r2"] / 100.0, "n": int(p["b_guil_n"]),
                    "waves": int(p["b_guil_waves"]), "w": p["b_guil_w"], "col": p["b_guil_col"],
                    "rot": rot})
    if p["b_rope_on"]:
        els.append({"kind": "rope", "r": R * p["b_rope_r"] / 100.0, "w": p["b_rope_w"],
                    "col": p["b_rope_col"], "rot": rot})
    if p["b_laur_on"]:
        els.append({"kind": "laurel", "r": R * p["b_laur_r"] / 100.0, "size": p["b_laur_size"],
                    "span": p["b_laur_span"], "gap": p["b_laur_gap"], "col": p["b_laur_col"],
                    "rot": rot})
    icon_shift, icon_k, text_shift = 0.0, 1.0, 0.0
    ctr_polys = []
    if p["b_ctr_text"].strip():
        tp = _text_params(p["b_ctr_text"], p["b_ctr_font"], p["b_ctr_size"],
                          0.0, p["b_ctr_ls"])
        ctr_polys = _centered_text(tp)
    if p["b_icon_on"] and p["b_icon_auto"] and ctr_polys:
        # disposition automatique : forme au-dessus, texte en dessous
        ht = _bbox(ctr_polys)[3] - _bbox(ctr_polys)[1]
        hi = 2 * R * p["b_icon_size"] / 100.0
        # place disponible : disque central (plus petit anneau sous les textes du cercle)
        inner = [R * p["b_r%d_r" % i] / 100.0 for i in range(1, 5)
                 if p["b_r%d_on" % i] and p["b_r%d_r" % i] < min(p["b_top_r"], p["b_bot_r"])]
        r_in = min(inner) if inner else R * 0.6
        room = 2 * r_in * 0.62 - ht - R * 0.05
        icon_k = max(0.3, min(1.0, room / max(hi, 1e-6)))
        hi *= icon_k
        total = hi + R * 0.06 + ht
        icon_shift = -total / 2 + hi / 2
        text_shift = total / 2 - ht / 2
    if p["b_icon_on"]:
        try:
            subs = load_shape(p["b_icon_file"])
        except Exception:
            subs = []
        if subs:
            bb = _bbox([sp[0] for sp in subs])
            k = (2 * R * p["b_icon_size"] / 100.0) / max(bb[2] - bb[0], bb[3] - bb[1], 1e-6)
            k *= icon_k
            cx, cy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
            polys = [[((x - cx) * k, (y - cy) * k + p["b_icon_dy"] + icon_shift) for x, y in pts]
                     for pts, closed in subs if closed]
            polys = _rotate(polys, rot)
            if polys:
                els.append({"kind": "icon", "polys": polys, "col": p["b_icon_col"],
                            "metal": bool(p["b_icon_metal"])})

    sweeps = {}
    texts = []
    for key, center, bottom in (("top", -90.0, False), ("bot", 90.0, True)):
        tp = _text_params(p["b_%s_text" % key], p["b_%s_font" % key],
                          p["b_%s_size" % key], p["b_%s_sp" % key])
        r_mid = R * p["b_%s_r" % key] / 100.0
        tp = _fit_spacing(tp, r_mid, p["b_%s_fit" % key])
        polys, sw = _circle_text(tp, r_mid, center + rot, bottom)
        sweeps[key] = sw
        if polys:
            texts.append({"kind": "text", "polys": polys, "col": p["b_%s_col" % key],
                          "sw": p["b_%s_sw" % key], "scol": p["b_%s_scol" % key]})

    if p["b_pearl_on"] and p["b_pearl_n"] >= 1:
        els.append({"kind": "pearls", "r": R * p["b_pearl_r"] / 100.0, "n": int(p["b_pearl_n"]),
                    "size": p["b_pearl_size"], "style": p["b_pearl_style"],
                    "col": p["b_pearl_col"], "rot": rot, "metal": bool(p["b_pearl_metal"])})
    if p["b_ban_on"]:
        if ctr_polys:
            tb = _bbox(ctr_polys)
            th, tw = tb[3] - tb[1], tb[2] - tb[0]
        else:
            th, tw = p["b_ctr_size"] * 0.75, 0.0
        H = max(4.0, th * p["b_ban_h"] / 100.0)
        Wb = max(tw + H * 1.2, 2 * R * p["b_ban_w"] / 100.0)
        cy = p["b_ctr_dy"] + text_shift
        bp = _banner_parts(p["b_ban_style"], Wb, H, cy, p["b_ban_curve"], p["b_ban_fill"],
                           p["b_ban_rivets"])
        parts = [(_rotate([pts], rot)[0], col, out) for pts, col, out in bp["parts"]]
        rivs = [(*_rotate([[(x, y)]], rot)[0][0], r) for x, y, r in bp["rivets"]]
        els.append({"kind": "banner", "rot": 0.0, "metal": bool(p["b_ban_metal"]),
                    "parts": parts, "rivets": rivs,
                    "stroke": p["b_ban_stroke"], "sw": p["b_ban_sw"]})
    if ctr_polys:
        polys = [[(x, y + p["b_ctr_dy"] + text_shift) for x, y in poly] for poly in ctr_polys]
        polys = _rotate(polys, rot)
        if polys:
            texts.append({"kind": "text", "polys": polys, "col": p["b_ctr_col"],
                          "sw": 0.0, "scol": BLACK})

    if p["b_fil_on"]:
        g = p["b_fil_gap"]
        st, sb = sweeps.get("top", 0.0), sweeps.get("bot", 0.0)
        gt, gb = (g if st > 0 else 0.0), (g if sb > 0 else 0.0)
        arcs = []
        for a1, a2 in ((-90 + st / 2 + gt, 90 - sb / 2 - gb),
                       (90 + sb / 2 + gb, 270 - st / 2 - gt)):
            if a2 > a1:
                arcs.append((a1 + rot, a2 + rot))
        if arcs:
            els.append({"kind": "arcs", "r": R * p["b_fil_r"] / 100.0, "arcs": arcs,
                        "w": p["b_fil_w"], "col": p["b_fil_col"]})

    if p["b_mot_on"] and p["b_mot_char"].strip() and p["b_mot_n"] >= 1:
        glyph = _centered_text(_text_params(p["b_mot_char"], p["b_mot_font"], p["b_mot_size"]))
        n = int(p["b_mot_n"])
        rm = R * p["b_mot_r"] / 100.0
        polys = []
        for k in range(n):
            t = math.radians(-90 + rot + p["b_mot_start"] + k * 360.0 / n)
            g = _rotate(glyph, math.degrees(t) + 90) if p["b_mot_follow"] else glyph
            px, py = rm * math.cos(t), rm * math.sin(t)
            polys += [[(x + px, y + py) for x, y in poly] for poly in g]
        if polys:
            els.append({"kind": "motifs", "polys": polys, "col": p["b_mot_col"]})

    if p["b_note_text"].strip():
        tp = _text_params(p["b_note_text"], p["b_note_font"], p["b_note_size"], 1.0)
        polys, _sw = _circle_text(tp, R * p["b_note_r"] / 100.0, 90.0 + rot, True)
        if polys:
            texts.append({"kind": "text", "polys": polys, "col": p["b_note_col"],
                          "sw": 0.0, "scol": BLACK})

    # le bandeau passe devant les décors, derrière les textes
    els = [e for e in els if e["kind"] != "banner"] + [e for e in els if e["kind"] == "banner"]
    els += texts
    ext = 1.0
    for e in els:
        k = e["kind"]
        if k in ("ring_fill", "ring_stroke"):
            ext = max(ext, e["r"] + e.get("sw", 0) / 2)
        elif k == "arcs":
            ext = max(ext, e["r"] + e["w"] / 2)
        elif k == "rope":
            ext = max(ext, e["r"] + e["w"] / 2 + 1)
        elif k == "guil":
            ext = max(ext, e["r2"])
        elif k == "laurel":
            ext = max(ext, e["r"] + e["size"])
        elif k == "pearls":
            ext = max(ext, e["r"] + e["size"] / 2 + 1)
        elif k == "banner":
            pass        # le bandeau peut déborder du cercle : pris en compte dans bbox
        else:
            ext = max(ext, _max_radius(e["polys"]) + e.get("sw", 0.0))
    polys = [q for e in els if e["kind"] in ("text", "motifs", "icon") for q in e["polys"]]
    e2 = ext + 2
    bx0, by0, bx1, by1 = -e2, -e2, e2, e2
    for e in els:
        if e["kind"] == "banner":
            pb = _bbox([pts for pts, _c, _o in e["parts"]])
            m = e["sw"] + 2
            bx0, by0 = min(bx0, pb[0] - m), min(by0, pb[1] - m)
            bx1, by1 = max(bx1, pb[2] + m), max(by1, pb[3] + m)
    return {"els": els, "ext": e2, "R": R, "polys": polys, "box": (bx0, by0, bx1, by1)}


def badge_extents(g, p):
    e = g["ext"]
    x0, y0, x1, y1 = g.get("box", (-e, -e, e, e))
    if p["b_sh_on"] and p["b_sh_col"][3] > 0:
        b = p["b_sh_blur"] * 2 + 2
        x0 = min(x0, x0 + p["b_sh_dx"] - b)
        y0 = min(y0, y0 + p["b_sh_dy"] - b)
        x1 = max(x1, x1 + p["b_sh_dx"] + b)
        y1 = max(y1, y1 + p["b_sh_dy"] + b)
    return math.floor(x0), math.floor(y0), math.ceil(x1), math.ceil(y1)


EDGES = [("lisse", "Lisse"), ("feston", "Festonné (cire)"), ("dents", "Dentelé (capsule)"),
         ("crans", "Cranté (engrenage)"), ("ebreche", "Ébréché")]
EDGE_KEYS = [e[0] for e in EDGES]


def _edge_points(kind, R, n, depth, rot=0.0, seed=5):
    """Contour du bord extérieur : festonné, dentelé, cranté ou ébréché."""
    d = R * max(0.0, depth) / 100.0
    n = max(3, n)
    rnd = random.Random(seed)
    ph = [rnd.uniform(0, 2 * math.pi) for _ in range(4)]
    chips = [(rnd.uniform(0, 2 * math.pi), rnd.uniform(0.05, 0.12), rnd.uniform(0.5, 1.0))
             for _ in range(5)]
    N = max(360, n * 24)
    pts = []
    for k in range(N):
        t = 2 * math.pi * k / N
        if kind == "feston":
            r = R - d * 0.5 * (1 - math.cos(n * t))
            r += d * 0.35 * (math.sin(3 * t + ph[0]) + 0.6 * math.sin(5 * t + ph[1])
                             + 0.4 * math.sin(7 * t + ph[2]))
        elif kind == "dents":
            r = R - d * abs(math.sin(n * t / 2)) ** 0.8
        elif kind == "crans":
            u = (n * t / (2 * math.pi)) % 1.0
            e = 0.06
            if u < e:
                f = u / e
            elif u < 0.5:
                f = 1.0
            elif u < 0.5 + e:
                f = 1 - (u - 0.5) / e
            else:
                f = 0.0
            r = R - d * (1 - f)
        else:   # ebreche
            r = R
            for a, w, amt in chips:
                da = abs((t - a + math.pi) % (2 * math.pi) - math.pi)
                if da < w:
                    r -= d * amt * (1 - (da / w) ** 2)
            r += d * 0.06 * math.sin(40 * t + ph[3])
        tt = t + math.radians(rot)
        pts.append((r * math.cos(tt), r * math.sin(tt)))
    return pts


def _draw_rope(c, e):
    r, w, col = e["r"], max(1.0, e["w"]), e["col"]
    dark = _darken(col, 0.4)
    c.new_path()
    c.set_line_width(w)
    c.set_source_rgba(*dark)
    c.arc(0, 0, r, 0, 2 * math.pi)
    c.stroke()
    n = max(12, int(2 * math.pi * r / (w * 0.55)))
    c.set_line_width(max(0.6, w * 0.09))
    for k in range(n):
        t = 2 * math.pi * k / n + math.radians(e["rot"])
        c.save()
        c.translate(r * math.cos(t), r * math.sin(t))
        c.rotate(t + math.pi / 2 + 0.8)
        c.scale(w * 0.62, w * 0.3)
        c.new_path()
        c.arc(0, 0, 1, 0, 2 * math.pi)
        c.restore()
        c.set_source_rgba(*col)
        c.fill_preserve()
        c.set_source_rgba(*dark)
        c.stroke()


def _draw_guilloche(c, e):
    r1, r2 = sorted((e["r1"], e["r2"]))
    c.save()
    c.new_path()
    c.arc(0, 0, r2, 0, 2 * math.pi)
    c.new_sub_path()
    c.arc(0, 0, max(0.1, r1), 0, 2 * math.pi)
    c.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
    c.clip()
    c.set_fill_rule(cairo.FILL_RULE_WINDING)
    rm, amp = (r1 + r2) / 2, (r2 - r1) * 0.65
    m = max(2, e["waves"])
    steps = m * 16
    c.set_line_width(max(0.3, e["w"]))
    c.set_source_rgba(*e["col"])
    off = math.radians(e["rot"])
    for k in range(max(1, e["n"])):
        phase = 2 * math.pi * k / max(1, e["n"])
        for sgn in (1, -1):
            c.new_path()
            for i in range(steps + 1):
                t = 2 * math.pi * i / steps
                rr = rm + amp * math.sin(sgn * m * t + phase)
                x, y = rr * math.cos(t + off), rr * math.sin(t + off)
                (c.move_to if i == 0 else c.line_to)(x, y)
            c.stroke()
    c.restore()


def _leaf(c, x, y, ang, L):
    c.save()
    c.translate(x, y)
    c.rotate(ang)
    c.move_to(0, 0)
    c.curve_to(L * 0.3, -L * 0.32, L * 0.75, -L * 0.22, L, 0)
    c.curve_to(L * 0.75, L * 0.22, L * 0.3, L * 0.32, 0, 0)
    c.close_path()
    c.restore()


def _draw_laurel(c, e):
    r, L, col = e["r"], max(2.0, e["size"]), e["col"]
    span, gap = max(e["gap"] / 2 + 10, e["span"]), e["gap"]
    rot = e["rot"]
    c.new_path()
    for side in (1, -1):
        a0, a1 = 90 + side * gap / 2, 90 + side * span
        length = r * math.radians(abs(a1 - a0))
        count = max(2, int(length / (L * 0.42)))
        for i in range(count):
            for half in (0.0, 0.5):
                u = (i + half) / count
                a = math.radians(a0 + (a1 - a0) * u + rot)
                dx, dy = -math.sin(a) * side, math.cos(a) * side
                ang = math.atan2(dy, dx)
                size = L * (1 - 0.45 * u)
                tilt = 0.75 if half == 0 else -0.75
                _leaf(c, r * math.cos(a), r * math.sin(a), ang + tilt, size)
    c.set_source_rgba(*col)
    c.fill()
    c.set_line_width(max(1.0, L * 0.08))
    c.set_line_cap(cairo.LINE_CAP_ROUND)
    for side in (1, -1):
        a0, a1 = math.radians(90 + side * gap / 2 + rot), math.radians(90 + side * span + rot)
        c.new_path()
        if side > 0:
            c.arc(0, 0, r, a0, a1)
        else:
            c.arc_negative(0, 0, r, a0, a1)
        c.stroke()


BANNER_STYLES = [("ruban", "Ruban (pointes fourchues)"), ("plaque", "Plaque")]
PEARL_STYLES = [("perle", "Perles"), ("rivet", "Rivets"), ("diamant", "Diamants")]


def _banner_parts(style, W, H, cy, curve, fill, rivets):
    """Polygones du bandeau (de l'arrière vers l'avant) + rivets."""
    parts, riv = [], []
    hw = W / 2
    if style == "plaque":
        rr = H * 0.22
        pts = []
        for cx_, cy_, a0 in ((hw - rr, cy - H / 2 + rr, -90), (hw - rr, cy + H / 2 - rr, 0),
                             (-hw + rr, cy + H / 2 - rr, 90), (-hw + rr, cy - H / 2 + rr, 180)):
            for k in range(10):
                a = math.radians(a0 + 9 * k)
                pts.append((cx_ + rr * math.cos(a), cy_ + rr * math.sin(a)))
        parts.append((pts, fill, True))
        if rivets:
            for sx in (-1, 1):
                for sy in (-1, 1):
                    riv.append((sx * (hw - H * 0.22), cy + sy * H * 0.28, H * 0.075))
        return {"parts": parts, "rivets": riv}
    # ruban : bande principale courbée, queues fourchues derrière, plis
    def edge_y(x, base):
        return base + curve * (x / hw) ** 2
    n = 40
    top = [(x, edge_y(x, cy - H / 2)) for x in (hw * (2 * k / n - 1) for k in range(n + 1))]
    bot = [(x, edge_y(x, cy + H / 2)) for x in (hw * (1 - 2 * k / n) for k in range(n + 1))]
    tail_col, fold_col = _darken(fill, 0.72), _darken(fill, 0.5)
    drop, out, inn = H * 0.38, H * 1.0, H * 0.55
    for sx in (-1, 1):
        yb = edge_y(hw, cy + H / 2)
        yt = yb - H + drop
        x_in, x_out = sx * (hw - inn), sx * (hw + out)
        tail = [(x_in, yt), (x_out, yt), (x_out - sx * H * 0.38, yt + H / 2),
                (x_out, yt + H), (x_in, yt + H)]
        parts.append((tail, tail_col, True))
        parts.append(([(sx * hw, yb), (sx * hw, yb + drop), (x_in, yb)], fold_col, False))
    parts.append((top + bot, fill, True))
    return {"parts": parts, "rivets": riv}


def _draw_banner(c, e):
    rot = math.radians(e["rot"])
    cr, sr = math.cos(rot), math.sin(rot)
    def tr(x, y):
        return x * cr - y * sr, x * sr + y * cr
    c.set_line_join(cairo.LINE_JOIN_ROUND)
    for pts, col, outline in e["parts"]:
        c.new_path()
        for i, (x, y) in enumerate(pts):
            (c.move_to if i == 0 else c.line_to)(*tr(x, y))
        c.close_path()
        c.set_source_rgba(*col)
        if outline and e["sw"] > 0 and e["stroke"][3] > 0:
            c.fill_preserve()
            c.set_line_width(e["sw"])
            c.set_source_rgba(*e["stroke"])
            c.stroke()
        else:
            c.fill()
    for x, y, r in e["rivets"]:
        _bead(c, *tr(x, y), r, e["stroke"], "rivet")


def _bead(c, x, y, r, col, style):
    """Une perle, un rivet ou un diamant, avec reflet."""
    if style == "rivet":
        c.new_path()
        c.arc(x, y, r, 0, 2 * math.pi)
        c.set_source_rgba(*_darken(col, 0.45))
        c.fill()
        r2 = r * 0.72
    else:
        r2 = r
    g = cairo.RadialGradient(x - r2 * 0.35, y - r2 * 0.35, r2 * 0.1, x, y, r2)
    if style == "diamant":
        g.add_color_stop_rgba(0, 1, 1, 1, 1)
        g.add_color_stop_rgba(0.6, *col)
        g.add_color_stop_rgba(1, *_darken(col, 0.55))
    else:
        g.add_color_stop_rgba(0, *_lerp(col, [1, 1, 1, col[3]], 0.7))
        g.add_color_stop_rgba(0.55, *col)
        g.add_color_stop_rgba(1, *_darken(col, 0.5))
    c.new_path()
    c.arc(x, y, r2, 0, 2 * math.pi)
    c.set_source(g)
    c.fill()
    if style == "diamant":
        c.set_source_rgba(1, 1, 1, 0.9)
        c.set_line_width(max(0.4, r * 0.12))
        for a in (0, math.pi / 2):
            c.new_path()
            c.move_to(x - r * 1.1 * math.cos(a), y - r * 1.1 * math.sin(a))
            c.line_to(x + r * 1.1 * math.cos(a), y + r * 1.1 * math.sin(a))
            c.stroke()


def _draw_pearls(c, e):
    n, r = max(1, e["n"]), e["r"]
    for k in range(n):
        t = 2 * math.pi * k / n + math.radians(e["rot"]) - math.pi / 2
        _bead(c, r * math.cos(t), r * math.sin(t), max(0.5, e["size"] / 2), e["col"], e["style"])


def _apply_texture(comp, kind, amount, scale, x0, y0, R, seed=11):
    """Texture sur tout le badge : métal brossé, cire, patine ou rouille."""
    if kind not in ("brosse", "cire", "patine", "rouille") or amount <= 0:
        return
    rnd = random.Random(seed)
    c = cairo.Context(comp)
    c.scale(scale, scale)
    c.translate(-x0, -y0)
    c.set_operator(cairo.OPERATOR_ATOP)
    if kind == "brosse":
        c.set_line_width(1.2 / max(scale, 0.05))
        r = 2.0
        while r < R * 1.15:
            light = rnd.random() < 0.5
            c.set_source_rgba(1 if light else 0, 1 if light else 0, 1 if light else 0,
                              amount * rnd.uniform(0.02, 0.12))
            c.new_path()
            c.arc(0, 0, r, 0, 2 * math.pi)
            c.stroke()
            r += max(1.0, 1.6 / max(scale, 0.05))
        return
    cols = {"cire": [((0, 0, 0), 0.22, 0.18), ((1, 1, 1), 0.18, 0.15)],
            "patine": [((0.12, 0.32, 0.3), 0.55, 0.12), ((0.05, 0.08, 0.05), 0.35, 0.05)],
            "rouille": [((0.55, 0.25, 0.08), 0.55, 0.1), ((0.2, 0.08, 0.02), 0.4, 0.04)]}[kind]
    for col, alpha, size in cols:
        for _ in range(70):
            rr = R * math.sqrt(rnd.random()) * 1.05
            t = rnd.uniform(0, 2 * math.pi)
            x, y = rr * math.cos(t), rr * math.sin(t)
            rb = R * size * rnd.uniform(0.3, 1.0)
            g = cairo.RadialGradient(x, y, 0, x, y, rb)
            g.add_color_stop_rgba(0, col[0], col[1], col[2], alpha * amount * rnd.uniform(0.4, 1))
            g.add_color_stop_rgba(1, col[0], col[1], col[2], 0)
            c.set_source(g)
            c.new_path()
            c.arc(x, y, rb, 0, 2 * math.pi)
            c.fill()


def _ring_path(c, e):
    c.new_path()
    if e.get("edge"):
        pts = e["edge"]
        c.move_to(*pts[0])
        for q in pts[1:]:
            c.line_to(*q)
        c.close_path()
    else:
        c.arc(0, 0, max(0.5, e["r"]), 0, 2 * math.pi)


def _draw_element(c, e):
    k = e["kind"]
    if k == "ring_fill":
        _ring_path(c, e)
        c.set_source_rgba(*e["fill"])
        c.fill()
    elif k == "ring_stroke":
        _ring_path(c, e)
        c.set_line_width(e["sw"])
        c.set_line_join(cairo.LINE_JOIN_ROUND)
        c.set_source_rgba(*e["stroke"])
        c.stroke()
    elif k == "rope":
        _draw_rope(c, e)
    elif k == "guil":
        _draw_guilloche(c, e)
    elif k == "laurel":
        _draw_laurel(c, e)
    elif k == "pearls":
        _draw_pearls(c, e)
    elif k == "banner":
        _draw_banner(c, e)
    elif k == "icon":
        _trace(c, e["polys"])
        c.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
        c.set_source_rgba(*e["col"])
        c.fill()
        c.set_fill_rule(cairo.FILL_RULE_WINDING)
    elif k == "arcs":
        c.set_line_width(e["w"])
        c.set_line_cap(cairo.LINE_CAP_ROUND)
        c.set_source_rgba(*e["col"])
        for a1, a2 in e["arcs"]:
            c.new_path()
            c.arc(0, 0, e["r"], math.radians(a1), math.radians(a2))
            c.stroke()
    else:
        _trace(c, e["polys"])
        c.set_fill_rule(cairo.FILL_RULE_WINDING)
        if e.get("sw", 0) > 0 and e["scol"][3] > 0:
            c.set_line_join(cairo.LINE_JOIN_ROUND)
            c.set_line_width(e["sw"] * 2)
            c.set_source_rgba(*e["scol"])
            c.stroke_preserve()
        c.set_source_rgba(*e["col"])
        c.fill()


def render_badge(g, p, scale=1.0):
    p = normalize(p)
    x0, y0, x1, y1 = badge_extents(g, p)
    W = max(1, int(math.ceil((x1 - x0) * scale)))
    H = max(1, int(math.ceil((y1 - y0) * scale)))
    comp = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    cc = cairo.Context(comp)

    def ctx_for(surf):
        c = cairo.Context(surf)
        c.scale(scale, scale)
        c.translate(-x0, -y0)
        return c

    metal = p["b_metal"] if p["b_metal"] in METALS else None
    scope = p["b_bev_scope"]
    for e in g["els"]:
        bevel = scope == "tout" or (scope == "textes" and e["kind"] in ("text", "motifs", "icon"))
        use_metal = metal and e.get("metal", True)
        if not use_metal and not bevel:
            _draw_element(ctx_for(comp), e)
            continue
        es = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
        _draw_element(ctx_for(es), e)
        if use_metal:
            er = g["ext"]
            _apply_metal(es, _gradient((-er, -er, er, er), 60, METALS[metal]), scale, x0, y0)
        if bevel:
            _bevel(es, p["b_bev_style"], p["b_bev_depth"] * scale, p["b_bev_soft"] * scale,
                   p["b_bev_angle"], p["b_bev_hi"], p["b_bev_sh"])
        cc.set_source_surface(es, 0, 0)
        cc.paint()

    _apply_texture(comp, p["b_tex"], p["b_tex_amount"], scale, x0, y0, g["R"])

    if p["b_sh_on"] and p["b_sh_col"][3] > 0:
        out = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
        _paint_shadow(out, comp, p["b_sh_col"], p["b_sh_dx"] * scale,
                      p["b_sh_dy"] * scale, p["b_sh_blur"] * scale)
        c = cairo.Context(out)
        c.set_source_surface(comp, 0, 0)
        c.paint()
        comp = out
    comp.flush()
    return comp, (x0, y0)


# --------------------------------------------------------------------------
# Mode texte sur chemin : formes SVG ou tracé de l'image
# --------------------------------------------------------------------------
PATH_DEFAULTS = {
    "path_src": "svg",             # svg / image (tracé sélectionné dans l'image)
    "path_file": "builtin:etoile.svg",
    "path_sub": 0,                 # contour suivi (0 = le plus long)
    "path_size": 600.0,            # taille de la forme (plus grande dimension, px)
    "path_rot": 0.0,               # rotation de la forme (°)
    "path_pos": 0.0,               # centre du texte le long du chemin (%)
    "path_side": "dessus",         # dessus / centre / dessous
    "path_offset": 4.0,            # écart texte / chemin (px)
    "path_reverse": False,         # inverser le sens (texte de l'autre côté)
    "path_fit": 0.0,               # remplir x % du chemin (0 = naturel)
    "path_repeat": False,          # répéter le texte pour faire le tour
    "path_sep": " • ",
    "path_rigid": True,            # lettres rigides (sinon courbées avec le chemin)
    "path_show": True,             # dessiner aussi la forme
    "path_fill": [0.44, 0.62, 0.82, 0.0],
    "path_stroke": [0.23, 0.37, 0.54, 1.0],
    "path_sw": 3.0,
}
DEFAULTS.update(PATH_DEFAULTS)
PATH_KEYS = set(PATH_DEFAULTS)
PATH_SIDES = [("dessus", "Au-dessus (à l'extérieur)"), ("centre", "Centré sur le chemin"),
              ("dessous", "En dessous (à l'intérieur)")]

# Dossiers des formes : "builtin" = fournies avec le greffon, "user" = vos SVG
SHAPE_DIRS = {"builtin": os.path.join(os.path.dirname(os.path.abspath(__file__)), "formes"),
              "user": None}
# Fonction fournie par le greffon : renvoie [(points, fermé), ...] du tracé de l'image
image_path_provider = None

_NUM = r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?"


def _mat_mul(a, b):
    return (a[0] * b[0] + a[2] * b[1], a[1] * b[0] + a[3] * b[1],
            a[0] * b[2] + a[2] * b[3], a[1] * b[2] + a[3] * b[3],
            a[0] * b[4] + a[2] * b[5] + a[4], a[1] * b[4] + a[3] * b[5] + a[5])


def _parse_transform(s):
    m = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    for name, args in re.findall(r"(\w+)\s*\(([^)]*)\)", s or ""):
        v = [float(x) for x in re.findall(_NUM, args)]
        t = None
        if name == "matrix" and len(v) == 6:
            t = tuple(v)
        elif name == "translate" and v:
            t = (1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0)
        elif name == "scale" and v:
            t = (v[0], 0, 0, v[1] if len(v) > 1 else v[0], 0, 0)
        elif name == "rotate" and v:
            a = math.radians(v[0])
            c, sn = math.cos(a), math.sin(a)
            t = (c, sn, -sn, c, 0, 0)
            if len(v) == 3:
                t = _mat_mul(_mat_mul((1, 0, 0, 1, v[1], v[2]), t), (1, 0, 0, 1, -v[1], -v[2]))
        elif name == "skewX" and v:
            t = (1, 0, math.tan(math.radians(v[0])), 1, 0, 0)
        elif name == "skewY" and v:
            t = (1, math.tan(math.radians(v[0])), 0, 1, 0, 0)
        if t:
            m = _mat_mul(m, t)
    return m


def _arc_points(x1, y1, rx, ry, phi, fa, fs, x2, y2):
    """Arc elliptique SVG (notation « A ») -> points (algorithme de la norme SVG)."""
    if rx == 0 or ry == 0:
        return [(x2, y2)]
    rx, ry = abs(rx), abs(ry)
    cp, sp = math.cos(math.radians(phi)), math.sin(math.radians(phi))
    dx, dy = (x1 - x2) / 2, (y1 - y2) / 2
    x1p, y1p = cp * dx + sp * dy, -sp * dx + cp * dy
    lam = (x1p / rx) ** 2 + (y1p / ry) ** 2
    if lam > 1:
        rx, ry = rx * math.sqrt(lam), ry * math.sqrt(lam)
    num = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p
    den = rx * rx * y1p * y1p + ry * ry * x1p * x1p
    co = math.sqrt(max(0.0, num / den)) if den else 0.0
    if fa == fs:
        co = -co
    cxp, cyp = co * rx * y1p / ry, -co * ry * x1p / rx
    cx = cp * cxp - sp * cyp + (x1 + x2) / 2
    cy = sp * cxp + cp * cyp + (y1 + y2) / 2

    def ang(ux, uy, vx, vy):
        a = math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
        return a
    t1 = ang(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    dt = ang((x1p - cxp) / rx, (y1p - cyp) / ry, (-x1p - cxp) / rx, (-y1p - cyp) / ry)
    if not fs and dt > 0:
        dt -= 2 * math.pi
    elif fs and dt < 0:
        dt += 2 * math.pi
    n = max(6, int(abs(dt) / (math.pi / 36)))
    out = []
    for i in range(1, n + 1):
        t = t1 + dt * i / n
        x, y = rx * math.cos(t), ry * math.sin(t)
        out.append((cp * x - sp * y + cx, sp * x + cp * y + cy))
    return out


def _parse_path_d(d):
    toks = re.findall(r"[A-Za-z]|" + _NUM, d or "")
    subs, cur, closed = [], [], False
    i, cmd = 0, None
    x = y = sx = sy = 0.0
    lcx = lcy = None      # dernier point de contrôle (S, T)
    prev = None

    def num():
        nonlocal i
        v = float(toks[i])
        i += 1
        return v

    def flag():
        nonlocal i
        t = toks[i]
        if len(t) > 1 and t[0] in "01" and "." not in t:
            toks[i] = t[1:]
            return t[0] == "1"
        i += 1
        return float(t) != 0

    def finish():
        nonlocal cur, closed
        if len(cur) > 1:
            subs.append((cur, closed))
        cur, closed = [], False

    while i < len(toks):
        if re.match(r"[A-Za-z]", toks[i]):
            cmd = toks[i]
            i += 1
            if cmd in "Zz":
                closed = True
                x, y = sx, sy
                finish()
                prev = cmd
                continue
        if cmd is None:
            break
        rel = cmd.islower()
        c = cmd.upper()
        ox, oy = (x, y) if rel else (0.0, 0.0)
        try:
            if c == "M":
                finish()
                x, y = ox + num(), oy + num()
                sx, sy = x, y
                cur = [(x, y)]
                cmd = "l" if rel else "L"      # coordonnées suivantes = lignes
            elif c == "L":
                x, y = ox + num(), oy + num()
                cur.append((x, y))
            elif c == "H":
                x = ox + num()
                cur.append((x, y))
            elif c == "V":
                y = oy + num()
                cur.append((x, y))
            elif c in "CS":
                if c == "C":
                    x1, y1 = ox + num(), oy + num()
                else:
                    if prev and prev.upper() in "CS" and lcx is not None:
                        x1, y1 = 2 * x - lcx, 2 * y - lcy
                    else:
                        x1, y1 = x, y
                x2, y2 = ox + num(), oy + num()
                x3, y3 = ox + num(), oy + num()
                for k in range(1, 21):
                    t = k / 20
                    mt = 1 - t
                    cur.append((mt ** 3 * x + 3 * mt * mt * t * x1 + 3 * mt * t * t * x2 + t ** 3 * x3,
                                mt ** 3 * y + 3 * mt * mt * t * y1 + 3 * mt * t * t * y2 + t ** 3 * y3))
                lcx, lcy = x2, y2
                x, y = x3, y3
            elif c in "QT":
                if c == "Q":
                    x1, y1 = ox + num(), oy + num()
                else:
                    if prev and prev.upper() in "QT" and lcx is not None:
                        x1, y1 = 2 * x - lcx, 2 * y - lcy
                    else:
                        x1, y1 = x, y
                x2, y2 = ox + num(), oy + num()
                for k in range(1, 17):
                    t = k / 16
                    mt = 1 - t
                    cur.append((mt * mt * x + 2 * mt * t * x1 + t * t * x2,
                                mt * mt * y + 2 * mt * t * y1 + t * t * y2))
                lcx, lcy = x1, y1
                x, y = x2, y2
            elif c == "A":
                rx, ry, phi = num(), num(), num()
                fa, fs = flag(), flag()
                x2, y2 = ox + num(), oy + num()
                cur += _arc_points(x, y, rx, ry, phi, fa, fs, x2, y2)
                x, y = x2, y2
            else:
                i += 1
        except (IndexError, ValueError):
            break
        if c not in "CSQT":
            lcx = lcy = None
        prev = cmd
    finish()
    return subs


def _ellipse(cx, cy, rx, ry, n=120):
    return [(cx + rx * math.cos(2 * math.pi * k / n), cy + ry * math.sin(2 * math.pi * k / n))
            for k in range(n)]


def parse_svg(filename):
    """Lit un fichier SVG -> [(points, fermé), ...] (formes simples et chemins)."""
    import xml.etree.ElementTree as ET
    root = ET.parse(filename).getroot()
    out = []

    def f(el, name, default=0.0):
        try:
            return float(re.findall(_NUM, el.get(name, str(default)))[0])
        except (IndexError, ValueError):
            return default

    def walk(el, m):
        tag = el.tag.split("}")[-1]
        if tag in ("defs", "clipPath", "mask", "symbol", "metadata", "style", "title", "desc"):
            return
        m = _mat_mul(m, _parse_transform(el.get("transform")))
        subs = []
        if tag == "path":
            subs = _parse_path_d(el.get("d"))
        elif tag in ("polygon", "polyline"):
            v = [float(n) for n in re.findall(_NUM, el.get("points", ""))]
            pts = list(zip(v[0::2], v[1::2]))
            if len(pts) > 1:
                subs = [(pts, tag == "polygon")]
        elif tag == "rect":
            x0, y0, w, h = f(el, "x"), f(el, "y"), f(el, "width"), f(el, "height")
            if w > 0 and h > 0:
                subs = [([(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)], True)]
        elif tag == "circle":
            r = f(el, "r")
            if r > 0:
                subs = [(_ellipse(f(el, "cx"), f(el, "cy"), r, r), True)]
        elif tag == "ellipse":
            rx, ry = f(el, "rx"), f(el, "ry")
            if rx > 0 and ry > 0:
                subs = [(_ellipse(f(el, "cx"), f(el, "cy"), rx, ry), True)]
        elif tag == "line":
            subs = [([(f(el, "x1"), f(el, "y1")), (f(el, "x2"), f(el, "y2"))], False)]
        for pts, closed in subs:
            out.append(([(m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]) for x, y in pts],
                        closed))
        for child in el:
            walk(child, m)

    walk(root, (1.0, 0.0, 0.0, 1.0, 0.0, 0.0))
    return out


def resolve_shape(ref):
    """'builtin:nom.svg', 'user:nom.svg' ou chemin complet -> chemin du fichier."""
    if ref.startswith("builtin:"):
        return os.path.join(SHAPE_DIRS["builtin"], ref[8:])
    if ref.startswith("user:") and SHAPE_DIRS.get("user"):
        return os.path.join(SHAPE_DIRS["user"], ref[5:])
    return ref


BUILTIN_NAMES = {"etoile.svg": "Étoile", "coeur.svg": "Cœur", "fleche.svg": "Flèche",
                 "maison.svg": "Maison", "fleur.svg": "Fleur", "spirale.svg": "Spirale",
                 "croix.svg": "Croix", "cercle.svg": "Cercle", "ovale.svg": "Ovale",
                 "vague.svg": "Vague", "arche.svg": "Arche", "bulle.svg": "Bulle",
                 "bouclier.svg": "Bouclier"}


def list_shapes():
    """[(référence, libellé)] : formes fournies puis vos formes."""
    out = []
    order = list(BUILTIN_NAMES)
    d = SHAPE_DIRS["builtin"]
    if os.path.isdir(d):
        files = sorted((f for f in os.listdir(d) if f.lower().endswith(".svg")),
                       key=lambda f: (order.index(f) if f in order else 99, f))
        out += [("builtin:" + f, BUILTIN_NAMES.get(f, os.path.splitext(f)[0])) for f in files]
    d = SHAPE_DIRS.get("user")
    if d and os.path.isdir(d):
        out += [("user:" + f, "★ " + os.path.splitext(f)[0])
                for f in sorted(os.listdir(d)) if f.lower().endswith(".svg")]
    return out


_SVG_CACHE = {}


def load_shape(ref):
    fn = resolve_shape(ref)
    key = (fn, os.path.getmtime(fn) if os.path.exists(fn) else 0)
    if key not in _SVG_CACHE:
        _SVG_CACHE[key] = parse_svg(fn)
    return _SVG_CACHE[key]


def _plen(pts, closed):
    n = len(pts)
    m = n if closed else n - 1
    return sum(math.hypot(pts[(k + 1) % n][0] - pts[k][0], pts[(k + 1) % n][1] - pts[k][1])
               for k in range(m))


def _area(pts):
    n = len(pts)
    return sum(pts[k][0] * pts[(k + 1) % n][1] - pts[(k + 1) % n][0] * pts[k][1]
               for k in range(n)) / 2


class _Track:
    """Chemin paramétré par la longueur (points interpolés, prolongé aux bouts)."""

    def __init__(self, pts, closed):
        if closed:
            pts = pts + [pts[0]]
        self.x = [p[0] for p in pts]
        self.y = [p[1] for p in pts]
        self.cum = [0.0]
        for k in range(1, len(pts)):
            self.cum.append(self.cum[-1] + math.hypot(self.x[k] - self.x[k - 1],
                                                      self.y[k] - self.y[k - 1]))
        self.L = max(self.cum[-1], 1e-6)
        self.closed = closed

    def at(self, s):
        import bisect
        n = len(self.cum)
        if self.closed:
            s %= self.L
        elif s < 0 or s > self.L:
            k = 0 if s < 0 else n - 2
            dx, dy = self.x[k + 1] - self.x[k], self.y[k + 1] - self.y[k]
            d = math.hypot(dx, dy) or 1.0
            bx, by, base = (self.x[0], self.y[0], 0.0) if s < 0 else (self.x[-1], self.y[-1], self.L)
            return bx + dx / d * (s - base), by + dy / d * (s - base)
        k = min(max(bisect.bisect_right(self.cum, s) - 1, 0), n - 2)
        seg = (self.cum[k + 1] - self.cum[k]) or 1e-9
        t = (s - self.cum[k]) / seg
        return (self.x[k] + (self.x[k + 1] - self.x[k]) * t,
                self.y[k] + (self.y[k + 1] - self.y[k]) * t)


def _glyph_groups(polys):
    """Regroupe les contours par lettre (chevauchement horizontal)."""
    items = sorted(((min(x for x, _ in q), max(x for x, _ in q), q) for q in polys),
                   key=lambda t: t[0])
    groups = []
    for x0, x1, q in items:
        if groups and x0 < groups[-1][1] - 0.5:
            g = groups[-1]
            groups[-1] = (g[0], max(g[1], x1), g[2] + [q])
        else:
            groups.append((x0, x1, [q]))
    return groups


def path_shapes(p):
    """Contours de la forme (déjà mis à l'échelle), et contour suivi par le texte."""
    if p["path_src"] == "image":
        if image_path_provider is None:
            raise ValueError("aucun tracé disponible")
        subs = image_path_provider()
        if not subs:
            raise ValueError("aucun tracé dans l'image : dessinez-en un avec l'outil Chemins")
        bb = _bbox([s[0] for s in subs])
        cx, cy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
        subs = [(_rotate([pts], p["path_rot"], cx, cy)[0], c) for pts, c in subs]
    else:
        subs = load_shape(p["path_file"])
        if not subs:
            raise ValueError("aucun contour lisible dans ce SVG")
        bb = _bbox([s[0] for s in subs])
        cx, cy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
        k = max(10.0, p["path_size"]) / max(bb[2] - bb[0], bb[3] - bb[1], 1e-6)
        subs = [(_rotate([[((x - cx) * k, (y - cy) * k) for x, y in pts]], p["path_rot"])[0], c)
                for pts, c in subs]
    idx = int(p["path_sub"])
    if 1 <= idx <= len(subs):
        main = subs[idx - 1]
    else:
        main = max(subs, key=lambda s: _plen(s[0], s[1]))
    return subs, main


def path_geometry(p):
    p = normalize(p)
    subs, (pts, closed) = path_shapes(p)
    # nettoyage + orientation : sens horaire, départ en haut au centre
    clean = [pts[0]]
    for q in pts[1:]:
        if math.hypot(q[0] - clean[-1][0], q[1] - clean[-1][1]) > 1e-6:
            clean.append(q)
    if closed and len(clean) > 2 and math.hypot(clean[0][0] - clean[-1][0],
                                                 clean[0][1] - clean[-1][1]) < 1e-6:
        clean.pop()
    pts = clean
    if closed and len(pts) > 2:
        if _area(pts) < 0:
            pts = pts[::-1]
        bx0, by0, bx1, by1 = _bbox([pts])
        top = min(range(len(pts)), key=lambda k: math.hypot(pts[k][0] - (bx0 + bx1) / 2,
                                                               (pts[k][1] - by0) * 3))
        pts = pts[top:] + pts[:top]
    if p["path_reverse"]:
        pts = [pts[0]] + pts[:0:-1] if closed else pts[::-1]
    track = _Track(pts, closed and len(pts) > 2)
    L = track.L

    # texte sur une ligne
    kx = max(5.0, p["width"]) / 100.0
    text = " ".join((p["text"] or "").split("\n")).strip() or " "
    tp = _text_params(text, p["font"], p["size"], p["spacing"])
    fit = p["path_fit"]
    if p["path_repeat"] and track.closed:
        unit = text + p["path_sep"]
        pu, inku, _ = _text_polygons(dict(tp, text=unit))
        wu = max(1.0, (inku[2] if pu else p["size"]) * kx + p["size"] * 0.25)
        tp["text"] = unit * max(1, int(L / wu))
        fit = 100.0
    if fit > 0:
        polys0, ink0, _ = _text_polygons(dict(tp, spacing=0.0))
        if polys0:
            target = L * min(fit, 100.0) / 100.0 / kx
            n = max(1, len(tp["text"]) - (0 if p["path_repeat"] else 1))
            tp["spacing"] = max((target - ink0[2]) / n, -tp["size"] * 0.4)
    polys, ink, logical = _text_polygons(tp)
    shape_bbox = _bbox([s[0] for s in subs])
    if not polys:
        return {"polys": [], "tbbox": shape_bbox, "subs": subs, "sbbox": shape_bbox}
    x0 = ink[0]
    y0, h = logical[1], max(1.0, logical[3])
    base = {"dessus": y0 + 0.78 * h, "centre": y0 + 0.52 * h,
            "dessous": y0 + 0.22 * h}.get(p["path_side"], y0 + 0.78 * h)
    off = p["path_offset"] * (1 if p["path_side"] != "dessous" else -1)
    wtext = ink[2] * kx
    if p["path_repeat"] and track.closed:
        s0 = p["path_pos"] / 100.0 * L
    else:
        s0 = p["path_pos"] / 100.0 * L - wtext / 2

    out = []
    if p["path_rigid"]:
        for gx0, gx1, group in _glyph_groups(polys):
            cxg = (gx0 + gx1) / 2
            hw = max((gx1 - gx0) / 2 * kx, h * 0.2)
            sc = s0 + (cxg - x0) * kx
            ax, ay = track.at(sc - hw)
            bx, by = track.at(sc + hw)
            th = math.atan2(by - ay, bx - ax)
            c, sn = math.cos(th), math.sin(th)
            px, py = track.at(sc)
            for q in group:
                pts2 = []
                for x, y in _subdivide(q, max(0.5, h / 30.0)):
                    lx, ly = (x - cxg) * kx, base - y + off
                    pts2.append((px + lx * c + ly * sn, py + lx * sn - ly * c))
                out.append(pts2)
    else:
        d = max(0.5, h * 0.05)
        for q in polys:
            pts2 = []
            for x, y in _subdivide(q, max(0.5, h / 40.0)):
                s = s0 + (x - x0) * kx
                ax, ay = track.at(s - d)
                bx, by = track.at(s + d)
                th = math.atan2(by - ay, bx - ax)
                px, py = track.at(s)
                ly = base - y + off
                pts2.append((px + ly * math.sin(th), py - ly * math.cos(th)))
            out.append(pts2)
    return {"polys": out, "tbbox": _bbox(out), "subs": subs, "sbbox": shape_bbox}


def _draw_shape(c, subs, p):
    fill, stroke, sw = p["path_fill"], p["path_stroke"], p["path_sw"]
    closed = [s for s in subs if s[1]]
    if closed and fill[3] > 0:
        c.new_path()
        for pts, _ in closed:
            c.move_to(*pts[0])
            for q in pts[1:]:
                c.line_to(*q)
            c.close_path()
        c.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
        c.set_source_rgba(*fill)
        c.fill()
        c.set_fill_rule(cairo.FILL_RULE_WINDING)
    if sw > 0 and stroke[3] > 0:
        c.set_line_width(sw)
        c.set_line_join(cairo.LINE_JOIN_ROUND)
        c.set_line_cap(cairo.LINE_CAP_ROUND)
        c.set_source_rgba(*stroke)
        for pts, cl in subs:
            c.new_path()
            c.move_to(*pts[0])
            for q in pts[1:]:
                c.line_to(*q)
            if cl:
                c.close_path()
            c.stroke()


def path_extents(g, p):
    x0, y0, x1, y1 = extents(g["tbbox"], p)
    if p["path_show"]:
        e = p["path_sw"] / 2 + 2
        sb = g["sbbox"]
        x0, y0 = min(x0, sb[0] - e), min(y0, sb[1] - e)
        x1, y1 = max(x1, sb[2] + e), max(y1, sb[3] + e)
    return math.floor(x0), math.floor(y0), math.ceil(x1), math.ceil(y1)


# --------------------------------------------------------------------------
# Mode texte dans une forme : mise en page du texte à l'intérieur d'un SVG
# --------------------------------------------------------------------------
INSIDE_DEFAULTS = {
    "in_align": "centre",          # gauche / centre / droite / justifie
    "in_valign": "centre",         # haut / centre
    "in_auto": True,               # taille ajustée pour remplir la forme
    "in_margin": 12.0,             # marge intérieure (px)
    "in_split": True,              # remplir les deux côtés d'un creux (haut du cœur…)
    "in_breaks": "continu",       # continu : lignes vides = paragraphes ; vers : chaque ligne
    "in_zones": "toutes",          # toutes / large / gauche / droite
    "in_where": "dans",            # dans : à l'intérieur ; hors : autour de la forme
    "in_frame_w": 250.0,           # hors : largeur du cadre (% de la forme)
    "in_frame_h": 150.0,           # hors : hauteur du cadre (% de la forme)
}
DEFAULTS.update(INSIDE_DEFAULTS)
INSIDE_KEYS = set(INSIDE_DEFAULTS)
INSIDE_BREAKS = [("continu", "Texte continu (lignes vides = paragraphes)"),
                 ("vers", "Respecter chaque retour à la ligne (vers)")]
INSIDE_ZONES = [("toutes", "Toutes (des deux côtés)"), ("large", "La plus large"),
                ("gauche", "À gauche seulement"), ("droite", "À droite seulement")]
INSIDE_WHERE = [("dans", "À l'intérieur de la forme"),
                ("hors", "À l'extérieur (le texte contourne la forme)")]
INSIDE_ALIGNS = [("gauche", "À gauche"), ("centre", "Centré"), ("droite", "À droite"),
                 ("justifie", "Justifié")]


def _scan(edges, y):
    """Intervalles [x0, x1] à l'intérieur des contours sur la ligne horizontale y."""
    xs = []
    for x1, y1, x2, y2 in edges:
        if (y1 <= y < y2) or (y2 <= y < y1):
            xs.append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
    xs.sort()
    return [(xs[k], xs[k + 1]) for k in range(0, len(xs) - 1, 2)]


def _inter(a, b):
    out, i, j = [], 0, 0
    while i < len(a) and j < len(b):
        lo, hi = max(a[i][0], b[j][0]), min(a[i][1], b[j][1])
        if lo < hi:
            out.append((lo, hi))
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return out


def _band(edges, yt, yb, margin):
    """Intervalles libres pour toute la hauteur d'une ligne (marge comprise)."""
    ys = [yt - margin, yt, yt + (yb - yt) * 0.25, (yt + yb) / 2, yt + (yb - yt) * 0.75, yb,
          yb + margin]
    cur = None
    for y in ys:
        iv = _scan(edges, y)
        cur = iv if cur is None else _inter(cur, iv)
        if not cur:
            return []
    return [(a + margin, b - margin) for a, b in cur if b - a > 2 * margin]


def _union(iv):
    iv = sorted(iv)
    out = []
    for a, b in iv:
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def _band_outside(edges, yt, yb, margin, fx0, fx1):
    """Intervalles libres hors de la forme (marge comprise), dans le cadre [fx0, fx1]."""
    ys = [yt - margin, yt, yt + (yb - yt) * 0.25, (yt + yb) / 2, yt + (yb - yt) * 0.75, yb,
          yb + margin]
    busy = []
    for y in ys:
        busy += [(a - margin, b + margin) for a, b in _scan(edges, y)]
    free, x = [], fx0
    for a, b in _union(busy):
        if a > x:
            free.append((x, min(a, fx1)))
        x = max(x, b)
        if x >= fx1:
            break
    if x < fx1:
        free.append((x, fx1))
    return [(a, b) for a, b in free if b - a > 1]


def _word_outlines(p, words):
    """Contours de chaque mot, mesurés en une seule mise en page (un mot par ligne)."""
    tp = _text_params("\n".join(words), p["font"], p["size"], p["spacing"])
    tp["align"] = "left"
    polys, ink, logical = _text_polygons(tp)
    n = len(words)
    lh = max(1.0, logical[3] / max(1, n))
    y0 = logical[1]
    per = [[] for _ in words]
    for q in polys:
        cy = (min(y for _, y in q) + max(y for _, y in q)) / 2
        k = min(n - 1, max(0, int((cy - y0) / lh)))
        per[k].append(q)
    out = []
    for k, qs in enumerate(per):
        if qs:
            bx0, _, bx1, _ = _bbox(qs)
            top = y0 + k * lh
            out.append(([[(x - bx0, y - top) for x, y in q] for q in qs], bx1 - bx0))
        else:
            out.append(([], p["size"] * 0.3))
    return out, lh


def _layout_inside(edges, top, bottom, words, widths, breaks, lh, space, s, p, start,
                   frame=None):
    """Place les mots ligne par ligne. Renvoie (placements, nb placés, bas du texte)."""
    margin = p["in_margin"]
    line_h = lh * s
    step = line_h * max(0.5, p["line_spacing"])
    y = start
    i, n = 0, len(words)
    placed, last_bottom, first_top = [], None, None
    while i < n and y + line_h <= bottom + 1e-6:
        if frame is None:
            segs = _band(edges, y, y + line_h, margin)
        else:
            segs = _band_outside(edges, y, y + line_h, margin, frame[0], frame[1])
        zones = p["in_zones"]
        if zones == "toutes" and not p["in_split"]:
            zones = "large"          # compatibilité avec les anciens réglages
        if segs and zones == "large":
            segs = [max(segs, key=lambda sg: sg[1] - sg[0])]
        elif segs and zones == "gauche":
            segs = segs[:1]
        elif segs and zones == "droite":
            segs = segs[-1:]
        line_items = []
        for sx0, sx1 in segs:
            if i >= n:
                break
            seg_words, width = [], 0.0
            while i < n:
                w = widths[i] * s
                need = w if not seg_words else width + space * s + w
                if need <= sx1 - sx0 + 1e-6:
                    seg_words.append(i)
                    width = need
                    i += 1
                    if i in breaks:
                        break
                else:
                    break
            if seg_words:
                line_items.append((sx0, sx1, seg_words, width))
            if i in breaks and seg_words:
                break
        for sx0, sx1, seg_words, width in line_items:
            free = (sx1 - sx0) - width
            gap = space * s
            last_of_par = seg_words[-1] + 1 in breaks or seg_words[-1] + 1 >= n
            align = p["in_align"]
            if align == "justifie":
                # justification limitée : au-delà de 3 espaces entre deux mots, la
                # ligne reste en partie non justifiée (pas de « rivières » de blanc)
                if len(seg_words) > 1 and not last_of_par:
                    gap += min(free / (len(seg_words) - 1), space * s * 2.0)
                x = sx0
            elif align == "gauche":
                x = sx0
            elif align == "droite":
                x = sx0 + free
            else:
                x = sx0 + free / 2
            for k in seg_words:
                placed.append((k, x, y))
                x += widths[k] * s + gap
        if line_items:
            first_top = y if first_top is None else first_top
            last_bottom = y + line_h
        elif i < n and i in breaks and placed and placed[-1][0] == i - 1:
            pass
        y += step
    return placed, i, first_top, last_bottom


def inside_geometry(p):
    p = normalize(p)
    subs, _ = path_shapes(p)
    closed = [s for s in subs if s[1]] or subs
    edges = []
    for pts, _ in closed:
        m = len(pts)
        for k in range(m):
            x1, y1 = pts[k]
            x2, y2 = pts[(k + 1) % m]
            if y1 != y2:
                edges.append((x1, y1, x2, y2))
    sb = _bbox([s[0] for s in subs])
    empty = {"polys": [], "tbbox": sb, "subs": subs, "sbbox": sb, "missing": 0, "scale": 1.0}

    # mots et fins de paragraphe
    words, breaks = [], set()
    text = p["text"] or ""
    if p["in_breaks"] == "continu":
        # un retour simple devient une espace ; une ligne vide sépare les paragraphes
        text = "\n".join(" ".join(b.split("\n")) for b in re.split(r"\n\s*\n", text))
    for par in text.split("\n"):
        ws = par.split()
        if ws:
            words += ws
            breaks.add(len(words))
    if not words:
        return empty
    uniq = list(dict.fromkeys(words))
    outl, lh = _word_outlines(p, uniq)
    kx = max(5.0, p["width"]) / 100.0
    idx = {w: k for k, w in enumerate(uniq)}
    widths = [outl[idx[w]][1] * kx for w in words]
    space = p["size"] * 0.33 * kx + p["spacing"]
    frame = None
    top, bottom = sb[1], sb[3]
    if p["in_where"] == "hors":
        cx, cy = (sb[0] + sb[2]) / 2, (sb[1] + sb[3]) / 2
        hw = (sb[2] - sb[0]) / 2 * max(100.0, p["in_frame_w"]) / 100.0
        hh = (sb[3] - sb[1]) / 2 * max(100.0, p["in_frame_h"]) / 100.0
        frame = (cx - hw, cx + hw)
        top, bottom = cy - hh, cy + hh

    def run(s, start):
        return _layout_inside(edges, top, bottom, words, widths, breaks, lh, space, s, p,
                              start, frame)

    s = 1.0
    if p["in_auto"]:
        lo, hi = 0.02, 1.0
        while run(hi, top)[1] >= len(words) and hi < 64:
            lo, hi = hi, hi * 2
        for _ in range(22):
            mid = (lo + hi) / 2
            if run(mid, top)[1] >= len(words):
                lo = mid
            else:
                hi = mid
        s = lo
    placed, count, ftop, fbot = run(s, top)
    if p["in_valign"] == "centre" and fbot is not None:
        best = (placed, count)
        shift = 0.0
        for _ in range(4):
            free = bottom - fbot
            if free <= 1:
                break
            shift += free / 2
            pl2, c2, ft2, fb2 = run(s, top + shift)
            if c2 < count:
                break
            best, fbot = (pl2, c2), fb2
        placed, count = best

    out = []
    for k, x, y in placed:
        qs = outl[idx[words[k]]][0]
        for q in qs:
            out.append([(x + qx * s * kx, y + qy * s) for qx, qy in q])
    return {"polys": out, "tbbox": _bbox(out) if out else sb, "subs": subs, "sbbox": sb,
            "missing": len(words) - count, "scale": s, "size": p["size"] * s}


# --------------------------------------------------------------------------
# Interface commune aux quatre modes
# --------------------------------------------------------------------------
def prepare(p):
    """Géométrie pleine taille : {'mode', 'polys', 'bbox', 'ext', ...}."""
    p = normalize(p)
    if p["mode"] == "badge":
        g = badge_geometry(p)
        e = g["ext"]
        return {"mode": "badge", "g": g, "polys": g["polys"], "bbox": (-e, -e, e, e),
                "ext": badge_extents(g, p), "R": g["R"]}
    if p["mode"] in ("chemin", "interieur"):
        g = path_geometry(p) if p["mode"] == "chemin" else inside_geometry(p)
        return {"mode": p["mode"], "g": g, "polys": g["polys"], "bbox": g["sbbox"],
                "ext": path_extents(g, p)}
    polys, bbox = geometry(p)
    return {"mode": "texte", "polys": polys, "bbox": bbox, "ext": extents(bbox, p)}


def draw(prep, p, scale=1.0):
    """Renvoie (surface, origine) pour une géométrie issue de prepare()."""
    if prep["mode"] == "badge":
        return render_badge(prep["g"], p, scale)
    if prep["mode"] in ("chemin", "interieur"):
        g = prep["g"]
        p = normalize(p)
        under = (lambda c: _draw_shape(c, g["subs"], p)) if p["path_show"] else None
        return render(g["polys"], g["tbbox"], p, scale, ext=path_extents(g, p), underlay=under)
    return render(prep["polys"], prep["bbox"], p, scale)


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
    # --- modèles inspirés des réalisations de la chaîne ---
    ("Cercle orange", dict(shape="cercle", fill_mode="gradient", fill1=_c("f7a531"),
                           fill2=_c("d9651e"), grad_angle=45, outline_w=0, shadow=False,
                           extrude=0)),
    ("Bloc 3D", dict(shape="droit", rot_y=-30, persp=1.6, fill_mode="solid",
                     fill1=_c("1b8a3a"), outline_w=0, extrude=7, extrude_angle=180,
                     extrude_col=_c("e01010"), shadow=False)),
    ("Double arche", dict(shape="arc_haut", arc=70, lines_sep=True, line_gap=10,
                          grow_center=35, fill_mode="solid", fill1=_c("ffffff"),
                          outline_w=0, shadow=True, shadow_dx=3, shadow_dy=5,
                          shadow_blur=6, shadow_col=_c("000000", 0.45), extrude=0)),
    ("Or estampé", dict(shape="droit", fill_mode="metal_or", grad_angle=70,
                        bevel="relief", bevel_depth=4, bevel_soft=2, outline_w=2,
                        outline_col=_c("6b4a00"), shadow=True, shadow_dx=4, shadow_dy=5,
                        shadow_blur=5, shadow_col=_c("000000", 0.4), extrude=0)),
]
CONTENT_KEYS = {"text", "font", "size", "spacing", "line_spacing", "align"}
PRESET_KEYS = set(DEFAULTS) - CONTENT_KEYS - BADGE_KEYS - PATH_KEYS - INSIDE_KEYS - {"mode"}


def _rings(*rings):
    """rings : (n°, visible, rayon %, fond, épaisseur contour, couleur contour)."""
    d = {}
    for r in rings:
        d.update(_ring_defaults(*r))
    return d


INK = _c("333333")
BADGE_PRESETS = [
    ("Club (deux anneaux)", dict(
        _rings((1, True, 100, _c("1f6f3a"), 6, WHITE), (2, True, 64, _c("d42a20"), 5, WHITE),
               (3, False, 90, NONE, 3, WHITE), (4, False, 50, NONE, 3, WHITE)),
        b_top_text="NOM DU CLUB", b_top_size=56, b_top_col=WHITE, b_top_r=82, b_top_fit=150,
        b_bot_text="VILLE", b_bot_size=56, b_bot_col=WHITE, b_bot_r=82, b_bot_sp=6,
        b_sel_on=True, b_sel_r=62)),
    ("Citation sur photo", dict(
        _rings((1, False, 100, NONE, 0, WHITE), (2, False, 64, NONE, 0, WHITE),
               (3, False, 90, NONE, 3, WHITE), (4, False, 50, NONE, 3, WHITE)),
        b_top_text="Fais de ta vie un rêve,", b_top_size=46, b_top_r=80, b_top_sp=1,
        b_bot_text="et d'un rêve, une réalité.", b_bot_size=46, b_bot_r=80, b_bot_sp=1,
        b_top_font="Sans-serif Bold", b_bot_font="Sans-serif Bold",
        b_ctr_text="Antoine de Saint-Exupéry", b_ctr_size=18, b_ctr_dy=272,
        b_fil_on=True, b_fil_r=80, b_fil_w=3, b_fil_col=WHITE, b_fil_gap=4,
        b_sh_on=True, b_sh_dx=2, b_sh_dy=3, b_sh_blur=4, b_sh_col=_c("000000", 0.5),
        b_sel_on=True, b_sel_r=100)),
    ("Médaille d'or", dict(
        _rings((1, True, 100, _c("eeeeee"), 5, INK), (2, True, 87, NONE, 3, INK),
               (3, True, 63, NONE, 3, INK), (4, False, 50, NONE, 3, INK)),
        b_top_text="ENTRAIDE GIMP ET LIBREOFFICE", b_top_size=42, b_top_col=INK,
        b_top_r=75, b_top_fit=335, b_bot_text="",
        b_ctr_text="GROUPE\nFACEBOOK\n+ DE 400\nMEMBRES", b_ctr_size=46, b_ctr_col=INK,
        b_mot_on=True, b_mot_char="★", b_mot_n=40, b_mot_r=93.5, b_mot_size=22,
        b_mot_col=_c("555555"), b_metal="or", b_bev_scope="tout", b_bev_style="relief",
        b_bev_depth=3, b_bev_soft=1.5, b_sh_on=True, b_sh_dx=4, b_sh_dy=6, b_sh_blur=8,
        b_sh_col=_c("000000", 0.35), b_sel_on=False)),
    ("Tampon encreur", dict(
        _rings((1, True, 100, NONE, 9, _c("c0182a")), (2, True, 70, NONE, 4, _c("c0182a")),
               (3, False, 90, NONE, 3, WHITE), (4, False, 50, NONE, 3, WHITE)),
        b_rotation=-12, b_top_text="MON ENTREPRISE", b_top_size=52, b_top_col=_c("c0182a"),
        b_top_r=85, b_top_fit=140, b_bot_text="PARIS", b_bot_size=52,
        b_bot_col=_c("c0182a"), b_bot_r=85, b_bot_sp=10,
        b_ctr_text="APPROUVÉ", b_ctr_size=64, b_ctr_col=_c("c0182a"),
        b_mot_on=True, b_mot_char="★", b_mot_n=2, b_mot_start=90, b_mot_r=85,
        b_mot_size=34, b_mot_col=_c("c0182a"), b_sel_on=False)),
    ("Écusson bleu et or", dict(
        _rings((1, True, 100, _c("0f2c5c"), 8, _c("d4a017")),
               (2, True, 66, _c("163d7a"), 4, _c("d4a017")),
               (3, False, 90, NONE, 3, WHITE), (4, False, 50, NONE, 3, WHITE)),
        b_top_text="ASSOCIATION", b_top_size=52, b_top_r=83, b_top_fit=140,
        b_bot_text="DEPUIS 2026", b_bot_size=44, b_bot_r=83, b_bot_sp=4,
        b_mot_on=True, b_mot_char="★", b_mot_n=2, b_mot_start=90, b_mot_r=83,
        b_mot_size=40, b_mot_col=_c("d4a017"), b_sh_on=True, b_sh_dx=5, b_sh_dy=7,
        b_sh_blur=8, b_sh_col=_c("000000", 0.4), b_sel_on=True, b_sel_r=64)),
]


def apply_preset(p, preset):
    """Applique un style de texte en conservant le texte et la police."""
    out = normalize(p)
    base = {k: DEFAULTS[k] for k in PRESET_KEYS}
    base.update({k: v for k, v in preset.items() if k in PRESET_KEYS})
    out.update(base)
    out["mode"] = out["mode"] if out["mode"] in ("chemin", "interieur") else "texte"
    return out


def apply_badge_preset(p, preset, keep_texts=False):
    """Applique un modèle de badge. keep_texts : garder les textes déjà saisis."""
    out = normalize(p)
    base = {k: DEFAULTS[k] for k in BADGE_KEYS}
    base.update({k: v for k, v in preset.items() if k in BADGE_KEYS})
    if keep_texts:
        for k in BADGE_TEXT_KEYS:
            base[k] = out[k]
        # Un texte gardé dans un emplacement que le modèle laisse vide prend
        # le style de l'autre texte du modèle (sinon il resterait blanc, etc.).
        for key, other in (("bot", "top"), ("top", "bot")):
            if out["b_%s_text" % key].strip() and not preset.get(
                    "b_%s_text" % key, DEFAULTS["b_%s_text" % key]).strip():
                for attr in ("font", "size", "col", "r", "sw", "scol"):
                    base["b_%s_%s" % (key, attr)] = base["b_%s_%s" % (other, attr)]
                base["b_%s_fit" % key] = 0.0
                # l'autre texte ne doit plus faire presque tout le tour
                base["b_%s_fit" % other] = min(base["b_%s_fit" % other], 150.0)
        if out["b_ctr_text"].strip() and not preset.get("b_ctr_text", "").strip():
            # texte central gardé : police du modèle, couleur foncée lisible sur le fond
            base["b_ctr_font"] = base["b_top_font"]
            col = base["b_top_col"]
            # fond du centre = plus petit anneau affiché : clair -> texte foncé
            rings = [(base["b_r%d_r" % i], base["b_r%d_fill" % i]) for i in range(1, 5)
                     if base["b_r%d_on" % i] and base["b_r%d_fill" % i][3] > 0]
            fill = min(rings)[1] if rings else [1, 1, 1, 0]
            light = 0.3 * fill[0] + 0.59 * fill[1] + 0.11 * fill[2] >= 0.45
            base["b_ctr_col"] = _darken(col, 0.35) if (light and base["b_metal"] in METALS) else col
    out.update(base)
    out["mode"] = "badge"
    return out


def total_extents(prep, p):
    """Zone totale (effets compris) d'une géométrie issue de prepare()."""
    p = normalize(p)
    if prep["mode"] == "badge":
        return badge_extents(prep["g"], p)
    if prep["mode"] in ("chemin", "interieur"):
        return path_extents(prep["g"], p)
    return extents(prep["bbox"], p)


def _pp(shape, style, **path):
    d = {"path_file": "builtin:" + shape}
    d.update(path)
    d.update(style)
    return d


_GOLD = dict(fill_mode="metal_or", grad_angle=70, outline_w=1.5, outline_col=_c("5a3d00"),
             shadow=True, shadow_dx=2, shadow_dy=3, shadow_blur=3, shadow_col=_c("000000", 0.4))
PATH_PRESETS = [
    ("Étoile dorée", _pp("etoile.svg", _GOLD, path_fit=92, path_show=True,
                         path_stroke=_c("c89b2a"), path_sw=4, path_fill=_c("fff4c9", 0.0))),
    ("Cœur tendre", _pp("coeur.svg", dict(fill_mode="gradient", fill1=_c("ff6fa5"),
                                          fill2=_c("c2185b"), grad_angle=90, outline_w=0,
                                          shadow=False),
                        path_repeat=True, path_sep=" ♥ ", path_show=True,
                        path_fill=_c("ffd6e5", 1.0), path_stroke=_c("c2185b"), path_sw=3)),
    ("Flèche", _pp("fleche.svg", dict(fill_mode="solid", fill1=_c("1d4f91"), outline_w=0,
                                      shadow=False),
                   path_fit=90, path_show=True, path_fill=_c("6f9dd0", 1.0),
                   path_stroke=_c("3a5f8a"), path_sw=2)),
    ("Maison", _pp("maison.svg", dict(fill_mode="solid", fill1=_c("7a3b12"), outline_w=0,
                                      shadow=False),
                   path_side="dessous", path_offset=6, path_fit=90, path_show=True,
                   path_fill=_c("fff1dc", 1.0), path_stroke=_c("7a3b12"), path_sw=4)),
    ("Fleur", _pp("fleur.svg", dict(fill_mode="gradient", fill1=_c("9c27b0"), fill2=_c("e040fb"),
                                    grad_angle=0, outline_w=0, shadow=False),
                  path_repeat=True, path_sep=" ✿ ", path_show=True,
                  path_fill=_c("f3e5f5", 1.0), path_stroke=_c("9c27b0"), path_sw=3)),
    ("Spirale", _pp("spirale.svg", dict(fill_mode="solid", fill1=_c("222222"), outline_w=0,
                                        shadow=False),
                    path_size=800, path_pos=50, path_fit=98, path_side="centre",
                    path_offset=0, path_show=False)),
    ("Croix étoilée", _pp("croix.svg", dict(fill_mode="gradient", fill1=_c("4fc3f7"),
                                            fill2=_c("0d47a1"), grad_angle=90, outline_w=0,
                                            shadow=False),
                          path_fit=95, path_show=True, path_fill=_c("e3f2fd", 1.0),
                          path_stroke=_c("0d47a1"), path_sw=2)),
    ("Cercle continu", _pp("cercle.svg", dict(fill_mode="solid", fill1=_c("e65100"),
                                              outline_w=0, shadow=False),
                           path_repeat=True, path_sep=" • ", path_show=False)),
    ("Vague", _pp("vague.svg", dict(fill_mode="gradient", fill1=_c("00bcd4"), fill2=_c("01579b"),
                                    grad_angle=90, outline_w=0, shadow=False),
                  path_size=900, path_pos=50, path_fit=95, path_show=False)),
]


def apply_path_preset(p, preset):
    """Modèle de texte sur chemin : forme + style, texte et police conservés."""
    out = normalize(p)
    base = {k: DEFAULTS[k] for k in PRESET_KEYS | PATH_KEYS}
    base.update({k: v for k, v in preset.items() if k in PRESET_KEYS | PATH_KEYS})
    out.update(base)
    out["mode"] = "chemin"
    return out


INSIDE_PRESETS = [
    ("Cœur", _pp("coeur.svg", dict(fill_mode="gradient", fill1=_c("e91e63"), fill2=_c("880e4f"),
                                   grad_angle=90, outline_w=0, shadow=False),
                 path_show=True, path_fill=_c("ffe4ee", 1.0), path_stroke=_c("c2185b"),
                 path_sw=4, in_align="centre", in_margin=14)),
    ("Étoile", _pp("etoile.svg", dict(fill_mode="solid", fill1=_c("5a3d00"), outline_w=0,
                                      shadow=False),
                   path_show=True, path_fill=_c("ffe082", 1.0), path_stroke=_c("c89b2a"),
                   path_sw=4, in_align="centre", in_margin=8)),
    ("Maison", _pp("maison.svg", dict(fill_mode="solid", fill1=_c("4e2a0e"), outline_w=0,
                                      shadow=False),
                   path_show=True, path_fill=_c("fff1dc", 1.0), path_stroke=_c("7a3b12"),
                   path_sw=5, in_align="justifie", in_margin=16)),
    ("Bulle", _pp("bulle.svg", dict(fill_mode="solid", fill1=_c("1a1a1a"), outline_w=0,
                                    shadow=False),
                  path_show=True, path_fill=_c("ffffff", 1.0), path_stroke=_c("1a1a1a"),
                  path_sw=4, in_align="centre", in_margin=18)),
    ("Cercle", _pp("cercle.svg", dict(fill_mode="gradient", fill1=_c("0277bd"), fill2=_c("01579b"),
                                      grad_angle=90, outline_w=0, shadow=False),
                   path_show=True, path_fill=_c("e1f5fe", 1.0), path_stroke=_c("0277bd"),
                   path_sw=3, in_align="justifie", in_margin=14)),
    ("Fleur", _pp("fleur.svg", dict(fill_mode="gradient", fill1=_c("6a1b9a"), fill2=_c("ab47bc"),
                                    grad_angle=90, outline_w=0, shadow=False),
                  path_show=True, path_fill=_c("f3e5f5", 1.0), path_stroke=_c("8e24aa"),
                  path_sw=3, in_align="centre", in_margin=10)),
    ("Texte seul", _pp("coeur.svg", dict(fill_mode="solid", fill1=_c("c2185b"), outline_w=0,
                                         shadow=False),
                       path_show=False, in_align="centre", in_margin=4)),
]


def apply_inside_preset(p, preset):
    """Modèle de texte dans une forme : forme + style, texte et police conservés."""
    keys = PRESET_KEYS | PATH_KEYS | INSIDE_KEYS
    out = normalize(p)
    base = {k: DEFAULTS[k] for k in keys}
    base.update({k: v for k, v in preset.items() if k in keys})
    out.update(base)
    out["mode"] = "interieur"
    return out


INSIDE_PRESETS += [
    ("Autour d'un cœur", _pp("coeur.svg", dict(fill_mode="solid", fill1=_c("333333"),
                                               outline_w=0, shadow=False),
                             path_show=True, path_fill=_c("e91e63", 1.0), path_stroke=_c("880e4f"),
                             path_sw=3, path_size=300, in_where="hors", in_align="justifie",
                             in_margin=14, in_frame_w=270, in_frame_h=170)),
    ("Autour d'une étoile", _pp("etoile.svg", dict(fill_mode="solid", fill1=_c("1d3557"),
                                                   outline_w=0, shadow=False),
                                path_show=True, path_fill=_c("ffc107", 1.0),
                                path_stroke=_c("c89b2a"), path_sw=3, path_size=300,
                                in_where="hors", in_align="centre", in_margin=12,
                                in_frame_w=250, in_frame_h=160)),
]


# --------------------------------------------------------------------------
# Badges inspirés des sceaux et médailles (lot 1 : 6 modèles de validation)
# --------------------------------------------------------------------------
GOLD, CREAM, NAVY = _c("f6e7b8"), _c("fff6dc"), _c("16325c")
BADGE_PRESETS += [
    ("Sceau de cire rouge", dict(
        _rings((1, True, 100, _c("b3261e"), 0, NONE), (2, True, 78, NONE, 3, _c("8e1c15")),
               (3, True, 58, NONE, 2.5, _c("8e1c15")), (4, False, 50, NONE, 3, WHITE)),
        b_edge="feston", b_edge_n=11, b_edge_depth=7,
        b_top_text="MON ENTREPRISE", b_top_size=50, b_top_col=_c("5e0d09"), b_top_r=68,
        b_top_fit=150, b_bot_text="PARIS", b_bot_size=46, b_bot_col=_c("5e0d09"), b_bot_r=68,
        b_bot_sp=8, b_ctr_text="APPROUVÉ", b_ctr_size=58, b_ctr_col=_c("5e0d09"),
        b_mot_on=True, b_mot_char="★", b_mot_n=2, b_mot_start=90, b_mot_r=68, b_mot_size=30,
        b_mot_col=_c("5e0d09"), b_bev_scope="tout", b_bev_style="relief", b_bev_depth=5,
        b_bev_soft=4, b_bev_hi=0.45, b_bev_sh=0.6, b_tex="cire", b_tex_amount=0.55,
        b_sh_on=True, b_sh_dx=6, b_sh_dy=9, b_sh_blur=10, b_sh_col=_c("000000", 0.4),
        b_sel_on=False)),
    ("Badge bleu institutionnel", dict(
        _rings((1, True, 100, CREAM, 3, _c("6b4a00")), (2, True, 86, NAVY, 4, GOLD, False),
               (3, True, 58, _c("1d4f91"), 4, GOLD, False), (4, False, 50, NONE, 3, WHITE)),
        b_guil_on=True, b_guil_r1=87, b_guil_r2=99, b_guil_col=_c("6b4a00", 0.7), b_guil_n=8,
        b_guil_waves=40, b_guil_w=0.9,
        b_top_text="MON ENTREPRISE", b_top_size=50, b_top_col=GOLD, b_top_r=72, b_top_fit=150,
        b_bot_text="PARIS", b_bot_size=46, b_bot_col=GOLD, b_bot_r=72, b_bot_sp=8,
        b_ctr_text="APPROUVÉ", b_ctr_size=56, b_ctr_col=GOLD,
        b_mot_on=True, b_mot_char="★", b_mot_n=2, b_mot_start=90, b_mot_r=72, b_mot_size=30,
        b_mot_col=GOLD, b_metal="or", b_bev_scope="tout", b_bev_style="relief", b_bev_depth=3,
        b_bev_soft=1.5, b_sh_on=True, b_sh_dx=5, b_sh_dy=8, b_sh_blur=9,
        b_sh_col=_c("000000", 0.35), b_sel_on=False)),
    ("Médaille d'or prestige", dict(
        _rings((1, True, 100, CREAM, 4, _c("8a6a1c")), (2, True, 80, NONE, 3, _c("8a6a1c")),
               (3, False, 60, NONE, 3, WHITE), (4, False, 50, NONE, 3, WHITE)),
        b_laur_on=True, b_laur_r=113, b_laur_size=40, b_laur_span=150, b_laur_gap=40,
        b_laur_col=CREAM,
        b_top_text="MON ENTREPRISE", b_top_size=50, b_top_col=_c("6b4a00"), b_top_r=90,
        b_top_fit=140, b_bot_text="PARIS", b_bot_size=44, b_bot_col=_c("6b4a00"), b_bot_r=90,
        b_bot_sp=8, b_ctr_text="APPROUVÉ", b_ctr_size=62, b_ctr_col=_c("6b4a00"),
        b_mot_on=True, b_mot_char="★", b_mot_n=14, b_mot_start=0, b_mot_r=72, b_mot_size=20,
        b_mot_col=_c("8a6a1c"), b_metal="or", b_tex="brosse", b_tex_amount=0.7,
        b_bev_scope="tout", b_bev_style="relief", b_bev_depth=3, b_bev_soft=1.5,
        b_sh_on=True, b_sh_dx=4, b_sh_dy=7, b_sh_blur=8, b_sh_col=_c("000000", 0.3),
        b_sel_on=False)),
    ("Vintage brasserie", dict(
        _rings((1, True, 100, _c("f2d6a8"), 0, NONE), (2, True, 86, _c("2f5d5b"), 4, _c("f2d6a8"), False),
               (3, True, 56, _c("b88c5a"), 4, _c("5c3a14")), (4, False, 50, NONE, 3, WHITE)),
        b_edge="dents", b_edge_n=40, b_edge_depth=5,
        b_top_text="CERTIFIÉ CONFORME", b_top_size=48, b_top_col=_c("f2d6a8"), b_top_r=71,
        b_top_fit=150, b_bot_text="DEPUIS 2026", b_bot_size=46, b_bot_col=_c("f2d6a8"),
        b_bot_r=71, b_bot_sp=4, b_icon_on=True, b_icon_file="builtin:etoile.svg",
        b_icon_size=36, b_icon_col=_c("fff3dc"),
        b_mot_on=True, b_mot_char="★", b_mot_n=2, b_mot_start=90, b_mot_r=71, b_mot_size=30,
        b_mot_col=_c("f2d6a8"), b_metal="bronze", b_tex="patine", b_tex_amount=0.8,
        b_bev_scope="tout", b_bev_style="relief", b_bev_depth=3, b_bev_soft=1.5,
        b_sh_on=True, b_sh_dx=5, b_sh_dy=8, b_sh_blur=9, b_sh_col=_c("000000", 0.35),
        b_sel_on=False)),
    ("Moderne & tech", dict(
        _rings((1, True, 100, CREAM, 0, NONE), (2, True, 88, _c("0b3d91"), 3, GOLD, False),
               (3, True, 58, _c("15171c"), 4, GOLD, False), (4, False, 50, NONE, 3, WHITE)),
        b_edge="crans", b_edge_n=8, b_edge_depth=4,
        b_top_text="CERTIFIÉ CONFORME", b_top_size=48, b_top_col=GOLD, b_top_r=73,
        b_top_fit=150, b_bot_text="DEPUIS 2026", b_bot_size=46, b_bot_col=GOLD, b_bot_r=73,
        b_bot_sp=4, b_icon_on=True, b_icon_file="builtin:bouclier.svg", b_icon_size=34,
        b_icon_col=_c("2f7de1"), b_icon_metal=False, b_note_text="GIMP-FONTWORK", b_note_size=15, b_note_r=94,
        b_note_col=_c("3a2a00"), b_metal="or", b_tex="brosse", b_tex_amount=0.5,
        b_bev_scope="tout", b_bev_style="relief", b_bev_depth=3, b_bev_soft=1.5,
        b_sh_on=True, b_sh_dx=5, b_sh_dy=8, b_sh_blur=9, b_sh_col=_c("000000", 0.35),
        b_sel_on=False)),
    ("Champion (humour)", dict(
        _rings((1, True, 94, NAVY, 3, GOLD, False), (2, True, 64, CREAM, 4, GOLD),
               (3, False, 90, NONE, 3, WHITE), (4, False, 50, NONE, 3, WHITE)),
        b_rope_on=True, b_rope_r=98, b_rope_w=16, b_rope_col=CREAM,
        b_top_text="CHAMPION DE LA PROCRASTINATION", b_top_font="Serif Bold", b_top_size=40,
        b_top_col=GOLD, b_top_r=79, b_top_fit=215, b_bot_text="DEPUIS TOUJOURS",
        b_bot_font="Serif Bold", b_bot_size=42, b_bot_col=GOLD, b_bot_r=79, b_bot_sp=3,
        b_mot_on=True, b_mot_char="★", b_mot_n=2, b_mot_start=90, b_mot_r=79, b_mot_size=26,
        b_mot_col=GOLD, b_note_text="GIMP-FONTWORK", b_note_size=14, b_note_r=106,
        b_note_col=_c("3a2a00"), b_metal="or", b_bev_scope="tout", b_bev_style="relief",
        b_bev_depth=3, b_bev_soft=1.5, b_sh_on=True, b_sh_dx=5, b_sh_dy=8, b_sh_blur=9,
        b_sh_col=_c("000000", 0.35), b_sel_on=True, b_sel_r=63)),
]


# Lot 2 : bandeaux, perles, rivets et diamants
SLATE, STEEL = _c("23272e"), _c("d5d9de")
BADGE_PRESETS += [
    ("Gravure blanche", dict(
        _rings((1, True, 100, SLATE, 3, WHITE), (2, True, 93, NONE, 1.5, WHITE),
               (3, True, 62, NONE, 2.5, WHITE), (4, False, 50, NONE, 3, WHITE)),
        b_top_text="MON ENTREPRISE", b_top_size=50, b_top_col=WHITE, b_top_r=78, b_top_fit=140,
        b_bot_text="PARIS", b_bot_size=46, b_bot_col=WHITE, b_bot_r=78, b_bot_sp=8,
        b_ctr_text="APPROUVÉ", b_ctr_size=56, b_ctr_col=WHITE,
        b_ban_on=True, b_ban_style="ruban", b_ban_w=88, b_ban_h=165, b_ban_curve=10,
        b_ban_fill=SLATE, b_ban_stroke=WHITE, b_ban_sw=3,
        b_pearl_on=True, b_pearl_style="perle", b_pearl_r=68, b_pearl_n=56, b_pearl_size=4,
        b_pearl_col=WHITE, b_bev_scope="textes", b_bev_style="relief", b_bev_depth=2,
        b_bev_soft=1, b_bev_hi=0.35, b_bev_sh=0.6, b_sel_on=False)),
    ("Industriel cuivre", dict(
        _rings((1, True, 100, _c("f0c9a8"), 3, _c("5a2c12")), (2, True, 84, NONE, 3, _c("5a2c12")),
               (3, True, 60, _c("e8e8e8"), 3, _c("5a2c12")), (4, False, 50, NONE, 3, WHITE)),
        b_top_text="MON ENTREPRISE", b_top_size=50, b_top_col=_c("4a2210"), b_top_r=72,
        b_top_fit=140, b_bot_text="PARIS", b_bot_size=48, b_bot_col=_c("4a2210"), b_bot_r=72,
        b_bot_sp=8, b_ctr_text="APPROUVÉ", b_ctr_size=54, b_ctr_col=_c("3a2a20"),
        b_ban_on=True, b_ban_style="plaque", b_ban_w=82, b_ban_h=190, b_ban_fill=STEEL,
        b_ban_stroke=_c("6b6f75"), b_ban_sw=3, b_ban_rivets=True, b_ban_metal=False,
        b_pearl_on=True, b_pearl_style="rivet", b_pearl_r=92, b_pearl_n=24, b_pearl_size=14,
        b_pearl_col=_c("f0c9a8"),
        b_mot_on=True, b_mot_char="★", b_mot_n=2, b_mot_start=90, b_mot_r=72, b_mot_size=30,
        b_mot_col=_c("4a2210"), b_metal="cuivre", b_tex="rouille", b_tex_amount=0.55,
        b_bev_scope="tout", b_bev_style="relief", b_bev_depth=3, b_bev_soft=1.5,
        b_sh_on=True, b_sh_dx=5, b_sh_dy=8, b_sh_blur=9, b_sh_col=_c("000000", 0.35),
        b_sel_on=False)),
    ("Bijouterie luxe", dict(
        _rings((1, True, 100, CREAM, 2, _c("8a6a1c")), (2, True, 91, NAVY, 3, GOLD, False),
               (3, True, 60, CREAM, 3, GOLD), (4, False, 50, NONE, 3, WHITE)),
        b_top_text="CERTIFIÉ CONFORME", b_top_font="Serif", b_top_size=44, b_top_col=GOLD,
        b_top_r=76, b_top_fit=150, b_bot_text="JOAILLERIE", b_bot_font="Serif",
        b_bot_size=42, b_bot_col=GOLD, b_bot_r=76, b_bot_sp=6,
        b_ctr_text="MC", b_ctr_font="Serif", b_ctr_size=130, b_ctr_col=_c("8a6a1c"),
        b_pearl_on=True, b_pearl_style="diamant", b_pearl_r=95.5, b_pearl_n=72, b_pearl_size=9,
        b_pearl_col=_c("dfe6ee"), b_pearl_metal=False,
        b_mot_on=True, b_mot_char="•", b_mot_n=2, b_mot_start=90, b_mot_r=76, b_mot_size=26,
        b_mot_col=GOLD, b_metal="or", b_tex="brosse", b_tex_amount=0.45,
        b_bev_scope="tout", b_bev_style="relief", b_bev_depth=3, b_bev_soft=1.5,
        b_sh_on=True, b_sh_dx=4, b_sh_dy=7, b_sh_blur=8, b_sh_col=_c("000000", 0.3),
        b_sel_on=False)),
    ("Éco vert & rouge", dict(
        _rings((1, True, 100, _c("3f6f32"), 4, _c("2c4f23"), False),
               (2, True, 63, _c("b63a2b"), 0, NONE, False), (3, False, 60, NONE, 3, WHITE),
               (4, False, 50, NONE, 3, WHITE)),
        b_rope_on=True, b_rope_r=64.5, b_rope_w=9, b_rope_col=_c("e8c75a"),
        b_laur_on=True, b_laur_r=80, b_laur_size=26, b_laur_span=105, b_laur_gap=100,
        b_laur_col=_c("8cc06a"),
        b_top_text="MON ENTREPRISE", b_top_size=54, b_top_col=_c("f3ead0"), b_top_r=82,
        b_top_fit=125, b_bot_text="PARIS", b_bot_size=50, b_bot_col=_c("f3ead0"), b_bot_r=82,
        b_bot_sp=8, b_ctr_text="APPROUVÉ", b_ctr_size=60, b_ctr_col=WHITE,
        b_bev_scope="tout", b_bev_style="relief", b_bev_depth=2.5, b_bev_soft=1.5,
        b_bev_hi=0.5, b_bev_sh=0.45, b_tex="cire", b_tex_amount=0.3,
        b_sh_on=True, b_sh_dx=4, b_sh_dy=7, b_sh_blur=8, b_sh_col=_c("000000", 0.3),
        b_sel_on=False)),
    ("Institutionnel à ruban", dict(
        _rings((1, True, 100, CREAM, 3, _c("6b4a00")), (2, True, 86, NAVY, 4, GOLD, False),
               (3, True, 60, NAVY, 3, GOLD, False), (4, False, 50, NONE, 3, WHITE)),
        b_rope_on=True, b_rope_r=93, b_rope_w=17, b_rope_col=CREAM,
        b_top_text="CERTIFIÉ INSTITUTIONNEL", b_top_font="Serif Bold", b_top_size=44,
        b_top_col=GOLD, b_top_r=73, b_top_fit=170, b_bot_text="",
        b_ctr_text="DEPUIS 2026", b_ctr_font="Serif Bold", b_ctr_size=30, b_ctr_col=GOLD,
        b_ctr_dy=196, b_ban_on=True, b_ban_style="ruban", b_ban_w=82, b_ban_h=200,
        b_ban_curve=-12, b_ban_fill=NAVY, b_ban_stroke=GOLD, b_ban_sw=4,
        b_icon_on=True, b_icon_file="builtin:bouclier.svg", b_icon_size=42, b_icon_col=CREAM,
        b_icon_auto=False, b_icon_dy=-12,
        b_mot_on=True, b_mot_char="★", b_mot_n=14, b_mot_start=0, b_mot_r=66, b_mot_size=16,
        b_mot_col=GOLD, b_metal="or", b_bev_scope="tout", b_bev_style="relief",
        b_bev_depth=3, b_bev_soft=1.5, b_sh_on=True, b_sh_dx=5, b_sh_dy=8, b_sh_blur=9,
        b_sh_col=_c("000000", 0.35), b_sel_on=False)),
]


# Lot 3 : sport, tampon éco et variantes humoristiques du Champion
_CHAMPION = dict(BADGE_PRESETS)["Champion (humour)"]


def _champion(top, bot, note="GIMP-FONTWORK", **kw):
    d = dict(_CHAMPION, b_top_text=top, b_bot_text=bot, b_note_text=note)
    d.update(kw)
    return d


RED = _c("c62828")
BADGE_PRESETS += [
    ("Sport & performance", dict(
        _rings((1, True, 100, CREAM, 4, _c("6b4a00")), (2, True, 90, NAVY, 3, GOLD, False),
               (3, True, 62, CREAM, 5, RED), (4, True, 58, NONE, 2, _c("6b4a00"))),
        b_top_text="CERTIFIÉ CONFORME", b_top_size=50, b_top_col=GOLD, b_top_r=76,
        b_top_fit=150, b_bot_text="DEPUIS 2026", b_bot_size=48, b_bot_col=GOLD, b_bot_r=76,
        b_bot_sp=4, b_laur_on=True, b_laur_r=50, b_laur_size=22, b_laur_span=140,
        b_laur_gap=40, b_laur_col=CREAM,
        b_mot_on=True, b_mot_char="■", b_mot_n=2, b_mot_start=90, b_mot_r=76, b_mot_size=22,
        b_mot_col=GOLD, b_note_text="GIMP-FONTWORK", b_note_size=14, b_note_r=95,
        b_note_col=_c("3a2a00"), b_metal="or", b_bev_scope="tout", b_bev_style="relief",
        b_bev_depth=3, b_bev_soft=1.5, b_sh_on=True, b_sh_dx=5, b_sh_dy=8, b_sh_blur=9,
        b_sh_col=_c("000000", 0.35), b_sel_on=True, b_sel_r=56)),
    ("Tampon éco", dict(
        _rings((1, True, 100, WHITE, 9, _c("1f5c4a")), (2, True, 92, NONE, 2.5, _c("1f5c4a")),
               (3, True, 58, _c("d8c48a"), 4, _c("1f5c4a")), (4, False, 50, NONE, 3, WHITE)),
        b_top_text="CERTIFIÉ CONFORME", b_top_size=52, b_top_col=_c("1f5c4a"), b_top_r=76,
        b_top_fit=0, b_top_sp=3, b_bot_text="DEPUIS 2026", b_bot_size=50, b_bot_col=_c("1f5c4a"),
        b_bot_r=76, b_bot_sp=4, b_laur_on=True, b_laur_r=76, b_laur_size=22, b_laur_span=92,
        b_laur_gap=92, b_laur_col=_c("2e7d5b"),
        b_note_text="GIMP-FONTWORK", b_note_size=14, b_note_r=106, b_note_col=_c("1f5c4a"),
        b_sel_on=True, b_sel_r=57)),
    ("Champion : reine de la gaffe", _champion(
        "REINE DE LA GAFFE", "DEPUIS 2026", "SANS FAIRE EXPRÈS", b_edge="ebreche",
        b_edge_depth=6, b_top_fit=180)),
    ("Champion : mauvaise foi garantie", _champion(
        "MAUVAISE FOI GARANTIE", "100% DE BONNE FOI", b_top_fit=190)),
    ("Champion : expert en cafouillage", _champion(
        "EXPERT EN CAFOUILLAGE", "DEPUIS CE MATIN", b_top_fit=190, b_tex="patine",
        b_tex_amount=0.45, b_rope_on=False, b_edge="ebreche", b_edge_depth=4)),
    ("Champion : sorcier de la caféine", _champion(
        "SORCIER DE LA CAFÉINE", "GRÂCE AU CAFÉ", b_top_fit=190, b_rope_on=False,
        b_mot_char="●", b_mot_size=18)),
    ("Champion : grand maître du bazar", _champion(
        "GRAND MAÎTRE DU BAZAR", "TOUT EST SOUS CONTRÔLE", b_top_fit=190, b_bot_size=34)),
]
