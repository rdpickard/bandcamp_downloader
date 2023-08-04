import urllib
import logging
import os
import time
import base64

import arrow

from selenium import webdriver
import selenium.common.exceptions
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

def initialize_and_get_browser(chrome_application_path, download_dir, logger):
    """
    Create an instance of a Chrome browser to control

    :param chrome_application_path:
    :param download_dir:
    :param logger:
    :return:
    """
    logging.getLogger('WDM').setLevel(logging.NOTSET)
    os.environ['WDM_LOG'] = "false"

    d = DesiredCapabilities.CHROME
    d['loggingPrefs'] = {'browser': 'ALL'}

    logger.info(f"Setting up headless browser  {chrome_application_path}")

    chrome_options = webdriver.ChromeOptions()

    chrome_options.add_experimental_option("prefs",
                                           {"download.default_directory": download_dir})

    chrome_application_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    chrome_options.binary_location = chrome_application_path
    the_headless_browser = webdriver.Chrome(service=Service(ChromeDriverManager().install()),
                                            options=chrome_options)

    return the_headless_browser


def wait_for_element(browser, element_by, element_value, timeout_seconds, logger):
    """
    Wait for an element to exist in the DOM

    :param browser:
    :param element_by:
    :param element_value:
    :param timeout_seconds:
    :param logger:
    :return:
    """
    element = None
    start_time = arrow.utcnow()
    while (arrow.utcnow() - start_time).seconds < timeout_seconds:
        try:
            element = browser.find_element(by=element_by, value=element_value)
            if element is None:
                time.sleep(.5)
            else:
                break
        except selenium.common.exceptions.NoSuchElementException as nsee:
            logger.debug(f"could not yet find element {element_value}, waiting...")
            time.sleep(.5)
    if element is None:
        logger.debug(f"waiting on element {element_value} that was never found")
    return element


def inject_js_into_DOM(browser_session, js_content, logger):
    """
    Add Javascript to the current page in the browser session. Allows for functionality to be injected into a page

    :param browser_session:
    :param js_content:
    :param logger:
    :return:
    """

    js_content = urllib.parse.quote(js_content)
    injection_js = """
    injection_target_element = document.querySelector('head');

    var injected_element = document.createElement('script');
    injected_element.type = "text/javascript";
    injected_element.textContent = unescape(\"""" + js_content + """\");
    injection_target_element.appendChild(injected_element);  
    """
    browser_session.execute_script(injection_js)

def inject_html_into_DOM(browser_session, html_content, logger):
    """
    Append a new HTML element to the DOM of the current page at the end of the body element

    :param browser_session:
    :param html_content:
    :param logger:
    :return:
    """

    html_content = urllib.parse.quote(html_content)

    injection_js = """
        injection_target_element = document.querySelector('body');
        injection_target_element.innerHTML += unescape(\"""" + html_content + """\");
        """
    browser_session.execute_script(injection_js)

def inject_css_into_DOM(browser_session, css_content, logger):
    """
    Add CSS styling to the current DOM in the browser session

    :param browser_session:
    :param css_content:
    :param logger:
    :return:
    """
    css_content = urllib.parse.quote(css_content)

    injection_js = """
    injection_target_element = document.querySelector('head');

    var injected_element = document.createElement('style');
    injected_element.textContent = unescape(\"""" + css_content + """\");

    injection_target_element.appendChild(injected_element);  
    """
    browser_session.execute_script(injection_js)

def inject_css_from_file_into_DOM(browser_session, css_content_file, logger):
    """

    :param browser_session:
    :param css_content_file:
    :param logger:
    :return:
    """
    with open(css_content_file) as css_file:
        css_file_content = css_file.read()
    inject_css_into_DOM(browser_session, css_file_content, logger)


def inject_html_from_file_into_DOM(browser_session, html_file_path, logger):
    """

    :param browser_session:
    :param html_file_path:
    :param logger:
    :return:
    """
    with open(html_file_path) as html_file:
        html_file_content = html_file.read()
    inject_html_into_DOM(browser_session, html_file_content, logger)


def inject_js_from_file_into_DOM(browser_session, js_file_path, logger):
    """

    :param browser_session:
    :param js_file_path:
    :param logger:
    :return:
    """

    with open(js_file_path) as js_file:
        js_file_content = js_file.read()

    inject_js_into_DOM(browser_session, js_file_content, logger)


def save_browser_current_page(browser,
                              save_dir,
                              prefix=None,
                              notes=None):
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    if prefix is None:
        prefix = ""
    else:
        prefix = prefix + "-"

    url_of_content = browser.current_url
    content = browser.page_source

    allowed_nonalpha_filename_characters = (' ', '_', '-', ":")

    encoded_url = "".join(base64.b64encode(url_of_content.encode('ascii')).decode("utf-8")[0:50])
    saved_page_filename = f"{prefix}{encoded_url}_{arrow.utcnow().format('YYYY-MM-DD_HH:mm:ss_ZZ')}"
    saved_page_filename = "".join(c for c in saved_page_filename if c.isalnum() or c in allowed_nonalpha_filename_characters).rstrip()
    saved_page_filename = saved_page_filename+".html"

    save_page_path = os.path.join(save_dir, saved_page_filename)

    with open(save_page_path, "a+") as f:
        f.write(f"<!--SAVED CONTENT OF \"{url_of_content}\" -->\n\n")
        if notes is not None:
            f.write(f"<!--NOTES \"{notes}\" -->\n\n")

        f.write(content)

    return save_page_path
