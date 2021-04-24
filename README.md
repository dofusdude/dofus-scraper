# Dofus Scraper
Cloudscraper based encyclopedia scraping to JSON and API creation client with Python.

## Usage
Install dependencies (requires Python 3 with pip) `./setup.sh`

The script should be used like a CLI.
See the usage with `python3 scraper.py --help`.

## Example
Scraping all data to JSON.
```sh
$ python3 scraper.py --scrape --check
```

Scraping all not found to JSON. If still be not found, try again later.
```sh
$ python3 scraper.py --notfound --check
```

Call API to create english items via JSON data on the API.
```sh
$ python3 scraper.py --api --create
```

Only update languages data to the API.
```sh
$ python3 scraper.py --api --lang
```

## Notice
This script was build for populating the Dofus API. The needed steps might not suit your use case.
Furthermore, the script is not perfect - a few categories could need multiple tries to get the JSON or API calls right.


## License
Author: Christopher Sieh <stelzo@steado.de>

This project is licensed under the GPLv3 License.
