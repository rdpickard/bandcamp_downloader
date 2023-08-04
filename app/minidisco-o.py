import os
import base64
import logging
import time
import sys
import pathlib
import urllib.parse
import shutil
import re

import requests
import arrow

import browser_control_utils

from selenium import webdriver
import selenium.common.exceptions
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

bandcamp_account_username = os.environ.get("BANDCAMP_ACCOUNT_USERNAME")
bandcamp_account_password = os.environ.get("BANDCAMP_ACCOUNT_PASSWORD")

download_dir = "/tmp/"

logger = logging.getLogger('MiniDisco BandCamp Downloader')
logger.setLevel(logging.DEBUG)

def close_browser_and_exit(browser):
    minidisco_browser.close()
    sys.exit()

def wait_for_input_value_or_quit(browser, element_by, element_value, timeout_seconds, logger):
    desired_element = browser_control_utils.wait_for_element(browser, element_by, element_value,
                                                             timeout_seconds, logger)

    if desired_element is None:
        logger.info(f"Timed out on waiting for {element_value}. Quitting")
        close_browser_and_exit(browser)

    return desired_element.get_attribute("value")


minidisco_browser = browser_control_utils.initialize_and_get_browser(chrome_path, download_dir, logger)

minidisco_browser.get("https://bandcamp.com/login")

#minidisco_browser.find_element(by=By.ID, value="username-field").send_keys(bandcamp_account_username)
#minidisco_browser.find_element(by=By.ID, value="password-field").send_keys(bandcamp_account_password)
#minidisco_browser.find_element(by=By.XPATH, value="//button[@type='submit']").click()
"""
# inject jquery and semantic web into the page
browser_control_utils.inject_js_from_file_into_DOM(minidisco_browser, "resources/jquery-3.7.0.min.js", logger)
browser_control_utils.inject_js_from_file_into_DOM(minidisco_browser, "resources/semantic.min.js", logger)
browser_control_utils.inject_css_from_file_into_DOM(minidisco_browser, "resources/semantic.min.css", logger)

# inject minidisco UI into the page
browser_control_utils.inject_html_from_file_into_DOM(minidisco_browser, "resources/minidisco_injected_html.html", logger)
browser_control_utils.inject_js_from_file_into_DOM(minidisco_browser, "resources/minidisco_injected_javascript.js", logger)

# init the minidisco UI in the page
minidisco_browser.execute_script(f"minidisco_ui_script_hook_init()")

if bandcamp_account_username is not None and bandcamp_account_username != "" and \
    bandcamp_account_password is not None and bandcamp_account_password != "":
        minidisco_browser.execute_script(f"minidisco_ui_script_hook_set_username_and_password('{bandcamp_account_username}', '{bandcamp_account_password}');")
        
minidisco_browser.execute_script("minidisco_ui_script_hook_loginpage_welcome_modal();")

flow_step_1_value = wait_for_input_value_or_quit(minidisco_browser,
                                                 By.XPATH, "//input[@id='minidisco_flow_step_1']",
                                                 30, logger)
if flow_step_1_value == "quit":
    close_browser_and_exit(minidisco_browser)
elif flow_step_1_value == "approved":
"""
logger.info("minidisco_flow_step_1 was approved, filling in the details")

minidisco_browser.find_element(by=By.ID, value="username-field").send_keys(bandcamp_account_username)
minidisco_browser.find_element(by=By.ID, value="password-field").send_keys(bandcamp_account_password)
minidisco_browser.find_element(by=By.XPATH, value="//button[@type='submit']").click()

wait_for_element(minidisco_browser, By.XPATH, "//button[@class='show-more']")
#minidisco_browser.execute_script('$( "<div>test</div>" ).dialog();')

#for entry in minidisco_browser.get_log('browser'):
#    print(entry)

input("Press Enter to quit...")

minidisco_browser.close()