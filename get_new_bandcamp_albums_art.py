import os
import base64
import logging
import time
import sys
import pathlib
import urllib.parse
import shutil


import requests
import arrow
from bs4 import BeautifulSoup

from selenium import webdriver
import selenium.common.exceptions
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

bandcamp_downloader_config = dict()
bandcamp_downloader_config["logging_files_dir"] = "local/logs/"
bandcamp_downloader_config["logging_level"] = logging.DEBUG
bandcamp_downloader_config["headless_browser_scraped_pages_dir"] = "local/saved_pages/"
bandcamp_downloader_config["downloads_dir"] = "/Users/pickard/projects/bandcamp_downloader/local/downloads/"

if not os.path.exists(bandcamp_downloader_config["logging_files_dir"]):
    os.makedirs(bandcamp_downloader_config["logging_files_dir"])
if not os.path.exists(bandcamp_downloader_config["headless_browser_scraped_pages_dir"]):
    os.makedirs(bandcamp_downloader_config["headless_browser_scraped_pages_dir"])
if not os.path.exists(bandcamp_downloader_config["downloads_dir"]):
    os.makedirs(bandcamp_downloader_config["downloads_dir"])


def save_browser_current_page(url_of_content,
                              content,
                              prefix=None,
                              save_dir=bandcamp_downloader_config["headless_browser_scraped_pages_dir"]):
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    if prefix is None:
        prefix = ""
    else:
        prefix = prefix + "-"
    saved_page_filename = "{}{}{}{}_{}.html".format(save_dir,
                                                    os.path.sep,
                                                    prefix,
                                                    "".join(base64.b64encode(url_of_content.encode('ascii')).decode(
                                                        "utf-8")[0:50]),
                                                    arrow.utcnow().format('YYYY-MM-DD_HH:mm:ss_ZZ'))

    with open(saved_page_filename, "a+") as f:
        f.write(f"<!--SAVED CONTENT OF \"{url_of_content}\" -->\n\n")
        f.write(content)

    return saved_page_filename


class HeadlessBrowserScrapeException(Exception):
    scraped_url = None
    page_contents = None
    page_element = None
    saved_file_name = None

    def __init__(self, message, scraped_url, page_contents, page_element=None):
        super().__init__(message)
        self.scraped_url = scraped_url
        self.page_contents = page_contents
        self.page_element = page_element

        self.saved_file_name = save_browser_current_page(scraped_url, page_contents)


def initialize_and_get_headless_browser(chrome_application_path, logger):
    logging.getLogger('WDM').setLevel(logging.NOTSET)
    os.environ['WDM_LOG'] = "false"

    # tui_terminal_console.log(f"Setting up headless browser  {chrome_application_path}")
    logger.info(f"Setting up headless browser  {chrome_application_path}")

    chrome_options = webdriver.ChromeOptions()
    # chrome_options.add_argument("--headless")
    chrome_options.add_experimental_option("prefs",
                                           {"download.default_directory": bandcamp_downloader_config["downloads_dir"]})
    chrome_options.binary_location = chrome_application_path

    headless_browser = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    return headless_browser


def wait_for_element(browser, element_by, element_value, timeout_seconds=10):
    element = None
    start_time = arrow.utcnow()
    while (arrow.utcnow() - start_time).seconds < timeout_seconds:
        try:
            element = browser.find_element(by=element_by, value=element_value)
            if element is None:
                time.sleep(.5)
        except Exception:
            time.sleep(.5)

    return element


logger = logging.getLogger('BandCamp Downloader')
logger.setLevel(bandcamp_downloader_config["logging_level"])
file_logging_handler = logging.FileHandler(os.path.join(bandcamp_downloader_config["logging_files_dir"],
                                                        "BandCampDownloader.log"))
file_logging_handler_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_logging_handler.setFormatter(file_logging_handler_formatter)
logger.addHandler(file_logging_handler)

chrome_application_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
# chrome_application_path = '/usr/bin/google-chrome'
headless_browser = initialize_and_get_headless_browser(chrome_application_path, logger)

bandcamp_account_username = os.environ.get("BANDCAMP_ACCOUNT_USERNAME")
bandcamp_account_password = os.environ.get("BANDCAMP_ACCOUNT_PASSWORD")

headless_browser.get("https://bandcamp.com/login")

headless_browser.find_element(by=By.ID, value="username-field").send_keys(bandcamp_account_username)
headless_browser.find_element(by=By.ID, value="password-field").send_keys(bandcamp_account_password)
headless_browser.find_element(by=By.XPATH, value="//button[@type='submit']").click()

