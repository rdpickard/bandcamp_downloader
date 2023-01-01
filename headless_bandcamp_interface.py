import os
import base64
import logging
import time
import sys
import urllib

import jsonschema
import requests
import arrow
from bs4 import BeautifulSoup

from selenium import webdriver
import selenium.common.exceptions
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

bandcamp_interface_config_schema = {
    "$id": "https://example.com/person.schema.json",
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Bandcamp Interface config",
    "type": "object",
    "properties": {
        "bandcamp_interface_config": {
            "type": "object",
            "properties": {
                "chrome_application_path": {"type": "string"},
                "browser_scraped_pages_dir": {"type": "string"},
                "downloads_dir": {"types": ["string", "null"]},
                "headless": {"type": "boolean"}
            },
            "required": ["browser_scraped_pages_dir", "chrome_application_path"]
        }
    },
    "required": ["bandcamp_interface_config"]
}


def save_browser_current_page(url_of_content,
                              note,
                              page_content,
                              file_prefix,
                              save_dir):
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    if file_prefix is None:
        file_prefix = ""
    else:
        file_prefix = file_prefix + "-"
    saved_page_filename = "{}{}{}{}_{}.html".format(save_dir,
                                                    os.path.sep,
                                                    file_prefix,
                                                    "".join(base64.b64encode(url_of_content.encode('ascii')).decode(
                                                        "utf-8")[0:50]),
                                                    arrow.utcnow().format('YYYY-MM-DD_HH:mm:ss_ZZ'))

    with open(saved_page_filename, "a+") as f:
        f.write(f"<!--SAVED CONTENT OF \"{url_of_content}\" -->\n\n")
        f.write(f"<!--NOTE \"{note}\" -->\n\n")

        f.write(page_content)

    return saved_page_filename


class BandcampInterfaceException(Exception):
    pass


class BandcampInterfaceScrapeException(BandcampInterfaceException):
    scraped_url = None
    page_contents = None
    page_element = None
    saved_file_name = None

    def __init__(self, message, scraped_url, page_contents, save_dir, page_element=None):
        super().__init__(message)
        self.scraped_url = scraped_url
        self.page_contents = page_contents
        self.page_element = page_element

        self.saved_file_name = save_browser_current_page(scraped_url, message, page_contents, None, save_dir)


