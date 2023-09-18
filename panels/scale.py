import gi
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel
from ks_includes.widgets.decimal_keypad import DecimalKeypad

def create_panel(*args):
    return ScalePanel(*args)


class ScalePanel(ScreenPanel):
    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.presets = {
            "tare_preset": "Tare (Kg)",
            "diameter_preset": "Diameter (mm)",
            "density_preset": "Density (g/cm3)",
        }
        self.grid = self._gtk.HomogeneousGrid()
        self.grid.attach(self.create_left_panel(), 0, 0, 1, 1)
        self.grid.attach(self.create_right_panel(), 1, 0, 1, 1)
        self.content.add(self.grid)

    def add_device(self, device, count):
        devname = device.split()[1] if len(device.split()) > 1 else device
        if devname.startswith("_"):
            return False
        
        name = self._gtk.Button("scale", devname.capitalize().replace("_", " "), "color"+str(count), self.bts, Gtk.PositionType.LEFT, 1)
        name.connect("clicked", self.show_scale_config, device)
        name.set_alignment(0, .5)
        name.set_vexpand(False)

        weight = self._gtk.Button(label="")
        weight.set_vexpand(False)

        self.devices[device] = {
            "name": name,
            "weight": weight,
            "class": "",
            "can_target": False,
            "visible": True
        }

        self.labels['devices'].insert_row(count)
        self.labels['devices'].attach(name, 0, count, 1, 1)
        self.labels['devices'].attach(weight, 1, count, 1, 1)
        self.labels['devices'].show_all()
        return True

    def create_left_panel(self):
        self.labels['devices'] = Gtk.Grid()
        self.labels['devices'].get_style_context().add_class('heater-grid')
        self.labels['devices'].set_vexpand(False)

        name = Gtk.Label("")
        temp = Gtk.Label(_("Weight (Kg)"))
        temp.get_style_context().add_class("heater-grid-temp")

        self.labels['devices'].attach(name, 0, 0, 1, 1)
        self.labels['devices'].attach(temp, 1, 0, 1, 1)

        scroll = self._gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self.labels['devices'])

        self.left_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.left_panel.add(scroll)

        for idx, d in enumerate(self._printer.get_scales()):
            self.add_device(d, idx + 1)

        return self.left_panel

    def create_right_panel(self):
        placeholder = Gtk.Label("Seleziona una bilancia da configurare")
        right = self._gtk.HomogeneousGrid()
        right.attach(placeholder, 0, 0, 1, 1)
        return right

    def show_scale_config(self, widget, device):
        scale_master_config = self._printer.get_config_section("scale")
        scale_config = self._printer.get_config_section(device)
        if not scale_master_config or not scale_config:
            return
        
        scroll = self._gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox.set_halign(Gtk.Align.CENTER)
        vbox.set_valign(Gtk.Align.CENTER)

        calibrate = self._gtk.Button("calibrate", _("Calibration"), "color1", self.bts, Gtk.PositionType.LEFT, 1)
        calibrate.connect("clicked", self.init_calibration, device)
        vbox.add(calibrate)
        
        for name, header in self.presets.items():
            if name in scale_master_config:
                values = scale_master_config[name].replace(" ", "").split(',') # string values
                target = name.replace("_preset", "")
                current = self._printer.get_dev_stat(device, target) # float value
                header = header + f': {current:.2f}'
                preset = self.create_preset(device, values, str(current), target, header)
                vbox.add(preset)
        
        close = self._gtk.Button('cancel', _('Close'), None, self.bts, Gtk.PositionType.LEFT, 1)
        close.connect("clicked", self.hide_scale_config)
        vbox.add(close)

        scroll.add(vbox)
        self.grid.remove_column(1)
        self.grid.attach(scroll, 1, 0, 1, 1)
        self.grid.show_all()

    def hide_scale_config(self, widget):
        self.grid.remove_column(1)
        self.grid.attach(self.create_right_panel(), 1, 0, 1, 1)
        self.grid.show_all()

    def create_preset(self, device, values, current, target, header):
        distgrid = self._gtk.HomogeneousGrid()
        for idx, value in enumerate(values):
            self.labels[value] = self._gtk.Button(label=value, scale=self.bts)
            self.labels[value].set_hexpand(False)
            self.labels[value].connect("clicked", self.update_target, device, target, value)
            ctx = self.labels[value].get_style_context()
            if idx == 0:
                ctx.add_class("distbutton_top")
            else:
                ctx.add_class("distbutton")
            if value == current:
                ctx.add_class("distbutton_active")
            distgrid.attach(self.labels[value], idx, 1, 1, 1)
        custom = self._gtk.Button(label='...', scale=self.bts)
        custom.connect("clicked", self.show_numpad, device, target)
        ctx = custom.get_style_context()
        ctx.add_class("distbutton_bottom")
        if current not in values:
            ctx.add_class("distbutton_active")
        distgrid.attach(custom, len(values), 1, 1, 1)
        
        title = Gtk.Label(header)
        title.set_halign(Gtk.Align.CENTER)
        title.set_vexpand(False)
        distgrid.attach(title, 0, 0, len(values), 1)
        distgrid.set_hexpand(True)
        return distgrid

    def update_target(self, widget, device, target, value):
        self._screen._ws.klippy.gcode_script(KlippyGcodes.update_scale(device, target, value))
        self.hide_config(widget)

    def show_numpad(self, widget, device, target):
        def on_value_confirm(value):
            self.update_target(widget, device, target, value)

        # if "keypad" not in self.labels:
        self.labels["keypad"] = DecimalKeypad(self._screen, on_value_confirm, self.hide_config)
        self.labels["keypad"].clear()

        self.grid.remove_column(1)
        self.grid.attach(self.labels["keypad"], 1, 0, 1, 1)
        self.grid.show_all()

    def hide_config(self, widget):
        self.grid.remove_column(1)
        self.grid.attach(self.create_right_panel(), 1, 0, 1, 1)
        self.grid.show_all()
    
    def init_calibration(self, widget, device):
        def on_value_confirm(value):
            self._screen._ws.klippy.gcode_script(KlippyGcodes.scale_calibration(device, value))
            self.hide_config(widget)

        # if "keypad2" not in self.labels:
        self.labels["keypad"] = DecimalKeypad(self._screen, on_value_confirm, self.hide_config, title=_("Known weight (Kg)"))
        self.labels["keypad"].clear()

        self.grid.remove_column(1)
        self.grid.attach(self.labels["keypad"], 1, 0, 1, 1)
        self.grid.show_all()

    def process_update(self, action, data):
        if action != "notify_status_update":
            return
        
        for x in (self._printer.get_scales()):
            self.update_weight(
                x, 
                self._printer.get_dev_stat(x, "weight"),
                self._printer.get_dev_stat(x, "tare")
            )
