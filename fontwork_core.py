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
}


def normalize(p):
    """Complète un dictionnaire de paramètres avec les valeurs par défaut."""
    out = dict(DEFAULTS)
    if p:
        out.update({k: v for k, v in p.items() if k in DEFAULTS or k.startswith("_")})
    if out["shape"] not in SHAPE_KEYS:
        out["shape"] = "droit"
    if out["mode"] not in ("texte", "badge"):
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
def _ring_defaults(i, on, r, fill, sw, stroke):
    return {"b_r%d_on" % i: on, "b_r%d_r" % i: r, "b_r%d_fill" % i: fill,
            "b_r%d_sw" % i: sw, "b_r%d_stroke" % i: stroke}


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
    return dict(tp, spacing=max(sp, -tp["size"] * 0.4))


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
            els.append({"kind": "ring", "r": R * p["b_r%d_r" % i] / 100.0,
                        "fill": p["b_r%d_fill" % i], "sw": p["b_r%d_sw" % i],
                        "stroke": p["b_r%d_stroke" % i]})

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

    if p["b_ctr_text"].strip():
        tp = _text_params(p["b_ctr_text"], p["b_ctr_font"], p["b_ctr_size"],
                          0.0, p["b_ctr_ls"])
        polys = [[(x, y + p["b_ctr_dy"]) for x, y in poly] for poly in _centered_text(tp)]
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

    els += texts
    ext = 1.0
    for e in els:
        if e["kind"] == "ring":
            ext = max(ext, e["r"] + e["sw"] / 2)
        elif e["kind"] == "arcs":
            ext = max(ext, e["r"] + e["w"] / 2)
        else:
            ext = max(ext, _max_radius(e["polys"]) + e.get("sw", 0.0))
    polys = [q for e in els if e["kind"] in ("text", "motifs") for q in e["polys"]]
    return {"els": els, "ext": ext + 2, "R": R, "polys": polys}


def badge_extents(g, p):
    e = g["ext"]
    x0, y0, x1, y1 = -e, -e, e, e
    if p["b_sh_on"] and p["b_sh_col"][3] > 0:
        b = p["b_sh_blur"] * 2 + 2
        x0 = min(x0, x0 + p["b_sh_dx"] - b)
        y0 = min(y0, y0 + p["b_sh_dy"] - b)
        x1 = max(x1, x1 + p["b_sh_dx"] + b)
        y1 = max(y1, y1 + p["b_sh_dy"] + b)
    return math.floor(x0), math.floor(y0), math.ceil(x1), math.ceil(y1)


def _draw_element(c, e):
    if e["kind"] == "ring":
        c.new_path()
        c.arc(0, 0, max(0.5, e["r"]), 0, 2 * math.pi)
        if e["fill"][3] > 0:
            c.set_source_rgba(*e["fill"])
            c.fill_preserve()
        if e["sw"] > 0 and e["stroke"][3] > 0:
            c.set_line_width(e["sw"])
            c.set_source_rgba(*e["stroke"])
            c.stroke()
        c.new_path()
    elif e["kind"] == "arcs":
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
        bevel = scope == "tout" or (scope == "textes" and e["kind"] in ("text", "motifs"))
        if not metal and not bevel:
            _draw_element(ctx_for(comp), e)
            continue
        es = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
        _draw_element(ctx_for(es), e)
        if metal:
            er = g["ext"]
            _apply_metal(es, _gradient((-er, -er, er, er), 60, METALS[metal]), scale, x0, y0)
        if bevel:
            _bevel(es, p["b_bev_style"], p["b_bev_depth"] * scale, p["b_bev_soft"] * scale,
                   p["b_bev_angle"], p["b_bev_hi"], p["b_bev_sh"])
        cc.set_source_surface(es, 0, 0)
        cc.paint()

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
# Interface commune aux deux modes
# --------------------------------------------------------------------------
def prepare(p):
    """Géométrie pleine taille : {'mode', 'polys', 'bbox', 'ext', ...}."""
    p = normalize(p)
    if p["mode"] == "badge":
        g = badge_geometry(p)
        e = g["ext"]
        return {"mode": "badge", "g": g, "polys": g["polys"], "bbox": (-e, -e, e, e),
                "ext": badge_extents(g, p), "R": g["R"]}
    polys, bbox = geometry(p)
    return {"mode": "texte", "polys": polys, "bbox": bbox, "ext": extents(bbox, p)}


def draw(prep, p, scale=1.0):
    """Renvoie (surface, origine) pour une géométrie issue de prepare()."""
    if prep["mode"] == "badge":
        return render_badge(prep["g"], p, scale)
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
PRESET_KEYS = set(DEFAULTS) - CONTENT_KEYS - BADGE_KEYS - {"mode"}


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
    out["mode"] = "texte"
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
            if out["b_%s_text" % key].strip() and not preset.get("b_%s_text" % key, "x").strip():
                for attr in ("font", "size", "col", "r", "sw", "scol"):
                    base["b_%s_%s" % (key, attr)] = base["b_%s_%s" % (other, attr)]
                base["b_%s_fit" % key] = 0.0
                # l'autre texte ne doit plus faire presque tout le tour
                base["b_%s_fit" % other] = min(base["b_%s_fit" % other], 150.0)
    out.update(base)
    out["mode"] = "badge"
    return out


def total_extents(prep, p):
    """Zone totale (effets compris) d'une géométrie issue de prepare()."""
    p = normalize(p)
    if prep["mode"] == "badge":
        return badge_extents(prep["g"], p)
    return extents(prep["bbox"], p)
