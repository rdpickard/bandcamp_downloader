import headless_bandcamp_interface

import time
import threading
import os
import logging
import sys

import dearpygui.dearpygui as dpg

import transitions

keep_fetching_albums = True

configuration = {
    "logging_dir": "/Users/pickard/projects/bandcamp_downloader/local/logs/",
    "logging_level": logging.DEBUG,
    "bandcamp_interface_config": {
        "chrome_application_path": "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "browser_scraped_pages_dir": "/Users/pickard/projects/bandcamp_downloader/local/logs/scraped_page",
        "downloads_dir": "/Users/pickard/projects/bandcamp_downloader/local/downloads2",
        "headless": False
    }
}

logger = logging.getLogger('BandCamp Downloader')
logger.setLevel(configuration["logging_level"])
file_logging_handler = logging.FileHandler(os.path.join(configuration["logging_dir"],
                                                        "BandCampDownloader.log"))
file_logging_handler_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_logging_handler.setFormatter(file_logging_handler_formatter)
logger.addHandler(file_logging_handler)
logger.addHandler(logging.StreamHandler(sys.stdout))

bci = headless_bandcamp_interface.BandcampInterface(configuration, logger)


class BandcampDownloaderAppStateMachine(object):
    states = ["logged_out", "logging_in", "updating_albums_list", "downloading_album", "idle"]

    def __init__(self):
        self.machine = transitions.Machine(model=self,
                                           states=BandcampDownloaderAppStateMachine.states,
                                           initial='logged_out')

        self.machine.add_transition(trigger='Go', source='logged_out', dest='logging_in')

        self.machine.add_transition(trigger='_log_in',
                                    source='logging_in',
                                    dest='idle')

        self.machine.add_transition(trigger='Get albums List',
                                    source='idle',
                                    dest='updating_albums_list',
                                    conditions=['logged_in'])

        self.machine.add_transition(trigger='Stop getting albums list',
                                    source='updating_albums_list',
                                    dest='idle',
                                    conditions=['logged_in'])

        self.machine.add_transition(trigger='_finished_updating_albums',
                                    source='updating_albums_list',
                                    dest='idle',
                                    conditions=['logged_in'])

        self.machine.add_transition(trigger='_download_album',
                                    source='idle',
                                    dest='downloading_album',
                                    conditions=['logged_in'])

        self.machine.add_transition(trigger='_finished_downloading_album',
                                    source='downloading_album',
                                    dest='idle',
                                    conditions=['logged_in'])


def rainbow_next(rbg_tuple, step=25):
    new_rgb_list = list(rbg_tuple)

    if (new_rgb_list[0] + step) <= 255:
        new_rgb_list[0] = new_rgb_list[0] + step
    elif (new_rgb_list[1] + step) <= 255:
        new_rgb_list[1] = new_rgb_list[1] + step
    elif (new_rgb_list[2] + step) <= 255:
        new_rgb_list[2] = new_rgb_list[2] + step
    else:
        new_rgb_list = [0, 0, 0]

    return tuple(new_rgb_list)


def callback_stop_everything():
    global keep_fetching_albums

    print("callback_stop_everything called")
    keep_fetching_albums = False


def callback_add_albums():
    dpg.set_item_label("action_button", "Stop fetching albums")
    dpg.configure_item("action_button", callback=callback_stop_everything)

    x = threading.Thread(target=add_albums)

    bci.login_to_bandcamp(dpg.get_value("input_username"),
                          dpg.get_value("input_password"))

    x.start()


def hover_handler(sender, data, user_data):
    print(f"HOVER {sender}")

    dpg.highlight_table_row("current_directory_files_list", 2, [0, 255, 0, 100])


def callback_file_selected(sender, data, user_data):
    dpg.set_value("pwd", user_data)
    tag = f"FILE_OPTION_{user_data}"

    dpg.get_item_parent(tag)

    #dpg.highlight_table_row("current_directory_files_list", i, [0, 255, 0, 100])

    #dpg.add_theme_color(sender, (0, 255, 0))


def callback_update_directory_file_list(sender, data, user_data):

    print(f"callback_update_directory_file_list called {user_data}")

    if user_data is None or user_data == "":
        path_to_list = "/"
    else:
        path_to_list = user_data

    file_names_list = sorted(os.listdir(path_to_list))

    # clean up
    for row in dpg.get_item_children("current_directory_files_list", 1):
        dpg.delete_item(row)

    with dpg.table_row(parent="current_directory_files_list"):
        dpg.add_button(label="[..]",
                           callback=callback_update_directory_file_list,
                           user_data=os.sep.join(path_to_list.split(os.sep)[:-1]))

    dpg.set_value("pwd", path_to_list)

    for file_name in file_names_list:

        with dpg.table_row(parent="current_directory_files_list") as tr:

            full_path_of_file = (os.path.join(path_to_list, file_name))
            tag = f"FILE_OPTION_{full_path_of_file}"

            if os.path.isdir(full_path_of_file):
                dpg.add_button(label=f"[{file_name}]",
                               tag=tag,
                               callback=callback_update_directory_file_list,
                               user_data=full_path_of_file)
                dpg.add_text("directory")
                dpg.add_text("-")
            else:
                dpg.add_button(label=file_name,
                               tag=tag,
                               callback=callback_file_selected,
                               user_data=full_path_of_file)

                dpg.add_text("file")
                dpg.add_text(str(os.access(full_path_of_file, os.X_OK)))

            #dpg.bind_item_handler_registry(tag, "rowhover")


