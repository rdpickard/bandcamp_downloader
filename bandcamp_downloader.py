import headless_bandcamp_interface

import json
import tempfile
import time
import threading
import os
import logging
import sys
import re

import dearpygui.dearpygui as dpg


class GUIEventLoggingStreamHandler(logging.StreamHandler):

    def __init__(self):
        super().__init__()

    def emit(self, record):

        msg = record.getMessage()

        if msg.startswith("BANDCAMP_DOWNLOADER_EVENT"):
            dpg.set_value("label_app_status", msg.replace("BANDCAMP_DOWNLOADER_EVENT", "").strip())


# Try to load a configuration file
user_home_dir_path = os.path.expanduser("~")
config_dir_path = os.path.join(user_home_dir_path, ".config")
json_config_file_path = os.path.join(config_dir_path, "bandcamp_downloader.json")
if not os.path.exists(config_dir_path):
    os.makedirs(config_dir_path)

print(f"config file is {json_config_file_path}")

if not os.path.exists(json_config_file_path):
    with open(json_config_file_path, 'w+') as basic_config_file:
        json.dump({
                    "logging_dir": tempfile.gettempdir(),
                    "logging_level": logging.INFO,
                    "username": None,
                    "bandcamp_interface_config": {
                        "chrome_application_path": None,
                        "browser_scraped_pages_dir": tempfile.gettempdir(),
                        "downloads_dir": None,
                        "headless": False,
                        "username": None
                    }
                },
                basic_config_file)

with open(json_config_file_path, 'r') as config_file:
    bandcamp_downloader_config = json.load(config_file)

# Set up logger
logger = logging.getLogger('BandCamp Downloader')
logger.setLevel(bandcamp_downloader_config["logging_level"])
file_logging_handler = logging.FileHandler(os.path.join(bandcamp_downloader_config["logging_dir"],
                                                        "BandCampDownloader.log"))
file_logging_handler_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_logging_handler.setFormatter(file_logging_handler_formatter)
logger.addHandler(file_logging_handler)
logger.addHandler(logging.StreamHandler(sys.stdout))

event_logging_handler = GUIEventLoggingStreamHandler()
logger.addHandler(event_logging_handler)

# The bandcamp headless interface
bci = None

current_albums_list = None


# Call back functions connected to GUI elements
def callback_update_directory_file_list(sender, data, user_data):

    logger.debug(f"callback_update_directory_file_list called {user_data}")

    if user_data is None or user_data == "":
        path_to_list = "/"
    else:
        path_to_list = user_data

    file_names_list = sorted(os.listdir(path_to_list))

    # clean up
    for row in dpg.get_item_children("table_current_directory_files_list", 1):
        dpg.delete_item(row)

    with dpg.table_row(parent="table_current_directory_files_list"):
        dpg.add_button(label="[..]",
                       callback=callback_update_directory_file_list,
                       user_data=os.sep.join(path_to_list.split(os.sep)[:-1]))

    dpg.set_value("label_chrome_location_pwd", path_to_list)

    for file_name in file_names_list:

        with dpg.table_row(parent="table_current_directory_files_list") as tr:

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


def callback_file_selected(sender, data, user_data):
    dpg.set_value("label_chrome_location_pwd", user_data)


def add_albums_to_album_list():

    global bci
    global current_albums_list

    logger.info("BANDCAMP_DOWNLOADER_EVENT Getting list of purchased albums")

    current_albums_list = bci.get_albums_in_library()

    logger.info("BANDCAMP_DOWNLOADER_EVENT Got list of purchased albums")

    for purchased_album in current_albums_list:

        with dpg.table_row(parent="table_album_list"):
            with dpg.group(horizontal=True):
                dpg.add_checkbox(tag=f"input_checkbox_download_album_{purchased_album['sitem_id']}")
                dpg.add_text(purchased_album["name"])
            dpg.add_text(purchased_album["artist"])


def callback_add_albums():

    global bci

    x = threading.Thread(target=add_albums_to_album_list)

    bandcamp_downloader_config["bandcamp_interface_config"]["chrome_application_path"] = dpg.get_value("input_chrome_location")

    logger.info("BANDCAMP_DOWNLOADER_EVENT Setting up browser")

    bci.configure_a_browser(dpg.get_value("input_chrome_location"),
                            dpg.get_value("input_checkbox_headless"))

    logger.info("BANDCAMP_DOWNLOADER_EVENT Logging into Bandcamp")

    bci.login_to_bandcamp(dpg.get_value("input_username"),
                          dpg.get_value("input_password"))

    logger.info("BANDCAMP_DOWNLOADER_EVENT Logged into Bandcamp")

    bandcamp_downloader_config["username"] = dpg.get_value("input_username")

    with open(json_config_file_path, 'w+') as config_file:
        json.dump(bandcamp_downloader_config, config_file)

    x.start()


def callback_select_all_albums():

    for album_download_cb_alias in filter(lambda an: an.startswith("input_checkbox_download_album"), dpg.get_aliases()):
        dpg.set_value(album_download_cb_alias, True)


def callback_de_select_all_albums():
    for album_download_cb_alias in filter(lambda an: an.startswith("input_checkbox_download_album"), dpg.get_aliases()):
        dpg.set_value(album_download_cb_alias, False)


def callback_set_chrome_location():

    dpg.set_value("input_chrome_location",
                  dpg.get_value("label_chrome_location_pwd"))

    dpg.configure_item("popup_window_file_picker", show=False)


