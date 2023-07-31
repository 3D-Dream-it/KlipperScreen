# -*- coding: utf-8 -*-
import logging
import os

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Pango
from datetime import datetime

from ks_includes.screen_panel import ScreenPanel


def create_panel(*args):
    return PrintPanel(*args)


class PrintPanel(ScreenPanel):
    cur_directory = "gcodes"
    dir_panels = {}
    filelist = {'gcodes': {'directories': [], 'files': []}}

    def __init__(self, screen, title):
        super().__init__(screen, title)
        sortdir = self._config.get_main_config().get("print_sort_dir", "name_asc")
        sortdir = sortdir.split('_')
        if sortdir[0] not in ["name", "date"] or sortdir[1] not in ["asc", "desc"]:
            sortdir = ["name", "asc"]
        self.sort_current = [sortdir[0], 0 if sortdir[1] == "asc" else 1]  # 0 for asc, 1 for desc
        self.sort_items = {
            "name": _("Name"),
            "date": _("Date")
        }
        self.sort_icon = ["arrow-up", "arrow-down"]
        self.scroll = self._gtk.ScrolledWindow()
        self.files = {}
        self.directories = {}
        self.labels['directories'] = {}
        self.labels['files'] = {}
        self.source = ""
        self.time_24 = self._config.get_main_config().getboolean("24htime", True)
        logging.info(f"24h time is {self.time_24}")

        sbox = Gtk.Box(spacing=0)
        sbox.set_vexpand(False)
        for i, (name, val) in enumerate(self.sort_items.items(), start=1):
            s = self._gtk.Button(None, val, f"color{i % 4}", .5, Gtk.PositionType.RIGHT, 1)
            s.get_style_context().add_class("buttons_slim")
            if name == self.sort_current[0]:
                s.set_image(self._gtk.Image(self.sort_icon[self.sort_current[1]], self._gtk.img_scale * self.bts))
            s.connect("clicked", self.change_sort, name)
            self.labels[f'sort_{name}'] = s
            sbox.add(s)
        refresh = self._gtk.Button("refresh", style="color4", scale=self.bts)
        refresh.get_style_context().add_class("buttons_slim")
        refresh.connect('clicked', self._refresh_files)
        sbox.add(refresh)
        sbox.set_hexpand(True)
        sbox.set_vexpand(False)

        pbox = Gtk.Box(spacing=0)
        pbox.set_hexpand(True)
        pbox.set_vexpand(False)
        self.labels['path'] = Gtk.Label()
        pbox.add(self.labels['path'])
        self.labels['path_box'] = pbox

        self.main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.main.set_vexpand(True)
        self.main.pack_start(sbox, False, False, 0)
        self.main.pack_start(pbox, False, False, 0)
        self.main.pack_start(self.scroll, True, True, 0)

        self.dir_panels['gcodes'] = Gtk.Grid()

        GLib.idle_add(self.reload_files)

        self.scroll.add(self.dir_panels['gcodes'])
        self.content.add(self.main)
        self._screen.files.add_file_callback(self._callback)
        self.showing_rename = False

    def activate(self):
        if self.cur_directory != "gcodes":
            self.change_dir(None, "gcodes")
        self._refresh_files()

    def add_directory(self, directory, show=True):
        parent_dir = os.path.dirname(directory)
        if directory not in self.filelist:
            self.filelist[directory] = {'directories': [], 'files': [], 'modified': 0}
            self.filelist[parent_dir]['directories'].append(directory)

        if directory not in self.labels['directories']:
            self._create_row(directory)
        reverse = self.sort_current[1] != 0
        dirs = sorted(
            self.filelist[parent_dir]['directories'],
            reverse=reverse, key=lambda item: self.filelist[item]['modified']
        ) if self.sort_current[0] == "date" else sorted(self.filelist[parent_dir]['directories'], reverse=reverse)

        pos = dirs.index(directory)

        self.dir_panels[parent_dir].insert_row(pos)
        self.dir_panels[parent_dir].attach(self.directories[directory], 0, pos, 1, 1)
        if show is True:
            self.dir_panels[parent_dir].show_all()

    def add_file(self, filepath, show=True):
        fileinfo = self._screen.files.get_file_info(filepath)
        if fileinfo is None:
            return
        filename = os.path.basename(filepath)
        if filename.startswith("."):
            return
        directory = os.path.dirname(os.path.join("gcodes", filepath))
        d = directory.split(os.sep)
        for i in range(1, len(d)):
            curdir = os.path.join(*d[:i])
            newdir = os.path.join(*d[:i + 1])
            if newdir not in self.filelist[curdir]['directories']:
                if d[i].startswith("."):
                    return
                self.add_directory(newdir)

        if filename not in self.filelist[directory]['files']:
            for i in range(1, len(d)):
                curdir = os.path.join(*d[:i + 1])
                if curdir != "gcodes" and fileinfo['modified'] > self.filelist[curdir]['modified']:
                    self.filelist[curdir]['modified'] = fileinfo['modified']
                    if self.time_24:
                        time = f':<b>  {datetime.fromtimestamp(fileinfo["modified"]):%Y-%m-%d %H:%M}</b>'
                    else:
                        time = f':<b>  {datetime.fromtimestamp(fileinfo["modified"]):%Y-%m-%d %I:%M %p}</b>'
                    info = _("Modified") + time
                    info += "\n" + _("Size") + f':<b>  {self.format_size(fileinfo["size"])}</b>'
                    self.labels['directories'][curdir]['info'].set_markup(info)
            self.filelist[directory]['files'].append(filename)

        if filepath not in self.files:
            self._create_row(filepath, filename)
        reverse = self.sort_current[1] != 0
        files = sorted(
            self.filelist[directory]['files'],
            reverse=reverse,
            key=lambda item: self._screen.files.get_file_info(f"{directory}/{item}"[7:])['modified']
        ) if self.sort_current[0] == "date" else sorted(self.filelist[directory]['files'], reverse=reverse)

        pos = files.index(filename)
        pos += len(self.filelist[directory]['directories'])

        self.dir_panels[directory].insert_row(pos)
        self.dir_panels[directory].attach(self.files[filepath], 0, pos, 1, 1)
        if show is True:
            self.dir_panels[directory].show_all()
        return False

    def _create_row(self, fullpath, filename=None):
        name = Gtk.Label()
        name.get_style_context().add_class("print-filename")
        if filename:
            name.set_markup(f'<big><b>{os.path.splitext(filename)[0].replace("_", " ")}</b></big>')
        else:
            name.set_markup(f"<big><b>{os.path.split(fullpath)[-1]}</b></big>")
        name.set_hexpand(True)
        name.set_halign(Gtk.Align.START)
        name.set_line_wrap(True)
        name.set_line_wrap_mode(Pango.WrapMode.CHAR)

        info = Gtk.Label()
        info.set_hexpand(True)
        info.set_halign(Gtk.Align.START)
        info.get_style_context().add_class("print-info")

        delete = self._gtk.Button("delete", style="color1", scale=self.bts)
        delete.set_hexpand(False)
        rename = self._gtk.Button("files", style="color2", scale=self.bts)
        rename.set_hexpand(False)

        if filename:
            action = self._gtk.Button("print", style="color3")
            action.connect("clicked", self.confirm_print, fullpath)
            info.set_markup(self.get_file_info_str(fullpath))
            icon = Gtk.Button()
            icon.connect("clicked", self.confirm_print, fullpath)
            delete.connect("clicked", self.confirm_delete_file, f"gcodes/{fullpath}")
            rename.connect("clicked", self.show_rename, f"gcodes/{fullpath}")
            GLib.idle_add(self.image_load, fullpath)
        else:
            action = self._gtk.Button("load", style="color3")
            action.connect("clicked", self.change_dir, fullpath)
            icon = self._gtk.Button("folder")
            icon.connect("clicked", self.change_dir, fullpath)
            delete.connect("clicked", self.confirm_delete_directory, fullpath)
            rename.connect("clicked", self.show_rename, fullpath)
        icon.set_hexpand(False)
        action.set_hexpand(False)
        action.set_halign(Gtk.Align.END)

        delete.connect("clicked", self.confirm_delete_file, f"gcodes/{fullpath}")

        row = Gtk.Grid()
        row.get_style_context().add_class("frame-item")
        row.set_hexpand(True)
        row.set_vexpand(False)
        row.attach(icon, 0, 0, 1, 2)
        row.attach(name, 1, 0, 3, 1)
        row.attach(info, 1, 1, 1, 1)
        row.attach(rename, 2, 1, 1, 1)
        row.attach(delete, 3, 1, 1, 1)

        if not filename or (filename and os.path.splitext(filename)[1] in [".gcode", ".g", ".gco"]):
            row.attach(action, 4, 0, 1, 2)

        if filename is not None:
            self.files[fullpath] = row
            self.labels['files'][fullpath] = {
                "icon": icon,
                "info": info,
                "name": name
            }
        else:
            self.directories[fullpath] = row
            self.labels['directories'][fullpath] = {
                "info": info,
                "name": name
            }
            self.dir_panels[fullpath] = Gtk.Grid()

    def image_load(self, filepath):
        pixbuf = self.get_file_image(filepath, small=True)
        if pixbuf is not None:
            self.labels['files'][filepath]['icon'].set_image(Gtk.Image.new_from_pixbuf(pixbuf))
        else:
            self.labels['files'][filepath]['icon'].set_image(self._gtk.Image("file"))
        return False

    def confirm_delete_file(self, widget, filepath):
        logging.debug(f"Sending delete_file {filepath}")
        params = {"path": f"{filepath}"}
        self._screen._confirm_send_action(
            None,
            _("Delete File?") + "\n\n" + filepath,
            "server.files.delete_file",
            params
        )

    def confirm_delete_directory(self, widget, dirpath):
        logging.debug(f"Sending delete_directory {dirpath}")
        params = {"path": f"{dirpath}", "force": True}
        self._screen._confirm_send_action(
            None,
            _("Delete Directory?") + "\n\n" + dirpath,
            "server.files.delete_directory",
            params
        )

    def back(self):
        if self.showing_rename:
            self.hide_rename()
            return True
        if os.path.dirname(self.cur_directory):
            self.change_dir(None, os.path.dirname(self.cur_directory))
            return True
        return False

    def change_dir(self, widget, directory):
        if directory not in self.dir_panels:
            return
        logging.debug(f"Changing dir to {directory}")

        for child in self.scroll.get_children():
            self.scroll.remove(child)
        self.cur_directory = directory
        self.labels['path'].set_text(f"  {self.cur_directory[7:]}")

        self.scroll.add(self.dir_panels[directory])
        self.content.show_all()

    def change_sort(self, widget, key):
        if self.sort_current[0] == key:
            self.sort_current[1] = (self.sort_current[1] + 1) % 2
        else:
            oldkey = self.sort_current[0]
            logging.info(f"Changing sort_{oldkey} to {self.sort_items[self.sort_current[0]]}")
            self.labels[f'sort_{oldkey}'].set_image(None)
            self.labels[f'sort_{oldkey}'].show_all()
            self.sort_current = [key, 0]
        self.labels[f'sort_{key}'].set_image(self._gtk.Image(self.sort_icon[self.sort_current[1]],
                                                             self._gtk.img_scale * self.bts))
        self.labels[f'sort_{key}'].show()
        GLib.idle_add(self.reload_files)

        self._config.set("main", "print_sort_dir", f'{key}_{"asc" if self.sort_current[1] == 0 else "desc"}')
        self._config.save_user_config_options()

    def confirm_print(self, widget, filename):

        buttons = [
            {"name": _("Print"), "response": Gtk.ResponseType.OK},
            {"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL}
        ]

        label = Gtk.Label()
        label.set_markup(f"<b>{filename}</b>\n")
        label.set_hexpand(True)
        label.set_halign(Gtk.Align.CENTER)
        label.set_vexpand(True)
        label.set_valign(Gtk.Align.CENTER)
        label.set_line_wrap(True)
        label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        grid = Gtk.Grid()
        grid.set_vexpand(True)
        grid.set_halign(Gtk.Align.CENTER)
        grid.set_valign(Gtk.Align.CENTER)
        grid.attach(label, 0, 0, 1, 1)

        pixbuf = self.get_file_image(filename, self._screen.width * .9, self._screen.height * .6)
        if pixbuf is not None:
            image = Gtk.Image.new_from_pixbuf(pixbuf)
            image.set_vexpand(False)
            grid.attach(image, 0, 1, 1, 1)

        metadata_response = self._screen.apiclient.send_request(f"server/files/metadata?filename={filename}")
        if metadata_response:
            metadata = metadata_response['result']
            if "filament_weight_total" in metadata and "estimated_time" in metadata:
                checkgrid = Gtk.Grid()
                title = Gtk.Label()
                title.set_markup(f"<b>{_('Filament Usage')}</b>")
                title.set_hexpand(True)
                title.set_halign(Gtk.Align.CENTER)
                req = Gtk.Label()
                req.set_markup(f"<b>{_('Required')}</b>")
                req.set_halign(Gtk.Align.CENTER)
                avail = Gtk.Label()
                avail.set_markup(f"<b>{_('Available')}</b>")
                avail.set_halign(Gtk.Align.CENTER)
                estim = Gtk.Label()
                estim.set_markup(f"<b>{_('Estimate')}</b>")
                estim.set_halign(Gtk.Align.CENTER)

                checkgrid.attach(title, 0, 0, 3, 1)
                checkgrid.attach(req, 0, 1, 1, 1)
                checkgrid.attach(avail, 1, 1, 1, 1)
                checkgrid.attach(estim, 2, 1, 1, 1)

                scales = self._printer.get_scales()
                reqs = metadata['filament_weight_total']
                reqs = reqs if type(reqs) is list else [reqs]
                i = 2
                for device, value in zip(scales, reqs):
                    a = Gtk.Label(f"{value:.2f} g" if value < 1000 else f"{value / 1000:.2f} Kg")
                    a.set_halign(Gtk.Align.START)
                    checkgrid.attach(a, 0, i, 1, 1)

                    w = self._printer.get_dev_stat(device, 'weight')
                    b = Gtk.Label(f"{w:.2f} g" if w < 1000 else f"{w / 1000:.2f} Kg")
                    b.set_halign(Gtk.Align.START)
                    checkgrid.attach(b, 1, i, 1, 1)

                    if w >= (value + 10):
                        c = self._gtk.Button("complete", scale=self.bts)
                    else:
                        time = metadata['estimated_time']
                        time = w / value * time if value > 0 else 0
                        c = Gtk.Label("%02dh %02dm %02ds" % self.seconds_to_time(time))
                    c.set_halign(Gtk.Align.CENTER)
                    checkgrid.attach(c, 2, i, 1, 1)
                    i += 1
                box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
                box.add(checkgrid)
                grid.attach(box, 1, 0, 1, 2)

        dialog = self._gtk.Dialog(self._screen, buttons, grid, self.confirm_print_response, filename)
        dialog.set_title(_("Print"))

    def seconds_to_time(self, seconds):
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        seconds = int((seconds % 3600) % 60)
        return hours, minutes, seconds

    def confirm_print_response(self, dialog, response_id, filename):
        self._gtk.remove_dialog(dialog)
        if response_id == Gtk.ResponseType.CANCEL:
            return
        logging.info(f"Starting print: {filename}")
        self._screen._ws.klippy.print_start(filename)

    def delete_file(self, filename):
        directory = os.path.join("gcodes", os.path.dirname(filename)) if os.path.dirname(filename) else "gcodes"
        if directory not in self.filelist or os.path.basename(filename).startswith("."):
            return
        try:
            self.filelist[directory]["files"].pop(self.filelist[directory]["files"].index(os.path.basename(filename)))
        except Exception as e:
            logging.exception(e)
        dir_parts = directory.split(os.sep)
        i = len(dir_parts)
        while i > 1:
            cur_dir = os.path.join(*dir_parts[:i])
            if len(self.filelist[cur_dir]['directories']) > 0 or len(self.filelist[cur_dir]['files']) > 0:
                break
            parent_dir = os.path.dirname(cur_dir)

            if self.cur_directory == cur_dir:
                self.change_dir(None, parent_dir)

            del self.filelist[cur_dir]
            self.filelist[parent_dir]['directories'].pop(self.filelist[parent_dir]['directories'].index(cur_dir))
            self.dir_panels[parent_dir].remove(self.directories[cur_dir])
            del self.directories[cur_dir]
            del self.labels['directories'][cur_dir]
            self.dir_panels[parent_dir].show_all()
            i -= 1

        try:
            self.dir_panels[directory].remove(self.files[filename])
        except Exception as e:
            logging.exception(e)
        self.dir_panels[directory].show_all()
        self.files.pop(filename)

    def get_file_info_str(self, filename):

        fileinfo = self._screen.files.get_file_info(filename)
        if fileinfo is None:
            return
        info = _("Uploaded")
        if self.time_24:
            info += f':<b>  {datetime.fromtimestamp(fileinfo["modified"]):%Y-%m-%d %H:%M}</b>\n'
        else:
            info += f':<b>  {datetime.fromtimestamp(fileinfo["modified"]):%Y-%m-%d %I:%M %p}</b>\n'

        if "size" in fileinfo:
            info += _("Size") + f':  <b>{self.format_size(fileinfo["size"])}</b>\n'
        if "estimated_time" in fileinfo:
            info += _("Print Time") + f':  <b>{self.format_time(fileinfo["estimated_time"])}</b>'
        return info

    def reload_files(self, widget=None):
        self.filelist = {'gcodes': {'directories': [], 'files': []}}
        for dirpan in self.dir_panels:
            for child in self.dir_panels[dirpan].get_children():
                self.dir_panels[dirpan].remove(child)

        flist = sorted(self._screen.files.get_file_list(), key=lambda item: '/' in item)
        for file in flist:
            GLib.idle_add(self.add_file, file)
        return False

    def update_file(self, filename):
        if filename not in self.labels['files']:
            logging.debug(f"Cannot update file, file not in labels: {filename}")
            return

        logging.info(f"Updating file {filename}")
        self.labels['files'][filename]['info'].set_markup(self.get_file_info_str(filename))

        # Update icon
        GLib.idle_add(self.image_load, filename)

    def _callback(self, newfiles, deletedfiles, updatedfiles=None):
        logging.debug(f"newfiles: {newfiles}")
        for file in newfiles:
            self.add_file(file)
        logging.debug(f"deletedfiles: {deletedfiles}")
        for file in deletedfiles:
            self.delete_file(file)
        if updatedfiles is not None:
            logging.debug(f"updatefiles: {updatedfiles}")
            for file in updatedfiles:
                self.update_file(file)
        return False

    def _refresh_files(self, widget=None):
        self._files.refresh_files()
        return False

    def show_rename(self, widget, fullpath):
        self.source = fullpath
        logging.info(self.source)

        for child in self.content.get_children():
            self.content.remove(child)

        if "rename_file" not in self.labels:
            self._create_rename_box(fullpath)
        self.content.add(self.labels['rename_file'])
        self.labels['new_name'].set_text(fullpath[7:])
        self.labels['new_name'].grab_focus_without_selecting()
        self.showing_rename = True

    def _create_rename_box(self, fullpath):
        lbl = self._gtk.Label(_("Rename/Move:"))
        lbl.set_halign(Gtk.Align.START)
        lbl.set_hexpand(False)
        self.labels['new_name'] = Gtk.Entry()
        self.labels['new_name'].set_text(fullpath)
        self.labels['new_name'].set_hexpand(True)
        self.labels['new_name'].connect("activate", self.rename)
        self.labels['new_name'].connect("focus-in-event", self._screen.show_keyboard)

        save = self._gtk.Button("complete", _("Save"), "color3")
        save.set_hexpand(False)
        save.connect("clicked", self.rename)

        box = Gtk.Box()
        box.pack_start(self.labels['new_name'], True, True, 5)
        box.pack_start(save, False, False, 5)

        self.labels['rename_file'] = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        self.labels['rename_file'].set_valign(Gtk.Align.CENTER)
        self.labels['rename_file'].set_hexpand(True)
        self.labels['rename_file'].set_vexpand(True)
        self.labels['rename_file'].pack_start(lbl, True, True, 5)
        self.labels['rename_file'].pack_start(box, True, True, 5)

    def hide_rename(self):
        self._screen.remove_keyboard()
        for child in self.content.get_children():
            self.content.remove(child)
        self.content.add(self.main)
        self.content.show()
        self.showing_rename = False

    def rename(self, widget):
        params = {"source": self.source, "dest": f"gcodes/{self.labels['new_name'].get_text()}"}
        self._screen._send_action(
            widget,
            "server.files.move",
            params
        )
        self.back()
        GLib.timeout_add_seconds(2, self._refresh_files)
