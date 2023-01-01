import headless_bandcamp_interface

import logging
import os
import sys

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

bci.login_to_bandcamp(os.environ.get("BANDCAMP_ACCOUNT_USERNAME"),
                      os.environ.get("BANDCAMP_ACCOUNT_PASSWORD"))

purchased_albums = bci.get_albums_in_library()
print(purchased_albums)
