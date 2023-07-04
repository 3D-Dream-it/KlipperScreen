import logging
import re
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Pango

from ks_includes.screen_panel import ScreenPanel


def create_panel(*args):
    return NozzleOffsetPanel(*args)


class NozzleOffsetPanel(ScreenPanel):
    distances = ['.01', '.1', '1', '10']
    distance = distances[0]
    active_direction = None
    label_mapping = {
        'off_x': 'X',
        'off_y': 'Y'
    }

    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.buttons = {
            '+': self._gtk.Button("plus", _("Increase"), "color1"),
            '-': self._gtk.Button("minus", _("Decrease"), "color2"),
            'save': self._gtk.Button("complete", _("Save"), None),
            'off_x': self._gtk.Button(None, "X", "color3", None, Gtk.PositionType.LEFT, 1),
            'off_y': self._gtk.Button(None, "Y", "color4", None, Gtk.PositionType.LEFT, 1),
        }
        self.buttons['+'].connect("clicked", self.modify, "+")
        self.buttons['-'].connect("clicked", self.modify, "-")
        self.buttons['save'].connect("clicked", self.persist)
        self.buttons['off_x'].connect("clicked", self.toggle, 'off_x')
        self.buttons['off_y'].connect("clicked", self.toggle, 'off_y')

        contentgrid = self._gtk.HomogeneousGrid()
        contentgrid.attach(self.buttons['+'], 0, 0, 1, 1)
        contentgrid.attach(self.buttons['-'], 0, 1, 1, 1)
        contentgrid.attach(self.buttons['off_x'], 1, 0, 3, 1)
        contentgrid.attach(self.buttons['off_y'], 1, 1, 3, 1)

        self.labels['move_dist'] = Gtk.Label(_("Move Distance (mm)"))
        distgrid = self._gtk.HomogeneousGrid()
        for j, i in enumerate(self.distances):
            self.labels[i] = self._gtk.Button(label=i)
            self.labels[i].set_direction(Gtk.TextDirection.LTR)
            self.labels[i].connect("clicked", self.change_distance, i)
            ctx = self.labels[i].get_style_context()
            if (self._screen.lang_ltr and j == 0) or (not self._screen.lang_ltr and j == len(self.distances) - 1):
                ctx.add_class("distbutton_top")
            elif (not self._screen.lang_ltr and j == 0) or (self._screen.lang_ltr and j == len(self.distances) - 1):
                ctx.add_class("distbutton_bottom")
            else:
                ctx.add_class("distbutton")
            if i == self.distance:
                ctx.add_class("distbutton_active")
            distgrid.attach(self.labels[i], j, 1, 1, 1)
        distgrid.attach(Gtk.Label("Step (mm)"), 0, 0, len(self.distances), 1)
        

        self.labels['offset_menu'] = Gtk.Grid()
        self.labels['offset_menu'].attach(contentgrid, 0, 0, 4, 2)
        self.labels['offset_menu'].attach(self.buttons['save'], 0, 2, 1, 1)
        self.labels['offset_menu'].attach(distgrid, 1, 2, 3, 1)

        self.content.add(self.labels['offset_menu'])

        printer_cfg = self._printer.get_config_section("printer")

    def activate(self):
        if len(self._printer.get_tools()) != 2:
            raise Exception("Servono esattamente due tools per questa funzione!")
        if self._printer.state in ["printing", "paused"]:
            raise Exception("Impossibile utilizzare questa funzione durante la stampa!")
        if "xyz" != self._printer.get_stat("toolhead", "homed_axes"):
            self._screen._ws.klippy.gcode_script('G28')
        self._screen._ws.klippy.gcode_script('T1')
    
    def change_distance(self, widget, distance):
        logging.info(f"### Distance {distance}")
        self.labels[f"{self.distance}"].get_style_context().remove_class("distbutton_active")
        self.labels[f"{distance}"].get_style_context().add_class("distbutton_active")
        self.distance = distance

    def modify(self, widget, direction):
        if self.active_direction not in self.label_mapping.keys():
            return
        lbl = self.label_mapping[self.active_direction]
        stp = direction + self.distance
        command = f"SET_GCODE_OFFSET {lbl}_ADJUST={stp} MOVE=0"
        logging.info(f'sending: {command}')
        self._screen._ws.klippy.gcode_script(command)

    def persist(self, widget):
        homed_axes = self._printer.get_stat("toolhead", "homed_axes")
        if homed_axes == "xyz":
            self._screen._ws.klippy.gcode_script(f"SAVE_VARIABLE VARIABLE=x_offset VALUE={self.x_offset:.2f}")
            self._screen._ws.klippy.gcode_script(f"SAVE_VARIABLE VARIABLE=y_offset VALUE={self.y_offset:.2f}")
            self._screen.show_popup_message("Le modifiche sono state salvate", 1)
    
    def toggle(self, widget, direction):
        for p in ('off_x', 'off_y'):
            self.buttons[p].get_style_context().remove_class("button_active")

        if self.active_direction == direction:
            self.active_direction = None
            self.buttons[direction].get_style_context().remove_class("button_active")
        else:
            self.active_direction = direction
            self.buttons[direction].get_style_context().add_class("button_active")

    def process_update(self, action, data):
        if action == "notify_busy":
            return

        if action != "notify_status_update":
            return

        homed_axes = self._printer.get_stat("toolhead", "homed_axes")
        if homed_axes == "xyz":
            if "gcode_move" in data and "gcode_position" in data["gcode_move"]:
                self.x_offset = data['gcode_move']['homing_origin'][0]
                self.buttons['off_x'].set_label(f"X: {self.x_offset:.2f}")
                self.y_offset = data['gcode_move']['homing_origin'][1]
                self.buttons['off_y'].set_label(f"Y: {self.y_offset:.2f}")