def add_albums():

    purchased_albums = bci.get_albums_in_library()

    for purchased_album in purchased_albums:
        if keep_fetching_albums:
            with dpg.table_row(parent="album_list"):
                with dpg.group(horizontal=True):
                    dpg.add_checkbox()
                    dpg.add_text(purchased_album["name"])
                dpg.add_text(purchased_album["artist"])

def add_albums_OLD():
    global keep_fetching_albums

    status_text_color = (255, 255, 255)

    for i in range(0, 146):
        if keep_fetching_albums:
            with dpg.table_row(parent="album_list"):
                with dpg.group(horizontal=True):
                    dpg.add_checkbox()
                    dpg.add_text(f"Row{i} Column 1")
                dpg.add_text(f"Row{i} Column 2")
                #dpg.configure_item("status_label", color=status_text_color)
                status_text_color = rainbow_next(status_text_color)
                dpg.set_value("status_label", f"adding row {i}")
                time.sleep(.2)


dpg.create_context()
dpg.create_viewport(title="Bandcamp Purchases Downloader", width=600, height=900)
dpg.setup_dearpygui()
dpg.show_viewport()

with dpg.window(label="MainWindow") as primary_window:

    dpg.add_text("Bandcamp Downloader", tag="header")
    dpg.add_separator()
    dpg.add_text()

    dpg.add_input_text(label=" Bandcamp username/email", tag="input_username")
    dpg.add_input_text(label=" Account password", password=True, tag="input_password")

    dpg.add_separator()

    dpg.add_text()
    dpg.add_input_text()
    dpg.add_same_line()
    dpg.add_button(label="Specify Chrome location", tag="specify_chrome_location_button")

    # check out simple module for details
    with dpg.popup("specify_chrome_location_button", mousebutton=dpg.mvMouseButton_Left, modal=True, tag="modal_id"):
        dpg.add_text("Specify path to Chrome app")
        dpg.add_separator()

        dpg.add_text("/", tag="pwd")

        dpg.add_button(label="User Selected",
                       callback=lambda: dpg.configure_item("modal_id", show=False))
        dpg.add_same_line()
        dpg.add_button(label="Close",
                       callback=lambda: dpg.configure_item("modal_id", show=False))

        dpg.configure_item("modal_id", min_size=[500, 800])

        with dpg.table(header_row=True, resizable=True,
                       tag="current_directory_files_list",
                       row_background=True):
            dpg.add_table_column(label="Filename")
            dpg.add_table_column(label="Type")
            dpg.add_table_column(label="Executable")

            callback_update_directory_file_list(None, None, "/")

    dpg.add_separator()
    dpg.add_text()
    with dpg.group(horizontal=True):
        sl = dpg.add_input_text(label="", tag="status_label")
        ga = dpg.add_button(label="Get Albums", callback=callback_add_albums, tag="action_button")

    dpg.disable_item('status_label')

    dpg.add_separator()
    dpg.add_text()

    with dpg.group(horizontal=True):
        ga = dpg.add_button(label="Download selected Albums", callback=callback_add_albums, tag="dl_action_button")
        dpg.add_text("|")
        sas = dpg.add_button(label="Select All", callback=callback_add_albums, tag="selectall_action_button")
        sas = dpg.add_button(label="De-select All", callback=callback_add_albums, tag="deselectall_action_button")

    with dpg.table(header_row=True,
                   resizable=True,
                   row_background=True,
                   tag="album_list"):
        # use add_table_column to add columns to the table,
        # table columns use child slot 0
        dpg.add_table_column(label="Album/Collection name")
        dpg.add_table_column(label="Artist")
        dpg.add_table_column(label=" Download Status")

    # theming
    with dpg.theme() as item_theme:
        with dpg.theme_component(dpg.mvInputText, enabled_state=False):
            dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (37, 37, 38), category=dpg.mvThemeCat_Core)

    dpg.bind_item_theme("status_label", item_theme)
    #dpg.bind_item_theme("dl_status_label", item_theme)


    with dpg.theme() as item_theme:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_Text, (26, 160, 195), category=dpg.mvThemeCat_Core)
    dpg.bind_item_theme("header", item_theme)


dpg.set_primary_window(primary_window, True)

dpg.start_dearpygui()
dpg.destroy_context()
