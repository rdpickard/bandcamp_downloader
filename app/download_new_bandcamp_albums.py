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

from selenium import webdriver
import selenium.common.exceptions
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager


chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

bandcamp_account_username = os.environ.get("BANDCAMP_ACCOUNT_USERNAME")
bandcamp_account_password = os.environ.get("BANDCAMP_ACCOUNT_PASSWORD")

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

download_dir = os.path.join(bandcamp_downloader_config["downloads_dir"], arrow.get().format("YYYY-M-D_HH:mm_ZZ"))
if not os.path.exists(download_dir):
    os.makedirs(download_dir)

allowed_nonalpha_filename_characters = (' ','_','-',":")

def save_browser_current_page(url_of_content,
                              content,
                              prefix=None,
                              notes=None,
                              save_dir=bandcamp_downloader_config["headless_browser_scraped_pages_dir"]):
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    if prefix is None:
        prefix = ""
    else:
        prefix = prefix + "-"

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

def wrapped_find_elements_by(browser, root_element, element_by, element_value, logger, save_prefix=None):
    try:
        found_elements = root_element.find_elements(by=element_by, value=element_value)
        return found_elements
    except Exception as e:
        notes = f"Could not find element by {element_by} with value {element_by}"
        saved_filename = save_browser_current_page(browser.current_url,
                                             browser.page_source,
                                             save_prefix,
                                             notes=notes)
        msg = f"Could not find element by {element_by} with value {element_by} file saved to {saved_filename}"
        logger.error(msg)
        logger.debug(e)
        return e


def wrapped_find_element_by(browser, root_element, element_by, element_value, logger, save_prefix=None):
    found_elements = wrapped_find_elements_by(browser, root_element, element_by, element_value, logger, save_prefix=None)
    if type(found_elements) is Exception:
        return found_elements

    return found_elements[0]


class HeadlessBrowserScrapeException(Exception):
    scraped_url = None
    page_contents = None
    page_element = None
    saved_file_name = None

    def __init__(self, message, scraped_url, page_contents, page_element=None, notes=None):
        super().__init__(message)
        self.scraped_url = scraped_url
        self.page_contents = page_contents
        self.page_element = page_element

        self.saved_file_name = save_browser_current_page(scraped_url, page_contents, notes=notes)


def initialize_and_get_headless_browser(chrome_application_path, logger):
    logging.getLogger('WDM').setLevel(logging.NOTSET)
    os.environ['WDM_LOG'] = "false"

    # tui_terminal_console.log(f"Setting up headless browser  {chrome_application_path}")
    logger.info(f"Setting up headless browser  {chrome_application_path}")

    chrome_options = webdriver.ChromeOptions()
    # chrome_options.add_argument("--headless")
    chrome_options.add_experimental_option("prefs",
                                           {"download.default_directory": download_dir})
    chrome_options.binary_location = chrome_application_path

    the_headless_browser = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    return the_headless_browser


def wait_for_element(browser, element_by, element_value, timeout_seconds=10):
    element = None
    start_time = arrow.utcnow()
    while (arrow.utcnow() - start_time).seconds < timeout_seconds:
        try:
            element = browser.find_element(by=element_by, value=element_value)
            if element is None:
                time.sleep(.5)
        except selenium.common.exceptions.NoSuchElementException as nsee:
            logger.debug(f"could not yet find element {element_value}, waiting...")
            time.sleep(.5)
    if element is None:
        logger.debug(f"waiting on element {element_value} that was never found")
    return element

def filename_from_httpresponse(response):
    if 'content-disposition' not in response.headers.keys():
        return None
    filename_matches = re.findall("filename=\"(.+)\"", response.headers['content-disposition'])
    if filename_matches is None or len(filename_matches) < 1:
        return None
    return filename_matches[0]

logger = logging.getLogger('BandCamp Downloader')
logger.setLevel(bandcamp_downloader_config["logging_level"])
file_logging_handler = logging.FileHandler(os.path.join(bandcamp_downloader_config["logging_files_dir"],
                                                        "BandCampDownloader.log"))
file_logging_handler_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_logging_handler.setFormatter(file_logging_handler_formatter)
logger.addHandler(file_logging_handler)

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


headless_browser = initialize_and_get_headless_browser(chrome_path, logger)

logger.info("Logging in to Bandcamp")
headless_browser.get("https://bandcamp.com/login")

headless_browser.find_element(by=By.ID, value="username-field").send_keys(bandcamp_account_username)
headless_browser.find_element(by=By.ID, value="password-field").send_keys(bandcamp_account_password)
headless_browser.find_element(by=By.XPATH, value="//button[@type='submit']").click()
filename = save_browser_current_page(headless_browser.current_url, headless_browser.page_source, prefix="before-captcha")
logger.info(f"BEFORE CAPTCHA DECTOR {filename}")

logger.debug("Clicked login. Waiting for user page to load")

# TODO need to catch / notify there is a CAPTCHA