class BandcampInterface:

    browser = None
    logger = None
    browser_scraped_pages_dir = None
    browser_is_headless = False

    def _save_current_page(self, note, file_prefix):
        save_browser_current_page(self.browser.current_url,
                                  note,
                                  self.browser.page_source,
                                  file_prefix,
                                  self.browser_scraped_pages_dir
                                  )

    def _raise_scrape_exception(self, message):
        raise BandcampInterfaceScrapeException(message,
                                               self.browser.current_url,
                                               self.browser.page_source,
                                               self.browser_scraped_pages_dir)

    def __init__(self, logger, browser_scraped_pages_dir):
        logging.getLogger('WDM').setLevel(logging.NOTSET)
        os.environ['WDM_LOG'] = "false"

        self.logger = logger
        self.browser_scraped_pages_dir = browser_scraped_pages_dir

        if not os.path.exists(browser_scraped_pages_dir):
            os.makedirs(browser_scraped_pages_dir)

    def _wait_for_element(self, element_by, element_value, timeout_seconds=10):
        self.logger.debug(f"Waiting for '{element_by}' '{element_value}'")
        element = None
        start_time = arrow.utcnow()
        while (arrow.utcnow() - start_time).seconds < timeout_seconds:
            try:
                element = self.browser.find_element(by=element_by, value=element_value)
                if element is None:
                    time.sleep(.5)
                else:
                    self.logger.debug(f"Found for '{element_by}' '{element_value}'")
                    break
            except Exception:
                time.sleep(.5)

        return element

    def configure_a_browser(self,
                            path_to_chrome_application,
                            headless,
                            chrome_downloads_dir=None):

        if self.browser is not None:
            self.logger.info("Before creating a new browser, closing exiting browser")
            self.browser.quit()
            self.browser = None

        self.browser_is_headless = headless

        chrome_options = webdriver.ChromeOptions()
        if self.browser_is_headless:
            chrome_options.add_argument("--headless")
        if chrome_downloads_dir is not None:
            self.logger.info(f"Setting Chrome downloads directory to '{chrome_downloads_dir}'")

            if not os.path.exists(chrome_downloads_dir):
                os.makedirs(chrome_downloads_dir)

            chrome_options.add_experimental_option("prefs", {"download.default_directory": chrome_downloads_dir})

        self.logger.info(f"Setting up headless browser '{path_to_chrome_application}'")
        chrome_options.binary_location = path_to_chrome_application

        self.browser = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    def login_to_bandcamp(self, bandcamp_account_username, bandcamp_account_password):

        self.browser.get("https://bandcamp.com/login")

        self.browser.find_element(by=By.ID, value="username-field").send_keys(bandcamp_account_username)
        self.browser.find_element(by=By.ID, value="password-field").send_keys(bandcamp_account_password)
        self._save_current_page("", "before-login")

        self.browser.find_element(by=By.XPATH, value="//button[@type='submit']").click()

        self.logger.debug("Clicked login. Waiting for user page to load")
        time.sleep(.5)

        if self.browser.current_url.endswith("login"):

            try:
                itsacaptcha = self.browser.find_element(by=By.XPATH, value="//div[text()='Please wait…' and @data-bind='if: submitting']")
            except selenium.common.exceptions.NoSuchElementException:
                itsacaptcha = None

            if itsacaptcha is not None:
                if self.browser_is_headless is False:
                    for _ in range(30):
                        if self.browser.current_url.endswith("login"):
                            time.sleep(1)
                        else:
                            break
                if self.browser.current_url.endswith("login"):
                    raise BandcampInterfaceException("Login demands CAPTCHA. Try setting 'headless' to false and rerunning to solve CAPTCHA.")
            else:
                self._raise_scrape_exception("Can't login. Login process redirected to login page")

        self._save_current_page("", "after-login")

        # TODO Need to verify login

    def get_albums_in_library(self):

        # TODO Need to verfiy logged in

        # TODO Need to goto libray page, browser might be on a different URL

        show_more_button_element = self._wait_for_element(By.XPATH, "//button[@class='show-more']")

        if show_more_button_element is not None:
            show_more_button_element.click()
            time.sleep(1)

        previous_container_height = 0
        container_height = self.browser.execute_script("return propOpenWrapper.scrollHeight")

        while container_height > previous_container_height:
            self.logger.debug(f"Scrolling container previous height '{previous_container_height}' current height '{container_height}'")

            previous_container_height = container_height
            self.browser.execute_script("window.scrollTo(0, propOpenWrapper.scrollHeight);")
            time.sleep(.5)

            container_height = self.browser.execute_script("return propOpenWrapper.scrollHeight")

        self._save_current_page("","all-albums")
        album_elements = self.browser.find_elements(by=By.CLASS_NAME, value="collection-item-container")
        self.logger.debug(f"Album elements count {len(album_elements)}")
        albums = list()
        for album_element in album_elements:
            c_album = dict()
            c_album["name"] = album_element.find_element(by=By.CLASS_NAME, value="collection-item-title").text
            c_album["artist"] = album_element.find_element(by=By.CLASS_NAME, value="collection-item-artist").text.replace("by","").strip()
            c_album["download_page_url"] = album_element.find_element(by=By.CLASS_NAME, value="redownload-item").find_element(by=By.TAG_NAME, value="a").get_attribute("href")
            c_album["sitem_id"] = urllib.parse.parse_qs(urllib.parse.urlparse(c_album["download_page_url"]).query).get("sitem_id", [''])[0]

            albums.append(c_album)

        return albums

    def download_album(self, album_download_page_url, preferred_format=None):
        
        self.browser.get(album_download_page_url)

        title_element = self._wait_for_element(By.CLASS_NAME, "title")
        album_title = title_element.text
        album_artist = self.browser.find_element(by=By.CLASS_NAME, value="artist").text.replace("by", "").strip()

        self.logger.info(f"Downloading {album_title} {album_artist}")

        file_download_url = None

        while True:
            album_download_element = self.browser.find_element(by=By.XPATH, value="//a[text()='Download']")
            try:
                file_download_url = album_download_element.get_attribute("href")
                if file_download_url is None or file_download_url == "":
                    print("Waiting for download to be ready")
                    time.sleep(1)
                    continue
                else:
                    break
            except Exception:
                print("caught exception asking for href. assuming it isn't there?")
                time.sleep(1)

        if file_download_url is not None:
            # self.browser.get(file_download_url)
            pass
        else:
            print("DOWNLOAD LINK IS NONE")
        time.sleep(5)