logger.debug("Clicked login. Waiting for user page to load")
show_more_button_element = wait_for_element(headless_browser, By.XPATH, "//button[@class='show-more']")

if show_more_button_element is None:
    filename = save_browser_current_page(headless_browser.current_url,
                                         headless_browser.page_source,
                                         "showmore-timeout")
    logger.error(f"Waiting for 'Show More' button timed out. Page source saved to {filename}")

    sys.exit(-1)
logger.debug("User page loaded")

show_more_button_element.click()
time.sleep(1)

container_height = headless_browser.execute_script("return propOpenWrapper.scrollHeight")
logger.debug(f"Scrolling to load all user purchased albums. Container initial height {container_height}")

scrolling_iters = 10
i = 0
container_height = headless_browser.execute_script("return propOpenWrapper.scrollHeight")
while i < scrolling_iters:
    i += 1
    headless_browser.execute_script("window.scrollTo(0, propOpenWrapper.scrollHeight);")
    container_height = headless_browser.execute_script("return propOpenWrapper.scrollHeight")

    try:
        headless_browser.find_element(by=By.CLASS_NAME, value="loading-new-items")
        time.sleep(1)
    except Exception:
        logger.debug(
            f"No more 'loading-new-items' spinner. All purchased albums should be loaded on page. Container final height {container_height}")
        break

album_elements = headless_browser.find_elements(by=By.CLASS_NAME, value="collection-title-details")
print(f"Album elements count {len(album_elements)}")
# for album_element in album_elements:
#   print(album_element.text.replace("\n"," "))

all_art_container_elements = headless_browser.find_elements(by=By.CLASS_NAME, value="collection-item-art-container")

keepcharacters = (' ','_','-')

for art_container_element in all_art_container_elements:
    inner_container = None

    try:
        inner_container = art_container_element.find_element(by=By.CLASS_NAME, value="banner-inner")
    except selenium.common.exceptions.NoSuchElementException:
        continue

    if inner_container is not None:
        img_element = art_container_element.find_element(by=By.CLASS_NAME, value="collection-item-art")
        img_url = img_element.get_attribute("src")

        album_name = "unknown"
        band_name = "unknown"

        try:
            album_text_element = art_container_element.find_element(by=By.XPATH, value="following-sibling::*")
            album_name = album_text_element.find_element(by=By.CLASS_NAME, value="collection-item-title").text
            band_name = album_text_element.find_element(by=By.CLASS_NAME, value="collection-item-artist").text
            band_name = band_name.replace("by ","")
        except selenium.common.exceptions.NoSuchElementException:
            print ("CANT FIND SIBLING")

        print(f"{album_name} {band_name} {img_url}")

        filename = "".join(c for c in f"{band_name}--{album_name}" if c.isalnum() or c in keepcharacters).rstrip()
        img_suffix_from_url = pathlib.Path(os.path.basename(urllib.parse.urlparse(img_url).path)).suffix
        filename = filename+img_suffix_from_url

        print(filename)

        response = requests.get(img_url, stream=True)
        with open(filename, 'wb') as out_file:
            shutil.copyfileobj(response.raw, out_file)
        del response

    else:
        print("no inner container")

"""

download_elements = headless_browser.find_elements(by=By.XPATH, value="//a[text()='download']")
print(f"Download element count {len(download_elements)}")

download_links = []
for download_element in download_elements:
    download_links.append(download_element.get_attribute("href"))

for download_link in download_links:
    #print(f"downloading link {download_link}")
    headless_browser.get(download_link)
    title_element = wait_for_element(headless_browser, By.CLASS_NAME, "title")
    album_title = title_element.text
    album_artist = headless_browser.find_element(by=By.CLASS_NAME, value="artist").text.replace("by","").strip()

    print(f"Downloading {album_title} {album_artist}")
    download_url = None
    while True:
        album_download_element = headless_browser.find_element(by=By.XPATH, value="//a[text()='Download']")
        try:
            download_url = album_download_element.get_attribute("href")
            if download_url is None or download_url == "":
                print("Waiting for download to be ready")
                time.sleep(1)
                continue
            else:
                break
        except Exception:
            print("caught exception asking for href. assuming it isn't there?")
            time.sleep(1)

    if download_url is not None:
        #headless_browser.get(download_url)
        pass
    else:
        print("DOWNLOAD LINK IS NONE")
    time.sleep(5)

"""
time.sleep(5)
headless_browser.quit()