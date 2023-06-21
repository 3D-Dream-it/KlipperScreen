import logging
import re
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Pango

from ks_includes.screen_panel import ScreenPanel


def create_panel(*args):
    return MacroRunningPanel(*args)


class MacroRunningPanel(ScreenPanel):

    def __init__(self, screen, title):
        super().__init__(screen, title)

        scroll = self._gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox.set_halign(Gtk.Align.CENTER)
        vbox.set_valign(Gtk.Align.CENTER)
        label = Gtk.Label(label=_("Wait ..."))
        spinner = Gtk.Spinner()
        spinner.gtk_spinner_start()
        vbox.add(spinner)
        vbox.add(label)
        scroll.add(vbox)

        self.content.add(scroll)