time.sleep(.5)

filename = save_browser_current_page(headless_browser.current_url, headless_browser.page_source, prefix="after-captcha")
logger.info(f"CAPTCHA {filename}")

try:
    recaptcha = headless_browser.find_element(by=By.ID, value="global-invisible-recaptcha")
    if "opacity" in recaptcha.get_attribute("style"):
        filename = save_browser_current_page(headless_browser.current_url, headless_browser.page_source, prefix="captcha")
        logger.info(f"CAPTCHA DETECTED {filename}")
        #quit()
except selenium.common.exceptions.NoSuchElementException as nsee:
    pass


show_more_button_element = wait_for_element(headless_browser, By.XPATH, "//button[@class='show-more']")

if show_more_button_element is None:
    filename = save_browser_current_page(headless_browser.current_url,
                                         headless_browser.page_source,
                                         "showmore-timeout",
                                         notes="XPATH //button[@class='show-more']")
    logger.error(f"Waiting for 'Show More' button timed out. Maybe a CAPTCHA Page source saved to {filename}")
    sys.exit(-1)

logger.debug("User page loaded")

show_more_button_element.click()
time.sleep(1)

init_container_height = headless_browser.execute_script("return propOpenWrapper.scrollHeight")
logger.debug(f"Scrolling to load all user purchased albums. Container initial height {init_container_height}")

scrolling_iters = 100
i = 0
container_height = 0

logger.info("Scrolling collection page to get all albums")

# TODO The timeout method of scrolling through the albums needs to be done a better way
scroll_time = arrow.now()
while True:

    if i >= scrolling_iters:
        logger.debug("Scrolling stopped because of iterations, not spinner detection")
        break

    i += 1
    headless_browser.execute_script("window.scrollTo(0, propOpenWrapper.scrollHeight);")

    new_container_height = headless_browser.execute_script("return propOpenWrapper.scrollHeight")
    logger.debug(f"Scrolled from {container_height} to {new_container_height}")

    if new_container_height != container_height:
        container_height = new_container_height
        scroll_time = arrow.now()
        continue

    if (arrow.now() - scroll_time).seconds >= 15:
        logger.debug(f"Reached end of list with with container height at {new_container_height}")
        break

    time.sleep(.5)

logger.debug("Finding all albums")
albums = []

album_elements = wrapped_find_elements_by(headless_browser, headless_browser,
                                          By.XPATH, "//li[starts-with(@id, 'collection-item-container_')]",
                                          logger)
if type(album_elements) is Exception:
    logger.fatal("Cloud not find albums on user page")
    sys.exit(-1)

logger.info("Collecting details of albums in collection")
for album_element in album_elements:

    # TODO should wrap these in wrapped_findelements
    album_name = album_element.find_element(by=By.CLASS_NAME, value="collection-item-title").text
    album_artist = album_element.find_element(by=By.CLASS_NAME, value="collection-item-artist").text.replace("by ","")
    album_is_new_to_collection = False
    album_art_url = None
    album_download_page_url = None

    logger.debug(f"Found {album_name} - {album_artist}")

    # Find the album name and artist name
    try:
        inner_container = album_element.find_element(by=By.CLASS_NAME, value="banner-inner")
        if inner_container.text.strip() == "New":
            album_is_new_to_collection = True
        else:
            logger.debug(f"Album {album_name} - {album_artist} has inner banner but text is '{inner_container.text}'. Expected 'New'. Not counting as new.")
    except selenium.common.exceptions.NoSuchElementException:
        # No inner banner, which is fine and isnt considered an error, we'll just move on
        pass

    # Find the link to the download page for the album. The URL can't be derived from info about the album, it needs
    # to be scraped from the page source
    wait_time = .5
    wait_timeout = 5
    start_time = arrow.now()
    while True:
        if (arrow.now() - start_time).seconds >= wait_timeout:
            file_name = save_browser_current_page(headless_browser.current_url, headless_browser.page_source,
                                                  f"album-details-{album_name}-{album_artist}",
                                                  notes="download button")
            logger.info(f"Timeout waiting for download link for album {album_name} - {album_artist}. Skipping. filesaved to {file_name} for debug")
            break

        album_download_element = wrapped_find_element_by(headless_browser, album_element,
                                                         By.LINK_TEXT, "download", logger)
        if type(album_download_element) is Exception:
            time.sleep(wait_time)
            continue

        download_page_url = album_download_element.get_attribute("href")
        if download_page_url is None or download_page_url == "":
            logger.debug(f"Found download element for {album_name} - {album_artist} but no link, might not be ready")
            time.sleep(wait_time)
            continue

        album_download_page_url = download_page_url
        break

    if album_download_page_url is None:
        logger.info("Could not find download page for {album_name} - {album_artist}. Skipping")
        continue


    # Find the URL of the image source of the album art
    img_element = wrapped_find_element_by(headless_browser, album_element,
                                          By.CLASS_NAME, "collection-item-art",
                                          logger)
    if type(img_element) is Exception:
        logger.info("Could not find element containing album art, skipping")
        continue
    album_art_url = img_element.get_attribute("src")


    albums.append({"name": album_name, "artist": album_artist,
                   "is_new": album_is_new_to_collection, "art_url": album_art_url,
                   "download_page_url": album_download_page_url})


