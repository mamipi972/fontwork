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
import traceback
import json
import os
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
        self.rb_badge = Gtk.RadioButton.new_with_label_from_widget(self.rb_text, "Badge / sceau")
        (self.rb_badge if self.p["mode"] == "badge" else self.rb_text).set_active(True)
        self.rb_text.connect("toggled", self._on_mode)
        mbox.pack_start(self.rb_text, False, False, 0)
        mbox.pack_start(self.rb_badge, False, False, 0)
        left.pack_start(mbox, False, False, 0)

        sbox = Gtk.Box(spacing=6)
        sbox.pack_start(Gtk.Label(label="Modèle :"), False, False, 0)
        self.style_combo = Gtk.ComboBoxText()
        self.style_combo.connect("changed", self._on_style)
        sbox.pack_start(self.style_combo, True, True, 0)
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
        nb.append_page(self._page(self._page_text()), Gtk.Label(label="Texte"))
        nb.append_page(self._page(self._page_shape()), Gtk.Label(label="Forme"))
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
        self.stack.set_visible_child_name(self.p["mode"])
        self.keep_texts.set_visible(self.p["mode"] == "badge")

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
        fbx.connect("selected-children-changed", self._on_shape)
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

    # ------------------------------------------------- pages mode badge
    def _page_b_rings(self):
        g = self._grid()
        self._section(g, "Badge")
        self._slider(g, "Diamètre (px)", "b_size", 100, 4000, 10)
        self._slider(g, "Rotation (°)", "b_rotation", -180, 180, 1)
        for i in range(1, 5):
            self._section(g, "Anneau %d" % i)
            self._check(g, "Afficher l'anneau %d" % i, "b_r%d_on" % i)
            self._slider(g, "Rayon (%)", "b_r%d_r" % i, 1, 120, 0.5, 1)
            self._color(g, "Fond (transparent possible)", "b_r%d_fill" % i)
            self._slider(g, "Épaisseur du trait", "b_r%d_sw" % i, 0, 60, 0.5, 1)
            self._color(g, "Couleur du trait", "b_r%d_stroke" % i)
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
        self._section(g, "Sélection pour une photo ou un logo")
        self._check(g, "Créer une sélection circulaire en validant", "b_sel_on")
        self._slider(g, "Rayon de la sélection (%)", "b_sel_r", 5, 120, 0.5, 1)
        return g

    def _page_b_effects(self):
        g = self._grid()
        self._section(g, "Finition")
        self._combo(g, "Métal", "b_metal", [("aucun", "Aucun (couleurs choisies)"),
                                            ("or", "Or"), ("argent", "Argent"),
                                            ("bronze", "Bronze")])
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
    def _fill_styles(self):
        self.loading_styles = True
        self.style_combo.remove_all()
        self.style_combo.append("", "— choisir un modèle —")
        if self.p["mode"] == "badge":
            for i, (name, _) in enumerate(fw.BADGE_PRESETS):
                self.style_combo.append("b%d" % i, name)
        else:
            for i, (name, _) in enumerate(fw.PRESETS):
                self.style_combo.append("p%d" % i, name)
        for name, st in sorted(load_json(STYLES_FILE, {}).items()):
            if st.get("mode", "texte") == self.p["mode"]:
                self.style_combo.append("u:" + name, "★ " + name)
        self.style_combo.set_active_id("")
        self.loading_styles = False

    def _on_style(self, combo):
        sid = combo.get_active_id()
        if not sid or getattr(self, "loading_styles", False):
            return
        if sid.startswith("u:"):
            style = load_json(STYLES_FILE, {}).get(sid[2:], {})
        elif sid.startswith("b"):
            style = dict(fw.BADGE_PRESETS[int(sid[1:])][1], mode="badge")
        else:
            style = fw.PRESETS[int(sid[1:])][1]
        if style.get("mode") == "badge":
            self.p = fw.apply_badge_preset(self.p, style, self.keep_texts.get_active())
        else:
            self.p = fw.apply_preset(self.p, style)
        self._sync_widgets()
        self._changed()

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
            keys = fw.BADGE_KEYS if self.p["mode"] == "badge" else fw.PRESET_KEYS
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

    def _on_mode(self, _btn):
        mode = "badge" if self.rb_badge.get_active() else "texte"
        if mode == self.p["mode"]:
            return
        self.p["mode"] = mode
        self.stack.set_visible_child_name(mode)
        self.keep_texts.set_visible(mode == "badge")
        self._fill_styles()
        self._changed()

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
        (self.rb_badge if self.p["mode"] == "badge" else self.rb_text).set_active(True)
        self.stack.set_visible_child_name(self.p["mode"])
        self.keep_texts.set_visible(self.p["mode"] == "badge")
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

    def _on_shape(self, box):
        sel = box.get_selected_children()
        if sel:
            self._set("shape", sel[0].shape_key)

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
        self._sens("line_gap", bool(p["lines_sep"]))
        self._sens("persp", bool(p["rot_x"] or p["rot_y"]))
        for i in range(1, 5):
            for k in ("r", "fill", "sw", "stroke"):
                self._sens("b_r%d_%s" % (i, k), bool(p["b_r%d_on" % i]))
        for k in ("b_fil_r", "b_fil_w", "b_fil_col", "b_fil_gap"):
            self._sens(k, bool(p["b_fil_on"]))
        for k in ("b_mot_char", "b_mot_font", "b_mot_n", "b_mot_r", "b_mot_size",
                  "b_mot_col", "b_mot_start", "b_mot_follow"):
            self._sens(k, bool(p["b_mot_on"]))
        self._sens("b_sel_r", bool(p["b_sel_on"]))
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
        keys = sorted(fw.BADGE_KEYS) if self.p["mode"] == "badge" else fw.GEOMETRY_KEYS
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
            self.status.set_text("Taille finale : %d × %d px   (aperçu à %d %%)"
                                 % (x1 - x0, y1 - y0, round(s * 100)))
        except Exception as e:
            self.status.set_text("Erreur : %s" % e)

    # ------------------------------------------------- aperçu sur l'image
    def placement(self, origin, bbox):
        cx, cy = (bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0
        return (int(round(self.anchor[0] + origin[0] - cx)),
                int(round(self.anchor[1] + origin[1] - cy)))

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
            "Crée un calque de texte déformé (arc, cercle, spirale, vague, entonnoir…) "
            "ou un badge circulaire (textes en cercle, anneaux, motifs), avec contour, "
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
            x = int(round(anchor[0] + origin[0] - cx))
            y = int(round(anchor[1] + origin[1] - cy))
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

        if p["mode"] == "badge" and p["b_sel_on"]:
            rs = prep["R"] * p["b_sel_r"] / 100.0
            step("sélection circulaire", lambda: image.select_ellipse(
                Gimp.ChannelOps.REPLACE, anchor[0] - rs, anchor[1] - rs, 2 * rs, 2 * rs))

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