def callback_downloaded_selected_albums():

    global current_albums_list

    selected_sitem_ids = []

    for album_download_cb_alias in filter(lambda an: an.startswith("input_checkbox_download_album"), dpg.get_aliases()):
        if dpg.get_value(album_download_cb_alias):
            selected_sitem_ids.append(re.match(r"input_checkbox_download_album_(\d+)", album_download_cb_alias).groups()[0])

    albums_to_download = filter(lambda album: album["sitem_id"] in selected_sitem_ids, current_albums_list)

    for album_to_download in albums_to_download:
        print(f"Going to DL {album_to_download}")

bci = headless_bandcamp_interface.BandcampInterface(logger, tempfile.gettempdir())

# Set up main GUI elements
dpg.create_context()
dpg.create_viewport(title="Bandcamp Purchases Downloader", width=600, height=900)
dpg.setup_dearpygui()
dpg.show_viewport()

with dpg.window(label="MainWindow") as primary_window:

    dpg.add_text("Bandcamp Downloader", tag="header")
    dpg.add_text(tag="label_app_status")
    dpg.add_separator()
    dpg.add_text()

    dpg.add_input_text(label=" Bandcamp username/email", tag="input_username")
    dpg.add_input_text(label=" Account password", password=True, tag="input_password")

    dpg.add_separator()

    dpg.add_text()
    dpg.add_input_text(tag="input_chrome_location")
    dpg.add_same_line()

    dpg.add_button(label="Specify Chrome location", tag="button_specify_chrome_location")
    with dpg.group(horizontal=True):
        sl = dpg.add_input_text(label="", tag="label_headless")
        dpg.add_checkbox(label="Headless browser",
                         tag="input_checkbox_headless",
                         default_value=bandcamp_downloader_config["bandcamp_interface_config"]["headless"])
    dpg.disable_item('label_headless')

    dpg.add_separator()
    dpg.add_text()
    with dpg.group(horizontal=True):
        sl = dpg.add_input_text(label="", tag="label_get_albums_status")
        ga = dpg.add_button(label="Get Albums", callback=callback_add_albums, tag="button_get_albums")

    dpg.disable_item('label_get_albums_status')

    with dpg.child_window(tag="window_album_list_container", autosize_x=True, height=600):

        with dpg.table(header_row=True,
                       resizable=True,
                       row_background=True,
                       hideable=True,
                       tag="table_album_list"):

            dpg.add_table_column(label="Album/Collection name")
            dpg.add_table_column(label="Artist")
            dpg.add_table_column(label=" Download Status")
            # Hiding tables doesn't seem to work
            #dpg.add_table_column(label="hidden_DownloadLink", tag="table_row_hidden_DownloadLink")

    #dpg.configure_item("table_row_hidden_DownloadLink", show=False)

    dpg.add_separator()

    with dpg.group(horizontal=True):
        dpg.add_button(label="Download selected Albums",
                       callback=callback_downloaded_selected_albums, tag="button_downloaded_selected_albums")
        dpg.add_text("|")
        dpg.add_button(label="Select All",
                             callback=callback_select_all_albums, tag="button_select_all")
        dpg.add_button(label="De-select All",
                             callback=callback_de_select_all_albums, tag="button_de_select_all")
# Pop up and modal windows for GUI
#   File picker for Chrome location
with dpg.popup("button_specify_chrome_location",
               mousebutton=dpg.mvMouseButton_Left, modal=True,
               tag="popup_window_file_picker"):

    dpg.add_text("Specify path to Chrome app")
    dpg.add_separator()

    dpg.add_input_text(default_value="/", tag="label_chrome_location_pwd")

    dpg.add_button(label="User Selected",
                   callback=callback_set_chrome_location)
    dpg.add_same_line()
    dpg.add_button(label="Close",
                   callback=lambda: dpg.configure_item("popup_window_file_picker", show=False))

    dpg.configure_item("popup_window_file_picker", min_size=[500, 800])

    with dpg.table(header_row=True, resizable=True,
                   tag="table_current_directory_files_list",
                   row_background=True):
        dpg.add_table_column(label="Filename")
        dpg.add_table_column(label="Type")
        dpg.add_table_column(label="Executable")

        callback_update_directory_file_list(None, None, "/")

# Theming of GUI elements
with dpg.theme() as item_theme:
    with dpg.theme_component(dpg.mvInputText, enabled_state=False):
        dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (37, 37, 38), category=dpg.mvThemeCat_Core)

dpg.bind_item_theme("label_get_albums_status", item_theme)
dpg.bind_item_theme("label_headless", item_theme)


with dpg.theme() as item_theme:
    with dpg.theme_component(dpg.mvAll):
        dpg.add_theme_color(dpg.mvThemeCol_Text, (26, 160, 195), category=dpg.mvThemeCat_Core)
dpg.bind_item_theme("header", item_theme)


# Set GUI input elements to have values from config file
if bandcamp_downloader_config["username"] is not None:
    dpg.set_value("input_username", bandcamp_downloader_config["username"])

if bandcamp_downloader_config["bandcamp_interface_config"]["chrome_application_path"] is not None:
    dpg.set_value("input_chrome_location", bandcamp_downloader_config["bandcamp_interface_config"]["chrome_application_path"])

# Display the main window and start the event loop
dpg.set_primary_window(primary_window, True)

for a in filter(lambda an: an.startswith("FILE"), dpg.get_aliases()):
    print(a)

dpg.start_dearpygui()
dpg.destroy_context()