# Output scraped details to debug log
logger.debug(f"scraped {len(albums)} albums")
for album in albums:
    logger.debug(f"scraped=>{album}")


# Create a requests session that has all of the cookies from the Chrome instance to inherit the Bandcamp session
dl_session = requests.session()
for cookie_dict in headless_browser.get_cookies():
    dl_session.cookies.set(cookie_dict["name"], cookie_dict["value"], domain=cookie_dict["domain"])

downloaded_count = 0

number_of_new_albums = len(list(filter(lambda album: album["is_new"], albums)))

if number_of_new_albums > 0:
    logger.info(f"{number_of_new_albums} new albums to download!")
else:
    logger.info(f"No new albums to download. Exiting")
    sys.exit(0)

for album in albums:
    # TODO need to toggle downloading non-new albums too
    if not album["is_new"]:
        continue

    logger.info(f"Downloading {album['name']} {album['artist']}")

    filename = "".join(c for c in f"{album['artist']} - {album['name']}" if c.isalnum() or c in allowed_nonalpha_filename_characters).rstrip()

    img_suffix_from_url = pathlib.Path(os.path.basename(urllib.parse.urlparse(album['art_url']).path)).suffix
    img_local_filename = filename + img_suffix_from_url

    album_local_filename = filename + ".album"

    default_img_filename = filename + img_suffix_from_url
    default_album_filename = filename + ".album"

    # download the album art
    art_response = dl_session.get(album['art_url'], stream=True)
    logger.debug(f"art response headers {art_response.headers}")
    if art_response.status_code != 200:
        logger.error(f"Request for album art {album['name']} - {album['artist']} for returned HTTP status code {art_response.status_code}. Expecting 200. Skipping. URL {album['art_url']}")
        continue
    image_fullfile_path = os.path.join(download_dir, filename_from_httpresponse(art_response) or default_img_filename)
    logger.info(f"Saving album art {album['name']} - {album['artist']} to {image_fullfile_path}")
    with open(image_fullfile_path, 'wb') as out_file:
        shutil.copyfileobj(art_response.raw, out_file)
    del art_response
    logger.debug(f"FINISHED Saving album art {album['name']} - {album['artist']} to {image_fullfile_path}")

    # Go to the page where the album can be downloaded from
    logger.debug(f"Going to download page for {album['name']} - {album['artist']} {album['download_page_url']}")
    headless_browser.get(album['download_page_url'])

    # wait for the download link to be 'prepared'
    wait_time = .5
    wait_timeout = 5
    start_time = arrow.now()
    download_file_url = None
    while True:
        if (arrow.now() - start_time).seconds >= wait_timeout:
            file_name = save_browser_current_page(headless_browser.current_url, headless_browser.page_source,
                                                  f"album-downloadpage-{album['name']}-{album['artist']}",
                                                  notes="download button")
            logger.info(f"Timeout waiting for download link for album {album['name']}-{album['artist']}. Skipping. filesaved to {file_name} for debug")
            break

        download_anchor_element = wrapped_find_element_by(headless_browser, headless_browser,
                                                          By.XPATH, "//a[text()='Download']",
                                                          logger)
        if type(download_anchor_element) is Exception:
            time.sleep(wait_time)
            continue

        if "display: none" in download_anchor_element.get_attribute("style").lower():
            time.sleep(wait_time)
            continue

        download_file_url = download_anchor_element.get_attribute("href")
        logger.debug(f"{album['name']}-{album['artist']} download file url is {download_file_url}")
        break

    if download_file_url is None:
        logger.info("Could not get URL to download album {album['name']}-{album['artist']}. Skipping")
        continue

    logger.debug(f"Going to download {album['name']}-{album['artist']} download file url is {download_file_url}")
    album_response = dl_session.get(download_file_url, stream=True)
    logger.debug(f"album download response headers {album_response.headers}")
    if album_response.status_code != 200:
        logger.error(f"Request for album downlad {album['name']} - {album['artist']} for returned HTTP status code {album_response.status_code}. Expecting 200. Skipping. URL {download_file_url}")
        continue
    album_fullfile_path = os.path.join(download_dir,
                                       filename_from_httpresponse(album_response) or default_album_filename)
    logger.info(f"Saving album {album['name']} - {album['artist']} to {album_fullfile_path}")
    with open(album_fullfile_path, 'wb') as out_file:
        shutil.copyfileobj(album_response.raw, out_file)
    del album_response
    logger.debug(f"FINISHED Saving album {album['name']} - {album['artist']} to {album_fullfile_path}")


time.sleep(5)
headless_browser.quit()