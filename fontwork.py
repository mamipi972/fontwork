#!/usr/bin/env python3
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
Texte Fontwork — greffon GIMP 3
Texte déformé (arc, cercle, spirale, vague, entonnoir...) avec contour,
dégradé, ombre portée et relief 3D, aperçu en direct et texte ré-éditable.

Installation : copier le dossier « fontwork » (fontwork.py + fontwork_core.py)
dans le dossier plug-ins de GIMP 3. Menu : Calque ▸ Texte Fontwork…
"""
import datetime
import hashlib
import traceback
import json
import os
import shutil
import sys

import gi
gi.require_version("Gimp", "3.0")
gi.require_version("GimpUi", "3.0")
gi.require_version("Gegl", "0.4")
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gimp, GimpUi, Gegl, GLib, Gtk, Gdk  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cairo  # noqa: E402,F401  (active le lien pycairo <-> GTK pour le dessin)
import fontwork_core as fw  # noqa: E402

PROC = "plug-in-fontwork-text"
PARASITE = "fontwork-params"
LAST_FILE = "fontwork-last.json"
STYLES_FILE = "fontwork-styles.json"
MAX_HISTORY = 15


# --------------------------------------------------------------------------
# Utilitaires GIMP
# --------------------------------------------------------------------------
def _cfg_path(name):
    return os.path.join(Gimp.directory(), name)


def load_json(name, default):
    try:
        with open(_cfg_path(name), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(name, data):
    try:
        with open(_cfg_path(name), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
    except Exception:
        pass


def public(p):
    return {k: v for k, v in p.items() if not k.startswith("_")}


def get_offsets(layer):
    r = layer.get_offsets()
    return (r[1], r[2]) if len(r) == 3 else (r[0], r[1])


def read_parasite(layer):
    try:
        par = layer.get_parasite(PARASITE)
        if par is None:
            return None
        return json.loads(bytes(bytearray(par.get_data())).decode("utf-8"))
    except Exception:
        return None


def write_parasite(layer, p):
    # ASCII pur (accents et ★ échappés en \uXXXX) : certaines versions de
    # GIMP refusent les octets > 127 dans les données d'un parasite.
    data = json.dumps(p, ensure_ascii=True).encode("ascii")
    flags = getattr(Gimp, "PARASITE_PERSISTENT", 1) | getattr(Gimp, "PARASITE_UNDOABLE", 2)
    try:
        par = Gimp.Parasite.new(PARASITE, flags, data)
    except TypeError:
        par = Gimp.Parasite.new(PARASITE, flags, list(data))
    layer.attach_parasite(par)


def log_error(where):
    """Écrit le détail de l'erreur dans fontwork-erreurs.log (dossier de profil GIMP)."""
    try:
        with open(_cfg_path("fontwork-erreurs.log"), "a", encoding="utf-8") as f:
            f.write("---- %s — %s\n" % (datetime.datetime.now().isoformat(" ", "seconds"), where))
            f.write(traceback.format_exc())
    except Exception:
        pass


def get_font(name):
    font = None
    try:
        font = Gimp.Font.get_by_name(name) if name else None
    except Exception:
        font = None
    return font or Gimp.context_get_font()


def _pixel_unit():
    try:
        return Gimp.Unit.pixel()
    except Exception:
        return Gimp.Unit.PIXEL


_OUTLINE_CACHE = {}


def gimp_layout_path(ctx, p):
    """
    Contours du texte via le moteur texte de GIMP (calque texte -> chemin).
    Remplace PangoCairo, absent de GIMP 3 sous Windows.
    """
    key = (p["text"], p["font"], p["size"], p["spacing"], p["line_spacing"], p["align"])
    data = _OUTLINE_CACHE.get(key)
    if data is None:
        img = Gimp.Image.new(16, 16, Gimp.ImageBaseType.RGB)
        try:
            img.undo_disable()
            size = max(1.0, float(p["size"]))
            tl = Gimp.TextLayer.new(img, p["text"] or " ", get_font(p["font"]), size, _pixel_unit())
            img.insert_layer(tl, None, 0)
            tl.set_letter_spacing(float(p["spacing"]))
            tl.set_line_spacing((float(p["line_spacing"]) - 1.0) * size)
            tl.set_justification({"left": Gimp.TextJustification.LEFT,
                                  "right": Gimp.TextJustification.RIGHT}.get(
                                      p["align"], Gimp.TextJustification.CENTER))
            w, h = tl.get_width(), tl.get_height()
            path = Gimp.Path.new_from_text_layer(img, tl)
            strokes = []
            for sid in path.get_strokes():
                r = path.stroke_get_points(sid)
                pts, closed = list(r[1]), bool(r[2])
                strokes.append((pts, closed))
        finally:
            img.delete()
        data = (strokes, w, h)
        if len(_OUTLINE_CACHE) > 30:
            _OUTLINE_CACHE.clear()
        _OUTLINE_CACHE[key] = data

    strokes, w, h = data
    # Points GIMP : (poignée entrée, ancre, poignée sortie) pour chaque ancre
    for pts, closed in strokes:
        n = len(pts) // 6
        if n < 2:
            continue
        P = [(pts[6 * i], pts[6 * i + 1], pts[6 * i + 2], pts[6 * i + 3],
              pts[6 * i + 4], pts[6 * i + 5]) for i in range(n)]
        ctx.move_to(P[0][2], P[0][3])
        last = n if closed else n - 1
        for i in range(last):
            a, b = P[i], P[(i + 1) % n]
            ctx.curve_to(a[4], a[5], b[0], b[1], b[2], b[3])
        ctx.close_path()
    return None, (0, 0, w, h)


fw.layout_path = gimp_layout_path


def write_layer(image, surf, x, y, name, parent, position):
    """Crée un calque à partir d'une surface cairo ARGB32."""
    w, h = surf.get_width(), surf.get_height()
    ltype = (Gimp.ImageType.GRAYA_IMAGE if image.get_base_type() == Gimp.ImageBaseType.GRAY
             else Gimp.ImageType.RGBA_IMAGE)
    layer = Gimp.Layer.new(image, name, w, h, ltype, 100.0, Gimp.LayerMode.NORMAL)
    image.insert_layer(layer, parent, position)
    layer.set_offsets(int(x), int(y))
    buf = layer.get_buffer()
    _fill_buffer(buf, surf)
    layer.update(0, 0, w, h)
    return layer


def _fill_buffer(buf, surf):
    w, h = surf.get_width(), surf.get_height()
    surf.flush()
    data = bytes(surf.get_data())
    rect = Gegl.Rectangle.new(0, 0, w, h)
    try:
        buf.set(rect, "cairo-ARGB32", data)
    except Exception:
        # repli : BGRA prémultiplié (petit-boutiste) -> RGBA prémultiplié
        b = bytearray(data)
        b[0::4], b[2::4] = b[2::4], b[0::4]
        buf.set(rect, "R'aG'aB'aA u8", bytes(b))
    buf.flush()


def update_layer_in_place(image, layer, surf, x, y):
    """
    Remplace le contenu d'un calque Fontwork existant sans recréer le calque :
    ses filtres non destructifs, son masque, son opacité, son mode de fusion,
    son nom et sa place dans la pile sont conservés. Opération annulable.
    """
    w, h = surf.get_width(), surf.get_height()
    layer.resize(w, h, 0, 0)
    layer.set_offsets(int(x), int(y))
    saved = None
    if not Gimp.Selection.is_empty(image):
        saved = Gimp.Selection.save(image)
        Gimp.Selection.none(image)
    try:
        shadow = layer.get_shadow_buffer()
        _fill_buffer(shadow, surf)
        layer.merge_shadow(True)
        layer.update(0, 0, w, h)
    finally:
        if saved is not None:
            image.select_item(Gimp.ChannelOps.REPLACE, saved)
            image.remove_channel(saved)


def remove_channel(image, name):
    for ch in image.get_channels():
        if ch.get_name() == name:
            image.remove_channel(ch)


def save_zone_channel(image, circle, name):
    """
    Enregistre un cercle comme canal nommé, sans laisser de sélection active :
    la sélection de l'utilisateur est remise telle qu'elle était.
    """
    previous = None
    if not Gimp.Selection.is_empty(image):
        previous = Gimp.Selection.save(image)
    try:
        image.select_ellipse(Gimp.ChannelOps.REPLACE, *circle)
        ch = Gimp.Selection.save(image)
        ch.set_name(name)
        ch.set_visible(False)
    finally:
        if previous is not None:
            image.select_item(Gimp.ChannelOps.REPLACE, previous)
            image.remove_channel(previous)
        else:
            Gimp.Selection.none(image)
    return ch


