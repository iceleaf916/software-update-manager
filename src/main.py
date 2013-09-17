#! /usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2011~2013 Deepin, Inc.
#               2011~2013 Kaisheng Ye
#
# Author:     Kaisheng Ye <kaisheng.ye@gmail.com>
# Maintainer: Kaisheng Ye <kaisheng.ye@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

#import os
#from deepin_utils.file import get_parent_dir
#from dtk.ui.init_skin import init_skin
#app_theme = init_skin(
    #"deepin-software-update-manager",
    #"1.0",
    #"colourless_glass",
    #os.path.join(get_parent_dir(__file__, 2), "skin"),
    #os.path.join(get_parent_dir(__file__, 2), "app_theme")
#)

from dtk.ui.init_skin import init_theme
init_theme()

import os
import gtk
import sys
import dbus
import dbus.service
import dbus.mainloop.glib
from dbus.mainloop.glib import DBusGMainLoop

from dtk.ui.application import Application
from dtk.ui.box import BackgroundBox
from dtk.ui.theme import ui_theme
from dtk.ui.draw import draw_vlinear
from dtk.ui.statusbar import Statusbar
from dtk.ui.button import Button
from dtk.ui.label import Label
from dtk.ui.utils import container_remove_all
from dtk.ui.treeview import TreeView, TreeItem
from deepin_utils.ipc import is_dbus_name_exists
from deepin_utils.file import get_parent_dir

DSC_SERVICE_NAME = "com.linuxdeepin.softwarecenter"
DSC_SERVICE_PATH = "/com/linuxdeepin/softwarecenter"

DSC_FRONTEND_NAME = "com.linuxdeepin.softwarecenter_frontend"
DSC_FRONTEND_PATH = "/com/linuxdeepin/softwarecenter_frontend"

DSC_UPDATE_MANAGER_NAME = 'com.linuxdeepin.softwarecenter_update_manager'
DSC_UPDATE_MANAGER_PATH = '/com/linuxdeepin/softwarecenter_update_manager'

def handle_dbus_reply(obj=None):
    print "Dbus Reply OK: %s", obj
    
def handle_dbus_error(obj, error=None):
    print "Dbus Reply Error: %s", obj
    print "ERROR MESSAGE: %s", error

def create_align(init, padding=None):
    align = gtk.Alignment(*init)
    if padding:
        align.set_padding(*padding)
    return align

def get_common_image(path):
    return os.path.join(get_parent_dir(__file__, 2), 'images', path)

def get_common_image_pixbuf(path):
    real_path = get_common_image(path)
    return gtk.gdk.pixbuf_new_from_file(real_path)