def anchor_for(p, bbox, anchor):
    """Avec un tracé de l'image, le texte se place exactement sur ce tracé."""
    if p.get("mode") in ("chemin", "interieur") and p.get("path_src") == "image":
        return (bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0
    return anchor


def image_path_polylines(image):
    """Tracé sélectionné (sinon le premier) de l'image -> [(points, fermé), ...]."""
    try:
        paths = list(image.get_selected_paths() or [])
    except Exception:
        paths = []
    if not paths:
        paths = list(image.get_paths() or [])[:1]
    if not paths:
        return []
    path = paths[0]
    out = []
    for sid in path.get_strokes():
        r = path.stroke_get_points(sid)
        pts, closed = list(r[1]), bool(r[2])
        n = len(pts) // 6
        if n < 1:
            continue
        P = [pts[6 * i:6 * i + 6] for i in range(n)]
        poly = [(P[0][2], P[0][3])]
        for i in range(n if closed else n - 1):
            a, b = P[i], P[(i + 1) % n]
            x0, y0, x1, y1, x2, y2, x3, y3 = a[2], a[3], a[4], a[5], b[0], b[1], b[2], b[3]
            for k in range(1, 17):
                t = k / 16.0
                mt = 1 - t
                poly.append((mt ** 3 * x0 + 3 * mt * mt * t * x1 + 3 * mt * t * t * x2 + t ** 3 * x3,
                             mt ** 3 * y0 + 3 * mt * mt * t * y1 + 3 * mt * t * t * y2 + t ** 3 * y3))
        if len(poly) > 1:
            out.append((poly, closed))
    return out


def user_shape_dir():
    d = _cfg_path("fontwork-formes")
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        pass
    return d


def add_path(image, polys, dx, dy, name):
    path = Gimp.Path.new(image, name)
    image.insert_path(path, None, 0)
    for poly in polys:
        pts = []
        for x, y in poly:
            pts += [x + dx, y + dy] * 3      # point d'ancrage + 2 poignées confondues
        path.stroke_new_from_points(Gimp.PathStrokeType.BEZIER, pts, True)
    return path


# --------------------------------------------------------------------------
# Boîte de dialogue
# --------------------------------------------------------------------------
def rgba_to_gdk(c):
    g = Gdk.RGBA()
    g.red, g.green, g.blue, g.alpha = c
    return g


class FontworkDialog:
    PREVIEW_W, PREVIEW_H = 560, 360

    def __init__(self, image, params, edit_layer, history=None):
        self.image = image
        self.p = fw.normalize(params)
        self.current = dict(self.p)
        self.history = history or []
        self.edit_layer = edit_layer
        self.widgets = {}
        self.rows = {}
        self.loading = False
        self.geo_key = None
        self.geo = None
        self.canvas_timer = None
        self.canvas_layer = None
        self.frozen = False
        self.edit_was_visible = edit_layer.get_visible() if edit_layer else False
        self.make_path = False
        self.merge = False
        self.anchor = None       # défini par le greffon

        GimpUi.init(PROC)
        self.dlg = GimpUi.Dialog(title="Texte Fontwork", role=PROC)
        self.dlg.add_button("_Annuler", Gtk.ResponseType.CANCEL)
        self.dlg.add_button("_Valider", Gtk.ResponseType.OK)
        self.dlg.set_default_response(Gtk.ResponseType.OK)
        self._build()

    # ---------------------------------------------------------------- UI
    def _build(self):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, margin=10)
        self.dlg.get_content_area().pack_start(box, True, True, 0)

        # Colonne gauche : mode, styles, aperçu
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.pack_start(left, True, True, 0)

        if self.edit_layer:
            lab = Gtk.Label(xalign=0)
            lab.set_markup("<b>Modification du calque :</b> " +
                           GLib.markup_escape_text(self.edit_layer.get_name()))
            left.pack_start(lab, False, False, 0)
            if self.history:
                hbox = Gtk.Box(spacing=6)
                hbox.pack_start(Gtk.Label(label="Version :"), False, False, 0)
                hc = Gtk.ComboBoxText()
                hc.append("cur", "Actuelle")
                shapes = dict((k, l) for k, l, _ in fw.SHAPES)
                for i, h in enumerate(self.history):
                    pp = h.get("params", {})
                    if pp.get("mode") == "badge":
                        txt, kind = pp.get("b_top_text", ""), "badge"
                    elif pp.get("mode") in ("chemin", "interieur"):
                        ref = pp.get("path_file", "")
                        txt = pp.get("text", "")
                        kind = "chemin : " + (fw.BUILTIN_NAMES.get(ref.split(":")[-1])
                                              or os.path.splitext(ref.split(":")[-1])[0])
                    else:
                        txt, kind = pp.get("text", ""), shapes.get(pp.get("shape"), "")
                    txt = (txt.strip().splitlines() or [""])[0][:24]
                    hc.append("h%d" % i, "%s — « %s » — %s" % (h.get("date", "?"), txt, kind))
                hc.set_active_id("cur")
                hc.connect("changed", self._on_version)
                hbox.pack_start(hc, True, True, 0)
                left.pack_start(hbox, False, False, 0)

        mbox = Gtk.Box(spacing=12)
        mbox.pack_start(Gtk.Label(label="Mode :"), False, False, 0)
        self.rb_text = Gtk.RadioButton.new_with_label_from_widget(None, "Texte déformé")
        self.rb_path = Gtk.RadioButton.new_with_label_from_widget(self.rb_text, "Texte sur chemin")
        self.rb_inside = Gtk.RadioButton.new_with_label_from_widget(self.rb_text, "Texte dans ou hors d'une forme")
        self.rb_badge = Gtk.RadioButton.new_with_label_from_widget(self.rb_text, "Badge / sceau")
        self.mode_radios = {"texte": self.rb_text, "chemin": self.rb_path,
                            "interieur": self.rb_inside, "badge": self.rb_badge}
        self.mode_radios[self.p["mode"]].set_active(True)
        for rb in self.mode_radios.values():
            rb.connect("toggled", self._on_mode)
            mbox.pack_start(rb, False, False, 0)
        left.pack_start(mbox, False, False, 0)

        sbox = Gtk.Box(spacing=6)
        sbox.pack_start(Gtk.Label(label="Modèle :"), False, False, 0)
        self.style_combo = Gtk.ComboBoxText()
        self.style_combo.connect("changed", self._on_style)
        sbox.pack_start(self.style_combo, True, True, 0)
        gbtn = Gtk.Button(label="Galerie…")
        gbtn.set_tooltip_text("Choisir un modèle d'après sa vignette")
        gbtn.connect("clicked", self._on_gallery)
        sbox.pack_start(gbtn, False, False, 0)
        btn = Gtk.Button(label="Enregistrer…")
        btn.set_tooltip_text("Enregistrer les réglages actuels comme modèle personnel")
        btn.connect("clicked", self._on_save_style)
        sbox.pack_start(btn, False, False, 0)
        rbtn = Gtk.Button(label="Réinitialiser")
        rbtn.set_tooltip_text("Revenir aux réglages d'origine du greffon")
        rbtn.connect("clicked", self._on_reset)
        sbox.pack_start(rbtn, False, False, 0)
        left.pack_start(sbox, False, False, 0)
        self.keep_texts = Gtk.CheckButton(label="Garder mes textes en changeant de modèle")
        self.keep_texts.set_active(True)
        left.pack_start(self.keep_texts, False, False, 0)

        frame = Gtk.Frame()
        self.area = Gtk.DrawingArea()
        self.area.set_size_request(self.PREVIEW_W, self.PREVIEW_H)
        self.area.connect("draw", self._on_draw)
        frame.add(self.area)
        left.pack_start(frame, True, True, 0)

        self.status = Gtk.Label(xalign=0)
        left.pack_start(self.status, False, False, 0)

        chk = Gtk.CheckButton(label="Aperçu en direct sur l'image")
        chk.connect("toggled", self._on_canvas_toggle)
        left.pack_start(chk, False, False, 0)
        self.canvas_check = chk
        chk2 = Gtk.CheckButton(label="Créer aussi un tracé (chemin) des textes")
        chk2.connect("toggled", lambda b: setattr(self, "make_path", b.get_active()))
        left.pack_start(chk2, False, False, 0)
        chk3 = Gtk.CheckButton(label="Fusionner avec le calque du dessous (ne sera plus modifiable)")
        chk3.connect("toggled", lambda b: setattr(self, "merge", b.get_active()))
        left.pack_start(chk3, False, False, 0)

        # Colonne droite : onglets selon le mode
        self.stack = Gtk.Stack()
        self.stack.set_size_request(430, -1)
        box.pack_start(self.stack, False, False, 0)

        nb = Gtk.Notebook(scrollable=True)
        self.nb_text = nb
        nb.append_page(self._page(self._page_text()), Gtk.Label(label="Texte"))
        self.pg_shape = self._page(self._page_shape())
        nb.append_page(self.pg_shape, Gtk.Label(label="Forme"))
        self.pg_path = self._page(self._page_path())
        nb.append_page(self.pg_path, Gtk.Label(label="Chemin"))
        nb.append_page(self._page(self._page_colors()), Gtk.Label(label="Couleurs"))
        nb.append_page(self._page(self._page_bevel("bevel", "bevel_depth", "bevel_soft",
                                                   "bevel_angle", "bevel_hi", "bevel_sh")),
                       Gtk.Label(label="Biseau"))
        nb.append_page(self._page(self._page_shadow()), Gtk.Label(label="Ombre"))
        nb.append_page(self._page(self._page_3d()), Gtk.Label(label="3D"))
        self.stack.add_named(nb, "texte")

        nbb = Gtk.Notebook(scrollable=True)
        nbb.append_page(self._page(self._page_b_rings()), Gtk.Label(label="Anneaux"))
        nbb.append_page(self._page(self._page_b_texts()), Gtk.Label(label="Textes"))
        nbb.append_page(self._page(self._page_b_decor()), Gtk.Label(label="Décors"))
        nbb.append_page(self._page(self._page_b_effects()), Gtk.Label(label="Effets"))
        self.stack.add_named(nbb, "badge")

        self._fill_styles()
        self._update_sensitivity()
        self.dlg.show_all()
        self._show_mode()

    # ------------------------------------------------------ constructeurs
    def _grid(self):
        g = Gtk.Grid(column_spacing=8, row_spacing=6, margin=10)
        g.row = 0
        return g

    @staticmethod
    def _page(g):
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw.set_min_content_height(470)
        sw.add(g)
        return sw

    def _section(self, g, title):
        lab = Gtk.Label(xalign=0)
        lab.set_markup("<b>%s</b>" % GLib.markup_escape_text(title))
        lab.set_margin_top(6 if g.row else 0)
        g.attach(lab, 0, g.row, 2, 1)
        g.row += 1
        return lab

    def _row(self, g, label, widget, key=None):
        lab = Gtk.Label(label=label, xalign=0)
        g.attach(lab, 0, g.row, 1, 1)
        g.attach(widget, 1, g.row, 1, 1)
        if key:
            self.rows[key] = (lab, widget)
        g.row += 1

    def _slider(self, g, label, key, lo, hi, step, digits=0):
        adj = Gtk.Adjustment(value=self.p[key], lower=lo, upper=hi,
                             step_increment=step, page_increment=step * 10)
        hb = Gtk.Box(spacing=4)
        sc = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adj,
                       digits=digits, draw_value=False, hexpand=True)
        sp = Gtk.SpinButton(adjustment=adj, digits=digits, width_chars=6)
        hb.pack_start(sc, True, True, 0)
        hb.pack_start(sp, False, False, 0)
        integer = isinstance(fw.DEFAULTS[key], int) and not isinstance(fw.DEFAULTS[key], bool)
        adj.connect("value-changed", lambda a: self._set(
            key, int(round(a.get_value())) if integer else a.get_value()))
        self.widgets[key] = ("adj", adj)
        self._row(g, label, hb, key)

    def _color(self, g, label, key):
        b = Gtk.ColorButton.new_with_rgba(rgba_to_gdk(self.p[key]))
        b.set_use_alpha(True)
        b.connect("color-set", lambda w: self._set(
            key, [w.get_rgba().red, w.get_rgba().green, w.get_rgba().blue, w.get_rgba().alpha]))
        self.widgets[key] = ("color", b)
        self._row(g, label, b, key)

    def _combo(self, g, label, key, items):
        c = Gtk.ComboBoxText()
        for k, t in items:
            c.append(k, t)
        c.set_active_id(self.p[key])
        c.connect("changed", lambda w: self._set(key, w.get_active_id()))
        self.widgets[key] = ("combo", c)
        self._row(g, label, c, key)

    def _check(self, g, label, key):
        chk = Gtk.CheckButton(label=label)
        chk.set_active(bool(self.p[key]))
        chk.connect("toggled", lambda b: self._set(key, b.get_active()))
        self.widgets[key] = ("check", chk)
        g.attach(chk, 0, g.row, 2, 1)
        self.rows[key] = (chk,)
        g.row += 1

    def _entry(self, g, label, key):
        e = Gtk.Entry(hexpand=True)
        e.set_text(self.p[key])
        e.connect("changed", lambda w: self._set(key, w.get_text()))
        self.widgets[key] = ("entry", e)
        self._row(g, label, e, key)

    def _textview(self, g, label, key, height=80):
        sw = Gtk.ScrolledWindow(hexpand=True)
        sw.set_size_request(-1, height)
        tv = Gtk.TextView(wrap_mode=Gtk.WrapMode.NONE)
        tv.get_buffer().set_text(self.p[key])
        tv.get_buffer().connect("changed", lambda b: self._set(
            key, b.get_text(b.get_start_iter(), b.get_end_iter(), False)))
        sw.add(tv)
        self.widgets[key] = ("text", tv)
        self._row(g, label, sw, key)

    def _font(self, g, label, key):
        font = get_font(self.p[key])
        self.p[key] = font.get_name()
        try:
            fb = GimpUi.FontChooser.new(label, None, font)
        except Exception:
            fb = GimpUi.FontChooser(title=label, resource=font)
        fb.connect("resource-set", lambda w, *a: self._on_font(key, w, *a))
        self.widgets[key] = ("font", fb)
        self._row(g, label, fb, key)

    # ------------------------------------------------- pages mode texte
    def _page_text(self):
        g = self._grid()
        self._textview(g, "Texte", "text", 90)
        self._font(g, "Police", "font")
        self._slider(g, "Taille (px)", "size", 6, 1000, 1)
        self._slider(g, "Espacement", "spacing", -30, 150, 0.5, 1)
        self._slider(g, "Interligne", "line_spacing", 0.5, 3, 0.05, 2)
        self._combo(g, "Alignement", "align",
                    [("left", "Gauche"), ("center", "Centré"), ("right", "Droite")])
        self._slider(g, "Largeur (%)", "width", 20, 400, 1)
        self._section(g, "Plusieurs lignes")
        self._check(g, "Déformer chaque ligne séparément", "lines_sep")
        self._slider(g, "Écart entre lignes", "line_gap", -100, 300, 1)
        return g

    def _page_shape(self):
        g = self._grid()
        fbx = Gtk.FlowBox(max_children_per_line=4, min_children_per_line=4,
                          selection_mode=Gtk.SelectionMode.SINGLE, homogeneous=True,
                          row_spacing=4, column_spacing=4)
        self.shape_children = {}
        for key, label, _ in fw.SHAPES:
            vb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            da = Gtk.DrawingArea()
            da.set_size_request(76, 44)
            da.connect("draw", self._draw_thumb, self._thumb(key))
            vb.pack_start(da, False, False, 0)
            vb.pack_start(Gtk.Label(label=label), False, False, 0)
            child = Gtk.FlowBoxChild()
            child.add(vb)
            child.shape_key = key
            fbx.add(child)
            self.shape_children[key] = child
        fbx.select_child(self.shape_children[self.p["shape"]])
        # Seul un clic (ou Entrée) choisit une forme ; la sélection automatique
        # que GTK fait quand la grille reçoit le focus est annulée.
        fbx.set_activate_on_single_click(True)
        fbx.connect("child-activated", self._on_shape)
        fbx.connect("selected-children-changed", self._keep_selection,
                    lambda: self.shape_children.get(self.p["shape"]))
        self.shape_box = fbx
        g.attach(fbx, 0, g.row, 2, 1)
        g.row += 1
        self._slider(g, "Intensité", "amount", -100, 100, 1)
        self._slider(g, "Nombre de vagues", "freq", 0.25, 8, 0.05, 2)
        self._slider(g, "Décalage vague (°)", "phase", 0, 360, 1)
        self._slider(g, "Angle de l'arc (°)", "arc", 10, 1080, 1)
        self._slider(g, "Rotation (°)", "rotation", -180, 180, 1)
        self._section(g, "Taille des lettres")
        self._slider(g, "Grossir au centre (%)", "grow_center", -90, 200, 1)
        self._slider(g, "Grossir vers la droite (%)", "grow_right", -180, 180, 1)
        return g

    def _page_colors(self):
        g = self._grid()
        self._combo(g, "Remplissage", "fill_mode", fw.FILL_MODES)
        self._color(g, "Couleur 1", "fill1")
        self._color(g, "Couleur du milieu", "fill3")
        self._color(g, "Couleur 2", "fill2")
        self._slider(g, "Angle du dégradé (°)", "grad_angle", 0, 360, 1)
        self._slider(g, "Épaisseur du contour", "outline_w", 0, 40, 0.5, 1)
        self._color(g, "Couleur du contour", "outline_col")
        return g

    def _page_bevel(self, k_style, k_depth, k_soft, k_angle, k_hi, k_sh, g=None):
        g = g or self._grid()
        if k_style == "bevel":
            self._combo(g, "Style", k_style, [("none", "Aucun"), ("relief", "Relief (bombé)"),
                                               ("grave", "Gravé (creusé)")])
        else:
            self._combo(g, "Style", k_style, [("relief", "Relief (bombé)"),
                                               ("grave", "Gravé (creusé)")])
        self._slider(g, "Profondeur (px)", k_depth, 0, 30, 0.5, 1)
        self._slider(g, "Douceur", k_soft, 0, 20, 0.5, 1)
        self._slider(g, "Lumière (°)", k_angle, 0, 360, 1)
        self._slider(g, "Éclat", k_hi, 0, 1, 0.05, 2)
        self._slider(g, "Ombre du biseau", k_sh, 0, 1, 0.05, 2)
        return g

    def _page_shadow(self):
        g = self._grid()
        self._check(g, "Ombre portée", "shadow")
        self._slider(g, "Décalage X", "shadow_dx", -100, 100, 1)
        self._slider(g, "Décalage Y", "shadow_dy", -100, 100, 1)
        self._slider(g, "Flou", "shadow_blur", 0, 60, 0.5, 1)
        self._color(g, "Couleur / opacité", "shadow_col")
        return g

    def _page_3d(self):
        g = self._grid()
        self._section(g, "Relief (extrusion)")
        self._slider(g, "Profondeur (px)", "extrude", 0, 200, 1)
        self._slider(g, "Direction (°)", "extrude_angle", 0, 360, 1)
        self._color(g, "Couleur du relief", "extrude_col")
        self._section(g, "Rotation 3D")
        self._slider(g, "Basculer (axe horizontal, °)", "rot_x", -80, 80, 1)
        self._slider(g, "Pivoter (axe vertical, °)", "rot_y", -80, 80, 1)
        self._slider(g, "Distance (perspective)", "persp", 0.8, 10, 0.1, 1)
        return g

    # ------------------------------------------------- page chemin
    def _page_path(self):
        g = self._grid()
        self._combo(g, "Chemin suivi", "path_src",
                    [("svg", "Forme SVG (bibliothèque)"),
                     ("image", "Tracé sélectionné dans l'image")])
        self.path_box = Gtk.FlowBox(max_children_per_line=4, min_children_per_line=4,
                                    selection_mode=Gtk.SelectionMode.SINGLE, homogeneous=True,
                                    row_spacing=4, column_spacing=4)
        self.path_box.set_activate_on_single_click(True)
        self.path_box.connect("child-activated", self._on_path_shape)
        self.path_box.connect("selected-children-changed", self._keep_selection,
                              lambda: self.path_children.get(self.p["path_file"]))
        g.attach(self.path_box, 0, g.row, 2, 1)
        self.rows["path_box"] = (self.path_box,)
        g.row += 1
        hb = Gtk.Box(spacing=6)
        add = Gtk.Button(label="Ajouter un SVG…")
        add.set_tooltip_text("Copie un fichier SVG dans votre bibliothèque de formes")
        add.connect("clicked", self._on_add_svg)
        hb.pack_start(add, False, False, 0)
        g.attach(hb, 0, g.row, 2, 1)
        self.rows["path_add"] = (add,)
        g.row += 1
        hint = Gtk.Label(xalign=0, wrap=True, max_width_chars=48, selectable=True)
        hint.set_markup("<small>Vos formes : <b>%s</b>\nVous pouvez aussi y déposer des fichiers "
                        "SVG directement.</small>" % GLib.markup_escape_text(user_shape_dir()))
        g.attach(hint, 0, g.row, 2, 1)
        g.row += 1
        self._fill_path_shapes()
        self._section(g, "Forme")
        self._slider(g, "Taille de la forme (px)", "path_size", 50, 5000, 10)
        self._slider(g, "Rotation de la forme (°)", "path_rot", -180, 180, 1)
        self._slider(g, "Contour suivi (0 = le plus long)", "path_sub", 0, 50, 1)
        self.sec_inside = self._section(g, "Mise en page du texte")
        self._combo(g, "Placer le texte", "in_where", fw.INSIDE_WHERE)
        self._slider(g, "Largeur du cadre (% de la forme)", "in_frame_w", 100, 600, 1)
        self._slider(g, "Hauteur du cadre (% de la forme)", "in_frame_h", 100, 600, 1)
        self._check(g, "Ajuster la taille pour remplir la forme", "in_auto")
        self._combo(g, "Alignement", "in_align", fw.INSIDE_ALIGNS)
        self._combo(g, "Position verticale", "in_valign",
                    [("haut", "En haut"), ("centre", "Centrée")])
        self._slider(g, "Marge intérieure (px)", "in_margin", 0, 300, 0.5, 1)
        self._combo(g, "Zones utilisées sur chaque ligne", "in_zones", fw.INSIDE_ZONES)
        self._combo(g, "Retours à la ligne", "in_breaks", fw.INSIDE_BREAKS)
        self.sec_path_text = self._section(g, "Texte sur le chemin")
        self._slider(g, "Position (%)", "path_pos", 0, 100, 0.5, 1)
        self._combo(g, "Côté", "path_side", fw.PATH_SIDES)
        self._slider(g, "Écart avec le chemin (px)", "path_offset", -100, 200, 0.5, 1)
        self._check(g, "Inverser le sens (texte de l'autre côté)", "path_reverse")
        self._slider(g, "Remplir le chemin (%, 0 = naturel)", "path_fit", 0, 100, 1)
        self._check(g, "Répéter le texte tout autour (formes fermées)", "path_repeat")
        self._entry(g, "Séparateur", "path_sep")
        self._check(g, "Lettres rigides (décocher : lettres courbées)", "path_rigid")
        self._section(g, "Dessiner la forme")
        self._check(g, "Afficher la forme sous le texte", "path_show")
        self._color(g, "Fond", "path_fill")
        self._color(g, "Trait", "path_stroke")
        self._slider(g, "Épaisseur du trait", "path_sw", 0, 60, 0.5, 1)
        return g

    def _shape_thumb(self, ref):
        try:
            subs = fw.load_shape(ref)
            bb = fw._bbox([sp[0] for sp in subs])
            k = min(64.0 / max(bb[2] - bb[0], 1e-6), 38.0 / max(bb[3] - bb[1], 1e-6))
            w = int((bb[2] - bb[0]) * k) + 6
            h = int((bb[3] - bb[1]) * k) + 6
            surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
            c = cairo.Context(surf)
            c.translate(3, 3)
            c.scale(k, k)
            c.translate(-bb[0], -bb[1])
            for pts, closed in subs:
                c.move_to(*pts[0])
                for q in pts[1:]:
                    c.line_to(*q)
                if closed:
                    c.close_path()
            c.set_source_rgba(0, 0, 0, 0.35)
            c.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
            c.fill_preserve()
            c.identity_matrix()
            c.set_line_width(1.5)
            c.set_source_rgba(0, 0, 0, 1)
            c.stroke()
            return surf
        except Exception:
            return None

    def _fill_path_shapes(self):
        for child in self.path_box.get_children():
            self.path_box.remove(child)
        self.path_children = {}
        for ref, label in fw.list_shapes():
            vb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            da = Gtk.DrawingArea()
            da.set_size_request(76, 44)
            da.connect("draw", self._draw_thumb, self._shape_thumb(ref))
            vb.pack_start(da, False, False, 0)
            lab = Gtk.Label(label=label, ellipsize=3, max_width_chars=10)
            vb.pack_start(lab, False, False, 0)
            child = Gtk.FlowBoxChild()
            child.add(vb)
            child.shape_ref = ref
            self.path_box.add(child)
            self.path_children[ref] = child
        self.path_box.show_all()
        self._select_path_child()

    def _select_path_child(self):
        child = self.path_children.get(self.p["path_file"])
        self.loading_path = True
        if child is not None:
            self.path_box.select_child(child)
        else:
            self.path_box.unselect_all()
        self.loading_path = False

    def _on_path_shape(self, box, child):
        box.select_child(child)
        self._set("path_file", child.shape_ref)

    def _keep_selection(self, box, wanted):
        """Remet en surbrillance la forme réellement choisie."""
        child = wanted()
        sel = box.get_selected_children()
        if child is not None and (not sel or sel[0] is not child):
            GLib.idle_add(self._reselect, box, child)

    @staticmethod
    def _reselect(box, child):
        box.select_child(child)
        return False

    def _on_add_svg(self, _btn):
        d = Gtk.FileChooserDialog(title="Ajouter une forme SVG", transient_for=self.dlg,
                                  action=Gtk.FileChooserAction.OPEN)
        d.add_button("_Annuler", Gtk.ResponseType.CANCEL)
        d.add_button("_Ajouter", Gtk.ResponseType.OK)
        f = Gtk.FileFilter()
        f.set_name("Images SVG")
        f.add_pattern("*.svg")
        f.add_pattern("*.SVG")
        d.add_filter(f)
        if d.run() == Gtk.ResponseType.OK and d.get_filename():
            src = d.get_filename()
            try:
                if not fw.parse_svg(src):
                    raise ValueError("aucun contour lisible (texte ou image intégrée ?)")
                dest_dir = user_shape_dir()
                base, ext = os.path.splitext(os.path.basename(src))
                name, k = base + ".svg", 2
                while os.path.exists(os.path.join(dest_dir, name)):
                    name, k = "%s-%d.svg" % (base, k), k + 1
                shutil.copyfile(src, os.path.join(dest_dir, name))
                self.p["path_file"] = "user:" + name
                self.p["path_src"] = "svg"
                self._fill_path_shapes()
                self._sync_widgets()
                self._changed()
            except Exception as e:
                self.status.set_text("SVG refusé : %s" % e)
        d.destroy()

    # ------------------------------------------------- pages mode badge
    def _page_b_rings(self):
        g = self._grid()
        self._section(g, "Badge")
        self._slider(g, "Diamètre (px)", "b_size", 100, 4000, 10)
        self._slider(g, "Rotation (°)", "b_rotation", -180, 180, 1)
        self._section(g, "Bord extérieur (anneau 1)")
        self._combo(g, "Forme du bord", "b_edge", fw.EDGES)
        self._slider(g, "Nombre de festons / dents / crans", "b_edge_n", 3, 120, 1)
        self._slider(g, "Profondeur (%)", "b_edge_depth", 0, 30, 0.5, 1)
        for i in range(1, 5):
            self._section(g, "Anneau %d" % i)
            self._check(g, "Afficher l'anneau %d" % i, "b_r%d_on" % i)
            self._slider(g, "Rayon (%)", "b_r%d_r" % i, 1, 120, 0.5, 1)
            self._color(g, "Fond (transparent possible)", "b_r%d_fill" % i)
            self._slider(g, "Épaisseur du trait", "b_r%d_sw" % i, 0, 60, 0.5, 1)
            self._color(g, "Couleur du trait", "b_r%d_stroke" % i)
            self._check(g, "Teinte métal sur le fond (si finition métal)", "b_r%d_metal" % i)
        return g

    def _page_b_texts(self):
        g = self._grid()
        for key, title in (("top", "Texte du haut"), ("bot", "Texte du bas")):
            self._section(g, title)
            self._entry(g, "Texte", "b_%s_text" % key)
            self._font(g, "Police", "b_%s_font" % key)
            self._slider(g, "Taille (px)", "b_%s_size" % key, 4, 600, 1)
            self._color(g, "Couleur", "b_%s_col" % key)
            self._slider(g, "Rayon (%)", "b_%s_r" % key, 5, 120, 0.5, 1)
            self._slider(g, "Étaler sur (°, 0 = naturel)", "b_%s_fit" % key, 0, 359, 1)
            self._slider(g, "Espacement", "b_%s_sp" % key, -30, 150, 0.5, 1)
            self._slider(g, "Contour", "b_%s_sw" % key, 0, 20, 0.5, 1)
            self._color(g, "Couleur du contour", "b_%s_scol" % key)
        self._section(g, "Texte central")
        self._textview(g, "Texte", "b_ctr_text", 70)
        self._font(g, "Police", "b_ctr_font")
        self._slider(g, "Taille (px)", "b_ctr_size", 4, 600, 1)
        self._color(g, "Couleur", "b_ctr_col")
        self._slider(g, "Interligne", "b_ctr_ls", 0.5, 3, 0.05, 2)
        self._slider(g, "Décalage vertical (px)", "b_ctr_dy", -2000, 2000, 1)
        return g

    def _page_b_decor(self):
        g = self._grid()
        self._section(g, "Filets en arc (entre les textes)")
        self._check(g, "Afficher les filets", "b_fil_on")
        self._slider(g, "Rayon (%)", "b_fil_r", 5, 120, 0.5, 1)
        self._slider(g, "Épaisseur", "b_fil_w", 0.5, 40, 0.5, 1)
        self._color(g, "Couleur", "b_fil_col")
        self._slider(g, "Écart avec les textes (°)", "b_fil_gap", 0, 45, 0.5, 1)
        self._section(g, "Couronne de motifs")
        self._check(g, "Afficher les motifs", "b_mot_on")
        self._entry(g, "Motif (★ • ✦ ❤ ✿ …)", "b_mot_char")
        self._font(g, "Police", "b_mot_font")
        self._slider(g, "Nombre", "b_mot_n", 1, 200, 1)
        self._slider(g, "Rayon (%)", "b_mot_r", 5, 120, 0.5, 1)
        self._slider(g, "Taille (px)", "b_mot_size", 2, 300, 1)
        self._color(g, "Couleur", "b_mot_col")
        self._slider(g, "Angle de départ (°)", "b_mot_start", -180, 180, 1)
        self._check(g, "Orienter les motifs selon le cercle", "b_mot_follow")
        self._section(g, "Cordelette torsadée")
        self._check(g, "Afficher la cordelette", "b_rope_on")
        self._slider(g, "Rayon (%)", "b_rope_r", 5, 130, 0.5, 1)
        self._slider(g, "Épaisseur", "b_rope_w", 2, 80, 0.5, 1)
        self._color(g, "Couleur", "b_rope_col")
        self._section(g, "Guillochage (hachures ondulées)")
        self._check(g, "Afficher le guillochage", "b_guil_on")
        self._slider(g, "Rayon intérieur (%)", "b_guil_r1", 0, 130, 0.5, 1)
        self._slider(g, "Rayon extérieur (%)", "b_guil_r2", 0, 130, 0.5, 1)
        self._slider(g, "Nombre de lignes", "b_guil_n", 1, 40, 1)
        self._slider(g, "Nombre d'ondulations", "b_guil_waves", 2, 200, 1)
        self._slider(g, "Épaisseur des lignes", "b_guil_w", 0.2, 6, 0.1, 1)
        self._color(g, "Couleur", "b_guil_col")
        self._section(g, "Couronne de lauriers")
        self._check(g, "Afficher les lauriers", "b_laur_on")
        self._slider(g, "Rayon (%)", "b_laur_r", 5, 150, 0.5, 1)
        self._slider(g, "Taille des feuilles (px)", "b_laur_size", 4, 200, 1)
        self._slider(g, "Hauteur des branches (°)", "b_laur_span", 20, 180, 1)
        self._slider(g, "Écart en bas (°)", "b_laur_gap", 0, 120, 1)
        self._color(g, "Couleur", "b_laur_col")
        self._section(g, "Forme SVG au centre")
        self._check(g, "Afficher une forme au centre", "b_icon_on")
        self._combo(g, "Forme", "b_icon_file", fw.list_shapes())
        self._slider(g, "Taille (% du diamètre)", "b_icon_size", 2, 100, 0.5, 1)
        self._slider(g, "Décalage vertical (px)", "b_icon_dy", -2000, 2000, 1)
        self._color(g, "Couleur", "b_icon_col")
        self._check(g, "Teinte métal (si finition métal)", "b_icon_metal")
        self._check(g, "Placer automatiquement au-dessus du texte central", "b_icon_auto")
        self._section(g, "Bandeau sous le texte central")
        self._check(g, "Afficher le bandeau", "b_ban_on")
        self._combo(g, "Style", "b_ban_style", fw.BANNER_STYLES)
        self._slider(g, "Largeur (% du diamètre)", "b_ban_w", 10, 200, 0.5, 1)
        self._slider(g, "Hauteur (% du texte)", "b_ban_h", 100, 400, 1)
        self._slider(g, "Courbure du ruban (px)", "b_ban_curve", -200, 200, 1)
        self._color(g, "Fond", "b_ban_fill")
        self._color(g, "Contour", "b_ban_stroke")
        self._slider(g, "Épaisseur du contour", "b_ban_sw", 0, 20, 0.5, 1)
        self._check(g, "Rivets aux coins (plaque)", "b_ban_rivets")
        self._check(g, "Teinte métal (si finition métal)", "b_ban_metal")
        self._section(g, "Couronne de perles, rivets ou diamants")
        self._check(g, "Afficher la couronne", "b_pearl_on")
        self._combo(g, "Style", "b_pearl_style", fw.PEARL_STYLES)
        self._slider(g, "Rayon (%)", "b_pearl_r", 5, 130, 0.5, 1)
        self._slider(g, "Nombre", "b_pearl_n", 1, 300, 1)
        self._slider(g, "Taille (px)", "b_pearl_size", 1, 100, 0.5, 1)
        self._color(g, "Couleur", "b_pearl_col")
        self._check(g, "Teinte métal (si finition métal)", "b_pearl_metal")
        self._section(g, "Petite mention en bas")
        self._entry(g, "Texte (vide = aucune)", "b_note_text")
        self._font(g, "Police", "b_note_font")
        self._slider(g, "Taille (px)", "b_note_size", 4, 200, 1)
        self._slider(g, "Rayon (%)", "b_note_r", 5, 150, 0.5, 1)
        self._color(g, "Couleur", "b_note_col")
        self._section(g, "Zone centrale pour une photo ou un logo")
        self._check(g, "Créer une zone circulaire en validant", "b_sel_on")
        self._combo(g, "Sous forme de", "b_sel_mode",
                    [("canal", "Canal enregistré (recommandé)"),
                     ("selection", "Sélection active")])
        self._slider(g, "Rayon de la zone (%)", "b_sel_r", 5, 120, 0.5, 1)
        hint = Gtk.Label(xalign=0, wrap=True, max_width_chars=48)
        hint.set_markup("<small>Canal : la zone est rangée dans l'onglet <b>Canaux</b>, "
                        "sans sélection active. Pour l'utiliser : clic droit sur le canal "
                        "▸ <b>Canal vers sélection</b>.</small>")
        g.attach(hint, 0, g.row, 2, 1)
        self.rows["b_sel_hint"] = (hint,)
        g.row += 1
        return g

    def _page_b_effects(self):
        g = self._grid()
        self._section(g, "Finition")
        self._combo(g, "Métal", "b_metal", [("aucun", "Aucun (couleurs choisies)"),
                                            ("or", "Or"), ("argent", "Argent"),
                                            ("bronze", "Bronze"), ("cuivre", "Cuivre")])
        self._combo(g, "Texture", "b_tex", [("aucune", "Aucune"), ("brosse", "Métal brossé"),
                                            ("cire", "Cire"), ("patine", "Patine"),
                                            ("rouille", "Rouille")])
        self._slider(g, "Intensité de la texture", "b_tex_amount", 0, 1, 0.05, 2)
        self._section(g, "Biseau")
        self._combo(g, "Appliquer à", "b_bev_scope", [("rien", "Rien"),
                                                      ("textes", "Textes et motifs"),
                                                      ("tout", "Tout le badge")])
        self._page_bevel("b_bev_style", "b_bev_depth", "b_bev_soft", "b_bev_angle",
                         "b_bev_hi", "b_bev_sh", g)
        self._section(g, "Ombre portée")
        self._check(g, "Ombre sous le badge", "b_sh_on")
        self._slider(g, "Décalage X", "b_sh_dx", -100, 100, 1)
        self._slider(g, "Décalage Y", "b_sh_dy", -100, 100, 1)
        self._slider(g, "Flou", "b_sh_blur", 0, 60, 0.5, 1)
        self._color(g, "Couleur / opacité", "b_sh_col")
        return g

    # ------------------------------------------------------ modèles
    def _style_entries(self):
        """[(identifiant, libellé)] des modèles du mode en cours."""
        out = []
        mode = self.p["mode"]
        if mode == "badge":
            out += [("b%d" % i, n) for i, (n, _) in enumerate(fw.BADGE_PRESETS)]
        elif mode in ("chemin", "interieur"):
            if mode == "chemin":
                out += [("c%d" % i, n) for i, (n, _) in enumerate(fw.PATH_PRESETS)]
            else:
                out += [("i%d" % i, n) for i, (n, _) in enumerate(fw.INSIDE_PRESETS)]
            out += [("p%d" % i, "Lettres : " + n) for i, (n, _) in enumerate(fw.PRESETS)]
        else:
            out += [("p%d" % i, n) for i, (n, _) in enumerate(fw.PRESETS)]
        for name, st in sorted(load_json(STYLES_FILE, {}).items()):
            if st.get("mode", "texte") == mode:
                out.append(("u:" + name, "★ " + name))
        return out

    def _styled(self, sid):
        """Réglages obtenus en appliquant le modèle sid aux réglages actuels."""
        if sid.startswith("u:"):
            style = load_json(STYLES_FILE, {}).get(sid[2:], {})
        elif sid.startswith("b"):
            style = dict(fw.BADGE_PRESETS[int(sid[1:])][1], mode="badge")
        elif sid.startswith("c"):
            style = dict(fw.PATH_PRESETS[int(sid[1:])][1], mode="chemin")
        elif sid.startswith("i"):
            style = dict(fw.INSIDE_PRESETS[int(sid[1:])][1], mode="interieur")
        else:
            style = fw.PRESETS[int(sid[1:])][1]
        if style.get("mode") == "badge":
            return fw.apply_badge_preset(self.p, style, self.keep_texts.get_active())
        if style.get("mode") == "chemin":
            return fw.apply_path_preset(self.p, style)
        if style.get("mode") == "interieur":
            return fw.apply_inside_preset(self.p, style)
        return fw.apply_preset(self.p, style)

    def _fill_styles(self):
        self.loading_styles = True
        self.style_combo.remove_all()
        self.style_combo.append("", "— choisir un modèle —")
        for sid, label in self._style_entries():
            self.style_combo.append(sid, label)
        self.style_combo.set_active_id("")
        self.loading_styles = False

    def _on_style(self, combo):
        sid = combo.get_active_id()
        if not sid or getattr(self, "loading_styles", False):
            return
        self.p = self._styled(sid)
        self._sync_widgets()
        self._changed()

    # ------------------------------------------------------ galerie
    THUMB = 132

    def _thumb_surface(self, params):
        """Vignette d'un modèle, gardée en mémoire et sur disque (fontwork-vignettes)."""
        key = hashlib.sha1(json.dumps(fw.normalize(params), sort_keys=True,
                                      ensure_ascii=True).encode()).hexdigest()
        cache = getattr(self, "_thumb_cache", None)
        if cache is None:
            cache = self._thumb_cache = {}
        if key in cache:
            return cache[key]
        folder = _cfg_path("fontwork-vignettes")
        fn = os.path.join(folder, key + ".png")
        surf = None
        if os.path.exists(fn):
            try:
                surf = cairo.ImageSurface.create_from_png(fn)
            except Exception:
                surf = None
        if surf is None:
            prep = fw.prepare(params)
            x0, y0, x1, y1 = fw.total_extents(prep, params)
            sc = min(self.THUMB / max(1, x1 - x0), self.THUMB / max(1, y1 - y0), 1.0)
            surf, _ = fw.draw(prep, params, sc)
            try:
                os.makedirs(folder, exist_ok=True)
                surf.write_to_png(fn)
            except Exception:
                pass
        cache[key] = surf
        return surf

    def _on_gallery(self, _btn):
        d = Gtk.Dialog(title="Galerie des modèles", transient_for=self.dlg, modal=True)
        d.add_button("_Fermer", Gtk.ResponseType.CLOSE)
        d.set_default_size(760, 560)
        sw = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        fb = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True,
                         max_children_per_line=8, row_spacing=8, column_spacing=8,
                         margin=8, valign=Gtk.Align.START)
        fb.set_activate_on_single_click(True)
        sw.add(fb)
        d.get_content_area().pack_start(sw, True, True, 0)
        pending = []
        for sid, label in self._style_entries():
            vb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            da = Gtk.DrawingArea()
            da.set_size_request(self.THUMB, self.THUMB)
            da.surf = None
            da.connect("draw", self._draw_gallery_cell)
            vb.pack_start(da, False, False, 0)
            lab = Gtk.Label(label=label, wrap=True, max_width_chars=16,
                            justify=Gtk.Justification.CENTER)
            vb.pack_start(lab, False, False, 0)
            child = Gtk.FlowBoxChild()
            child.add(vb)
            child.sid = sid
            child.set_tooltip_text("Cliquer pour appliquer ce modèle")
            fb.add(child)
            pending.append((sid, da))

        def on_pick(_box, child):
            self.p = self._styled(child.sid)
            self._sync_widgets()
            self._changed()
            d.response(Gtk.ResponseType.CLOSE)
        fb.connect("child-activated", on_pick)

        # vignettes calculées une par une, sans bloquer la fenêtre
        def step():
            if not pending or not d.get_visible():
                return False
            sid, da = pending.pop(0)
            try:
                da.surf = self._thumb_surface(self._styled(sid))
            except Exception:
                da.surf = None
            da.queue_draw()
            return bool(pending)
        d.show_all()
        GLib.idle_add(step)
        d.run()
        pending.clear()
        d.destroy()

    @staticmethod
    def _draw_gallery_cell(area, cr):
        w, h = area.get_allocated_width(), area.get_allocated_height()
        cr.set_source_rgb(0.62, 0.62, 0.62)
        cr.paint()
        cr.set_source_rgb(0.78, 0.78, 0.78)
        for yy in range(0, h, 12):
            for xx in range((yy // 12) % 2 * 12, w, 24):
                cr.rectangle(xx, yy, 12, 12)
        cr.fill()
        surf = getattr(area, "surf", None)
        if surf is None:
            return
        cr.set_source_surface(surf, (w - surf.get_width()) // 2, (h - surf.get_height()) // 2)
        cr.paint()

    def _on_save_style(self, _btn):
        d = Gtk.Dialog(title="Enregistrer le modèle", transient_for=self.dlg, modal=True)
        d.add_button("_Annuler", Gtk.ResponseType.CANCEL)
        d.add_button("_Enregistrer", Gtk.ResponseType.OK)
        e = Gtk.Entry(activates_default=True, margin=10)
        e.set_placeholder_text("Nom du modèle")
        d.get_content_area().add(e)
        d.set_default_response(Gtk.ResponseType.OK)
        d.show_all()
        if d.run() == Gtk.ResponseType.OK and e.get_text().strip():
            styles = load_json(STYLES_FILE, {})
            keys = {"badge": fw.BADGE_KEYS, "chemin": fw.PRESET_KEYS | fw.PATH_KEYS,
                    "interieur": fw.PRESET_KEYS | fw.PATH_KEYS | fw.INSIDE_KEYS}.get(
                self.p["mode"], fw.PRESET_KEYS)
            st = {k: self.p[k] for k in keys}
            st["mode"] = self.p["mode"]
            styles[e.get_text().strip()] = st
            save_json(STYLES_FILE, styles)
            self._fill_styles()
        d.destroy()

    def _on_reset(self, _btn):
        d = Gtk.Dialog(title="Réinitialiser", transient_for=self.dlg, modal=True)
        d.add_button("_Annuler", Gtk.ResponseType.CANCEL)
        d.add_button("_Réinitialiser", Gtk.ResponseType.OK)
        box = d.get_content_area()
        box.set_spacing(6)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(12)
        box.add(Gtk.Label(label="Revenir aux réglages d'origine (usine) du greffon ?", xalign=0))
        keep = Gtk.CheckButton(label="Garder mes textes")
        keep.set_active(False)
        box.add(keep)
        wipe = Gtk.CheckButton(label="Supprimer aussi mes modèles personnels (★)")
        box.add(wipe)
        d.show_all()
        if d.run() == Gtk.ResponseType.OK:
            fresh = fw.normalize({"mode": self.p["mode"]})
            if keep.get_active():
                for k in ("text",) + tuple(fw.BADGE_TEXT_KEYS):
                    fresh[k] = self.p[k]
            self.p = fresh
            try:
                os.remove(_cfg_path(LAST_FILE))
            except OSError:
                pass
            if wipe.get_active():
                try:
                    os.remove(_cfg_path(STYLES_FILE))
                except OSError:
                    pass
            self._fill_styles()
            self._sync_widgets()
            self._changed()
        d.destroy()

    def _on_version(self, combo):
        vid = combo.get_active_id()
        if vid == "cur":
            params = self.current
        elif vid:
            params = self.history[int(vid[1:])].get("params", {})
        else:
            return
        self.p = fw.normalize(params)
        self._sync_widgets()
        self._changed()

    def _on_mode(self, btn):
        if not btn.get_active() or self.loading:
            return
        mode = [m for m, rb in self.mode_radios.items() if rb is btn][0]
        if mode == self.p["mode"]:
            return
        self.p["mode"] = mode
        self._show_mode()
        if mode in ("chemin", "interieur"):
            self.nb_text.set_current_page(self.nb_text.page_num(self.pg_path))
        elif mode == "texte":
            self.nb_text.set_current_page(self.nb_text.page_num(self.pg_shape))
        self._fill_styles()
        self._update_sensitivity()
        self._changed()

    PATH_ONLY = ("path_sub", "path_pos", "path_side", "path_offset", "path_reverse",
                 "path_fit", "path_repeat", "path_sep", "path_rigid")
    INSIDE_ONLY = ("in_where", "in_frame_w", "in_frame_h", "in_auto", "in_align", "in_valign",
                   "in_margin", "in_zones", "in_breaks")

    def _show_mode(self):
        mode = self.p["mode"]
        self.stack.set_visible_child_name("badge" if mode == "badge" else "texte")
        self.pg_shape.set_visible(mode == "texte")
        self.pg_path.set_visible(mode in ("chemin", "interieur"))
        self.nb_text.set_tab_label_text(self.pg_path, "Forme SVG" if mode == "interieur" else "Chemin")
        self.keep_texts.set_visible(mode == "badge")
        inside = mode == "interieur"
        self.sec_path_text.set_visible(not inside)
        self.sec_inside.set_visible(inside)
        for k in self.PATH_ONLY:
            for w in self.rows.get(k, ()):
                w.set_visible(not inside)
        for k in self.INSIDE_ONLY:
            for w in self.rows.get(k, ()):
                w.set_visible(inside)

    def _sync_widgets(self):
        self.loading = True
        for key, (kind, w) in self.widgets.items():
            v = self.p[key]
            if kind == "text":
                w.get_buffer().set_text(v)
            elif kind == "entry":
                w.set_text(v)
            elif kind == "font":
                try:
                    w.set_resource(get_font(v))
                except Exception:
                    pass
            elif kind == "adj":
                w.set_value(v)
            elif kind == "color":
                w.set_rgba(rgba_to_gdk(v))
            elif kind == "combo":
                w.set_active_id(v)
            elif kind == "check":
                w.set_active(bool(v))
        self.shape_box.select_child(self.shape_children[self.p["shape"]])
        self._select_path_child()
        self.mode_radios[self.p["mode"]].set_active(True)
        self._show_mode()
        self.loading = False
        self._update_sensitivity()

    # ---------------------------------------------------------- handlers
    def _set(self, key, value):
        self.p[key] = value
        self._update_sensitivity()
        if not self.loading:
            self._changed()

    def _on_font(self, key, fb, *args):
        font = args[0] if args and isinstance(args[0], Gimp.Font) else fb.get_resource()
        if font is not None:
            self._set(key, font.get_name())

    def _on_shape(self, box, child):
        box.select_child(child)
        self._set("shape", child.shape_key)

    def _sens(self, key, on):
        for w in self.rows.get(key, ()):
            w.set_sensitive(on)

    def _update_sensitivity(self):
        if not hasattr(self, "shape_box"):
            return
        p = self.p
        useful = fw.SHAPE_PARAMS.get(p["shape"], set())
        for key in ("amount", "freq", "phase", "arc"):
            self._sens(key, key in useful)
        fm = p["fill_mode"]
        self._sens("fill1", fm in ("solid", "gradient", "gradient3"))
        self._sens("fill2", fm in ("gradient", "gradient3"))
        self._sens("fill3", fm == "gradient3")
        self._sens("grad_angle", fm not in ("none", "solid"))
        for key in ("shadow_dx", "shadow_dy", "shadow_blur", "shadow_col"):
            self._sens(key, bool(p["shadow"]))
        for key in ("bevel_depth", "bevel_soft", "bevel_angle", "bevel_hi", "bevel_sh"):
            self._sens(key, p["bevel"] != "none")
        chemin = p["mode"] in ("chemin", "interieur")
        self._sens("lines_sep", not chemin)
        self._sens("line_gap", bool(p["lines_sep"]) and not chemin)
        self._sens("line_spacing", not chemin)
        self._sens("align", not chemin)
        self._sens("rot_x", not chemin)
        self._sens("rot_y", not chemin)
        self._sens("persp", bool(p["rot_x"] or p["rot_y"]) and not chemin)
        svg = p["path_src"] == "svg"
        for k in ("path_box", "path_add", "path_size"):
            self._sens(k, svg)
        self._sens("path_sep", bool(p["path_repeat"]))
        for k in ("in_frame_w", "in_frame_h"):
            self._sens(k, p["in_where"] == "hors")
        self._sens("path_fit", not p["path_repeat"])
        for k in ("path_fill", "path_stroke", "path_sw"):
            self._sens(k, bool(p["path_show"]))
        for i in range(1, 5):
            for k in ("r", "fill", "sw", "stroke"):
                self._sens("b_r%d_%s" % (i, k), bool(p["b_r%d_on" % i]))
        for k in ("b_fil_r", "b_fil_w", "b_fil_col", "b_fil_gap"):
            self._sens(k, bool(p["b_fil_on"]))
        for k in ("b_mot_char", "b_mot_font", "b_mot_n", "b_mot_r", "b_mot_size",
                  "b_mot_col", "b_mot_start", "b_mot_follow"):
            self._sens(k, bool(p["b_mot_on"]))
        self._sens("b_edge_n", p["b_edge"] != "lisse")
        self._sens("b_edge_depth", p["b_edge"] != "lisse")
        for k in ("b_rope_r", "b_rope_w", "b_rope_col"):
            self._sens(k, bool(p["b_rope_on"]))
        for k in ("b_guil_r1", "b_guil_r2", "b_guil_n", "b_guil_waves", "b_guil_w", "b_guil_col"):
            self._sens(k, bool(p["b_guil_on"]))
        for k in ("b_laur_r", "b_laur_size", "b_laur_span", "b_laur_gap", "b_laur_col"):
            self._sens(k, bool(p["b_laur_on"]))
        for k in ("b_icon_file", "b_icon_size", "b_icon_dy", "b_icon_col", "b_icon_metal",
                  "b_icon_auto"):
            self._sens(k, bool(p["b_icon_on"]))
        self._sens("b_tex_amount", p["b_tex"] != "aucune")
        for k in ("b_ban_style", "b_ban_w", "b_ban_h", "b_ban_curve", "b_ban_fill",
                  "b_ban_stroke", "b_ban_sw", "b_ban_rivets", "b_ban_metal"):
            self._sens(k, bool(p["b_ban_on"]))
        self._sens("b_ban_curve", bool(p["b_ban_on"]) and p["b_ban_style"] == "ruban")
        self._sens("b_ban_rivets", bool(p["b_ban_on"]) and p["b_ban_style"] == "plaque")
        for k in ("b_pearl_style", "b_pearl_r", "b_pearl_n", "b_pearl_size", "b_pearl_col",
                  "b_pearl_metal"):
            self._sens(k, bool(p["b_pearl_on"]))
        for k in ("b_sel_r", "b_sel_mode", "b_sel_hint"):
            self._sens(k, bool(p["b_sel_on"]))
        for k in ("b_bev_style", "b_bev_depth", "b_bev_soft", "b_bev_angle", "b_bev_hi", "b_bev_sh"):
            self._sens(k, p["b_bev_scope"] != "rien")
        for k in ("b_sh_dx", "b_sh_dy", "b_sh_blur", "b_sh_col"):
            self._sens(k, bool(p["b_sh_on"]))

    def _changed(self):
        self.area.queue_draw()
        if self.canvas_check.get_active():
            if self.canvas_timer:
                GLib.source_remove(self.canvas_timer)
            self.canvas_timer = GLib.timeout_add(180, self._update_canvas)

    # ----------------------------------------------------------- rendu
    def prepare(self):
        keys = {"badge": sorted(fw.BADGE_KEYS),
                "chemin": list(fw.GEOMETRY_KEYS) + sorted(fw.PATH_KEYS),
                "interieur": list(fw.GEOMETRY_KEYS) + sorted(fw.PATH_KEYS | fw.INSIDE_KEYS)}.get(
            self.p["mode"], fw.GEOMETRY_KEYS)
        key = json.dumps([self.p["mode"]] + [self.p[k] for k in keys])
        if key != self.geo_key:
            self.geo = fw.prepare(self.p)
            self.geo_key = key
        return self.geo

    def _thumb(self, shape):
        p = fw.normalize(dict(text="Abc", font=self.p["font"], size=40, shape=shape, amount=60,
                              arc=540 if shape == "spirale" else 200, fill_mode="solid",
                              fill1=[0, 0, 0, 1], outline_w=0, shadow=False, extrude=0))
        try:
            polys, bbox = fw.geometry(p)
            x0, y0, x1, y1 = fw.extents(bbox, p)
            s = min(70.0 / max(1, x1 - x0), 40.0 / max(1, y1 - y0))
            return fw.render(polys, bbox, p, s)[0]
        except Exception:
            return None

    @staticmethod
    def _draw_thumb(area, cr, surf):
        """Vignette dessinée dans la couleur du texte du thème (clair ou sombre)."""
        if surf is None:
            return
        w, h = area.get_allocated_width(), area.get_allocated_height()
        fg = area.get_style_context().get_color(area.get_state_flags())
        cr.set_source_rgba(fg.red, fg.green, fg.blue, 1.0)
        cr.mask_surface(surf, (w - surf.get_width()) // 2, (h - surf.get_height()) // 2)

    def _on_draw(self, area, cr):
        aw, ah = area.get_allocated_width(), area.get_allocated_height()
        # damier de transparence
        cr.set_source_rgb(0.62, 0.62, 0.62)
        cr.paint()
        cr.set_source_rgb(0.78, 0.78, 0.78)
        for yy in range(0, ah, 16):
            for xx in range((yy // 16) % 2 * 16, aw, 32):
                cr.rectangle(xx, yy, 16, 16)
        cr.fill()
        try:
            prep = self.prepare()
            x0, y0, x1, y1 = fw.total_extents(prep, self.p)
            s = min((aw - 20) / max(1, x1 - x0), (ah - 20) / max(1, y1 - y0), 1.0)
            surf, _ = fw.draw(prep, self.p, s)
            cr.set_source_surface(surf, (aw - surf.get_width()) // 2,
                                  (ah - surf.get_height()) // 2)
            cr.paint()
            msg = "Taille finale : %d × %d px   (aperçu à %d %%)" % (x1 - x0, y1 - y0,
                                                                    round(s * 100))
            if prep["mode"] == "interieur":
                g = prep["g"]
                msg += "   —   texte : %d px" % round(g.get("size", self.p["size"]))
                if g.get("missing"):
                    msg = ("⚠ %d mot(s) ne tiennent pas dans la forme : réduisez la taille, "
                           "la marge, ou cochez l'ajustement automatique." % g["missing"])
            self.status.set_text(msg)
        except Exception as e:
            self.status.set_text("Erreur : %s" % e)

    # ------------------------------------------------- aperçu sur l'image
    def placement(self, origin, bbox):
        cx, cy = (bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0
        ax, ay = anchor_for(self.p, bbox, self.anchor)
        return (int(round(ax + origin[0] - cx)), int(round(ay + origin[1] - cy)))

    def _on_canvas_toggle(self, btn):
        if btn.get_active():
            if not self.frozen:
                self.image.undo_freeze()
                self.frozen = True
            if self.edit_layer:
                self.edit_layer.set_visible(False)
            self._update_canvas()
        else:
            self._remove_canvas_layer()
            if self.edit_layer:
                self.edit_layer.set_visible(self.edit_was_visible)
            Gimp.displays_flush()

    def _remove_canvas_layer(self):
        if self.canvas_layer is not None:
            try:
                self.image.remove_layer(self.canvas_layer)
            except Exception:
                pass
            self.canvas_layer = None

    def _update_canvas(self):
        self.canvas_timer = None
        if not self.canvas_check.get_active():
            return False
        try:
            prep = self.prepare()
            surf, origin = fw.draw(prep, self.p, 1.0)
            x, y = self.placement(origin, prep["bbox"])
            parent, pos = None, 0
            if self.edit_layer:
                parent = self.edit_layer.get_parent()
                pos = self.image.get_item_position(self.edit_layer)
            self._remove_canvas_layer()
            self.canvas_layer = write_layer(self.image, surf, x, y,
                                            "Fontwork (aperçu)", parent, pos)
            Gimp.displays_flush()
        except Exception as e:
            self.status.set_text("Erreur aperçu : %s" % e)
        return False

    def cleanup(self):
        if self.canvas_timer:
            GLib.source_remove(self.canvas_timer)
            self.canvas_timer = None
        self._remove_canvas_layer()
        if self.edit_layer:
            self.edit_layer.set_visible(self.edit_was_visible)
        if self.frozen:
            self.image.undo_thaw()
            self.frozen = False
        Gimp.displays_flush()

    def run(self):
        resp = self.dlg.run()
        self.cleanup()
        self.dlg.destroy()
        return resp == Gtk.ResponseType.OK


# --------------------------------------------------------------------------
# Greffon
# --------------------------------------------------------------------------
class FontworkPlugin(Gimp.PlugIn):
    def do_query_procedures(self):
        return [PROC]

    def do_set_i18n(self, name):
        return False

    def do_create_procedure(self, name):
        proc = Gimp.ImageProcedure.new(self, name, Gimp.PDBProcType.PLUGIN, self.run, None)
        proc.set_image_types("RGB*, GRAY*")
        proc.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE |
                                  Gimp.ProcedureSensitivityMask.DRAWABLES |
                                  Gimp.ProcedureSensitivityMask.NO_DRAWABLES)
        proc.set_menu_label("Texte _Fontwork…")
        proc.add_menu_path("<Image>/Layer/")
        proc.set_documentation(
            "Texte déformé façon Fontwork",
            "Crée un calque de texte déformé (arc, cercle, spirale, vague, entonnoir…), "
            "de texte qui suit ou remplit une forme SVG, ou un badge circulaire, avec contour, "
            "dégradé, métal, biseau, ombre, relief et rotation 3D. Relancer le greffon sur "
            "un calque Fontwork permet de modifier son texte et ses réglages.",
            name)
        proc.set_attribution("Miguel", "Miguel", "2026")
        return proc

    def run(self, procedure, run_mode, image, drawables, config, run_data):
        # Calque Fontwork existant sélectionné -> mode modification
        edit_layer, params = None, None
        try:
            sel = image.get_selected_layers()
        except Exception:
            sel = []
        if len(sel) == 1:
            params = read_parasite(sel[0])
            if params is not None:
                edit_layer = sel[0]
        if params is None:
            params = load_json(LAST_FILE, {})

        # Point d'ancrage (centre du texte dans l'image)
        if edit_layer is not None and "_anchor" in params and "_off" in params:
            ox, oy = get_offsets(edit_layer)
            anchor = (params["_anchor"][0] + ox - params["_off"][0],
                      params["_anchor"][1] + oy - params["_off"][1])
        else:
            anchor = (image.get_width() / 2.0, image.get_height() / 2.0)
            try:
                r = list(Gimp.Selection.bounds(image))
                if len(r) == 6:
                    r = r[1:]            # (succès, non_vide, x1, y1, x2, y2)
                if r[0]:
                    anchor = ((r[1] + r[3]) / 2.0, (r[2] + r[4]) / 2.0)
            except Exception:
                pass

        fw.SHAPE_DIRS["user"] = user_shape_dir()
        fw.image_path_provider = lambda: image_path_polylines(image)

        make_path = merge = False
        history = list(params.get("_history", [])) if edit_layer is not None else []
        if run_mode == Gimp.RunMode.INTERACTIVE:
            dlg = FontworkDialog(image, params, edit_layer, history)
            dlg.anchor = anchor
            if not dlg.run():
                return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
            p = dlg.p
            make_path, merge = dlg.make_path, dlg.merge
        else:
            p = fw.normalize(params)

        p = fw.normalize(public(p))
        save_json(LAST_FILE, p)

        # Historique : la version remplacée rejoint la liste des versions
        if edit_layer is not None:
            old = fw.normalize(public(params))
            if old != p:
                history.insert(0, {"date": params.get("_date", "?"), "params": public(old)})
            history = history[:MAX_HISTORY]

        image.undo_group_start()
        try:
            prep = fw.prepare(p)
            surf, origin = fw.draw(prep, p, 1.0)
            polys, bbox = prep["polys"], prep["bbox"]
            cx, cy = (bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0
            ax, ay = anchor_for(p, bbox, anchor)
            x = int(round(ax + origin[0] - cx))
            y = int(round(ay + origin[1] - cy))
            label = p["b_top_text"] if p["mode"] == "badge" else p["text"]
            first = (label.strip().splitlines() or ["texte"])[0][:30]

            if edit_layer is not None:
                layer = edit_layer
                update_layer_in_place(image, layer, surf, x, y)
                if layer.get_name().startswith("Fontwork : "):
                    layer.set_name("Fontwork : " + first)
            else:
                if sel:
                    parent = sel[0].get_parent()
                    pos = image.get_item_position(sel[0])
                else:
                    parent, pos = None, 0
                layer = write_layer(image, surf, x, y, "Fontwork : " + first, parent, pos)

            stored = dict(p)
            stored["_anchor"] = [anchor[0], anchor[1]]
            stored["_off"] = [x, y]
            stored["_date"] = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
            stored["_history"] = history
        except Exception as e:
            log_error("création du calque")
            image.undo_group_end()
            Gimp.displays_flush()
            msg = "Texte Fontwork : %s: %s" % (type(e).__name__, e)
            return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR,
                                               GLib.Error(msg))

        # Étapes de finition : une erreur n'annule pas le calque déjà créé
        warnings = []

        def step(label, func):
            try:
                func()
            except Exception as e:
                log_error(label)
                warnings.append("%s : %s: %s" % (label, type(e).__name__, e))

        step("enregistrement des réglages (texte modifiable)",
             lambda: write_parasite(layer, stored))

        # Zone centrale : l'ancien canal de ce badge est remplacé ou retiré
        old_zone = params.get("_zone") if edit_layer is not None else None
        if old_zone and not (p["mode"] == "badge" and p["b_sel_on"] and p["b_sel_mode"] == "canal"):
            step("suppression de l'ancienne zone", lambda: remove_channel(image, old_zone))
        if p["mode"] == "badge" and p["b_sel_on"]:
            rs = prep["R"] * p["b_sel_r"] / 100.0
            circle = (anchor[0] - rs, anchor[1] - rs, 2 * rs, 2 * rs)
            if p["b_sel_mode"] == "selection":
                step("sélection circulaire", lambda: image.select_ellipse(
                    Gimp.ChannelOps.REPLACE, *circle))
            else:
                zone = "Fontwork : zone centrale – " + first
                def make_zone():
                    if old_zone:
                        remove_channel(image, old_zone)
                    remove_channel(image, zone)
                    save_zone_channel(image, circle, zone)
                    stored["_zone"] = zone
                    write_parasite(layer, stored)
                step("zone centrale (canal)", make_zone)

        if make_path and polys:
            step("création du tracé", lambda: add_path(
                image, polys, x - origin[0], y - origin[1], "Fontwork : " + first))

        result = {"layer": layer}
        if merge:
            def do_merge():
                parent = layer.get_parent()
                siblings = parent.get_children() if parent else image.get_layers()
                if image.get_item_position(layer) + 1 >= len(siblings):
                    raise RuntimeError("aucun calque en dessous")
                try:
                    layer.detach_parasite(PARASITE)
                except Exception:
                    pass
                result["layer"] = image.merge_down(layer, Gimp.MergeType.EXPAND_AS_NECESSARY)
            step("fusion avec le calque du dessous", do_merge)

        step("sélection du calque", lambda: image.set_selected_layers([result["layer"]]))
        image.undo_group_end()
        Gimp.displays_flush()
        if warnings:
            Gimp.message("Texte Fontwork — calque créé, mais :\n• " + "\n• ".join(warnings) +
                         "\n\nDétails : fontwork-erreurs.log dans le dossier de profil GIMP.")
        return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


Gimp.main(FontworkPlugin.__gtype__, sys.argv)