class UpdateManager(dbus.service.Object):
    def __init__(self, session_bus):
        dbus.service.Object.__init__(self, session_bus, DSC_UPDATE_MANAGER_PATH)

        self.in_update_list = False
        self.in_upgrade_packages = False
        self.upgrade_pkg_infos = []

        self.application = Application()
        self.application.set_default_size(400, 250)
        self.application.add_titlebar(
                button_mask=['min', 'close'],
                app_name='Software Update Manager',
                )

        self.application.window.set_title("Software Update Manager")
        self.application.set_icon(get_common_image('update.png'))


        # Init page box.
        self.page_box = gtk.VBox()
        
        # Init page align.
        self.page_align = gtk.Alignment()
        self.page_align.set(0.5, 0.5, 1, 1)
        self.page_align.set_padding(0, 0, 2, 2)
        
        self.page_align.add(self.page_box)
        self.application.main_box.pack_start(self.page_align, True, True)
        
        # Init status bar.
        self.statusbar = Statusbar(28)
        status_box = gtk.HBox()

        self.statusbar.status_box.pack_start(status_box, True, True)
        self.application.main_box.pack_start(self.statusbar, False, False)

        self.background = BackgroundBox()
        self.background.draw_mask = self.draw_mask
        self.page_box.pack_start(self.background)

        self.upgrade_button = Button('更新软件')
        self.upgrade_button.set_sensitive(False)

        button_box = gtk.HBox()
        button_box.pack_start(self.upgrade_button, False, False)

        button_box_align = gtk.Alignment(0.5, 0.5, 0, 0)
        button_box_align.set_padding(3, 8, 4, 4)
        button_box_align.add(button_box)

        self.statusbar.status_item_box.pack_start(button_box_align)

        self.update_info_label = Label("初始化...")
        self.update_info_label_align = create_align((0.5, 0.5, 0, 0))
        self.update_info_label_align.add(self.update_info_label)
        
        self.upgrade_button.connect('clicked', self.upgrade_packages)


    def draw_mask(self, cr, x, y, w, h):
        sidebar_color = ui_theme.get_color("menu_select_font").get_color()
        draw_vlinear(cr, x, y, w, h,
                     [(0, (sidebar_color, 0.9)),
                      (1, (sidebar_color, 0.9)),]
                     )

    def start_dsc_backend(self):
        self.system_bus = dbus.SystemBus()
        bus_object = self.system_bus.get_object(DSC_SERVICE_NAME, DSC_SERVICE_PATH)
        self.bus_interface = dbus.Interface(bus_object, DSC_SERVICE_NAME)
        self.system_bus.add_signal_receiver(
                self.backend_signal_receiver, 
                signal_name="update_signal", 
                dbus_interface=DSC_SERVICE_NAME, 
                path=DSC_SERVICE_PATH)

    def backend_signal_receiver(self, messages):
        for message in messages:
            (signal_type, action_content) = message
            
            if signal_type == "update-list-update":
                self.in_update_list = True
                message_str = "正在检查更新，请稍等...(%s%%)" % int(float(action_content[0]))
                self.update_info_label.set_text(message_str)
                self.upgrade_button.set_sensitive(False)
            elif signal_type == 'update-list-finish':
                message_str = "正在检查更新，请稍等..."
                self.update_info_label.set_text(message_str)
                self.in_update_list = False

                self.bus_interface.request_upgrade_pkgs(
                        reply_handler=self.render_upgrade_info, 
                        error_handler=lambda e:handle_dbus_error("request_upgrade_pkgs", e))
            elif signal_type == 'update-list-failed':
                message_str = '检查更新失败！'
                self.update_info_label.set_text(message_str)

            elif signal_type == 'upgrade-commit-update':
                pkg_names, action_type, percent, status = action_content
                message_str = "[%s%%]%s" % (percent, status)
                self.update_info_label.set_text(message_str)
                self.upgrade_button.set_sensitive(False)
                self.in_upgrade_packages = True

            elif signal_type == 'upgrade-commit-finish':
                self.in_upgrade_packages = False
                message_str = '软件更新完成！'
                self.update_info_label.set_text(message_str)

    def upgrade_packages(self, widget):
        if self.in_update_list:
            print 'Check update, please wait...'
        elif self.in_upgrade_packages:
            print 'Upgrade packages, please wait...'
        else:
            self.upgrade_button.set_sensitive(False)
            self.in_upgrade_packages = True
            all_upgrade_pkgs = []
            for info in self.upgrade_pkg_infos:
                all_upgrade_pkgs.append(str(eval(info)[0]))
            self.bus_interface.upgrade_pkgs_with_new_policy(
                    all_upgrade_pkgs,
                    reply_handler=lambda :handle_dbus_reply("upgrade_pkgs_with_new_policy"), 
                    error_handler=lambda e:handle_dbus_error("upgrade_pkgs_with_new_policy", e),
                    )

    def render_upgrade_info(self, pkg_infos):
        self.upgrade_pkg_infos = pkg_infos
        if len(pkg_infos) > 0:
            msg_str = '您的系统有%s个更新！' % (len(pkg_infos),)
            self.upgrade_button.set_sensitive(True)
        else:
            msg_str = '您的系统已经最新状态了～'
            self.upgrade_button.set_sensitive(False)

        self.update_info_label.set_text(msg_str)
        self.application.window.show_all()

    def run(self):
        self.start_dsc_backend()
        container_remove_all(self.background)
        self.background.pack_start(self.update_info_label_align)

        gtk.timeout_add(1000, lambda:self.bus_interface.start_update_list(
                reply_handler=lambda :handle_dbus_reply("start_update_list"),
                error_handler=lambda e:handle_dbus_error("start_update_list", e)))

        self.application.run()
        self.bus_interface.request_quit(
                reply_handler=lambda :handle_dbus_reply("request_quit"), 
                error_handler=lambda e:handle_dbus_error("request_quit", e))

    def quit(self):
        gtk.main_quit()

    @dbus.service.method(DSC_UPDATE_MANAGER_NAME, in_signature="", out_signature="")    
    def hello(self):
        self.application.window.present()

class PackageItem(TreeItem):
    def __init__(self):
        pass

if __name__ == '__main__':
    arguments = sys.argv[1::]

    DBusGMainLoop(set_as_default=True)
    session_bus = dbus.SessionBus()
    
    if is_dbus_name_exists(DSC_UPDATE_MANAGER_NAME, True):
        print "Update Manager is running"
        bus_object = session_bus.get_object(DSC_UPDATE_MANAGER_NAME,
                                            DSC_UPDATE_MANAGER_PATH)
        bus_interface = dbus.Interface(bus_object, DSC_UPDATE_MANAGER_NAME)
        bus_interface.hello()
    else:
        bus = dbus.service.BusName(DSC_UPDATE_MANAGER_NAME, session_bus)
        try:
            UpdateManager(session_bus).run()
        except KeyboardInterrupt:
            pass
