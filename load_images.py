
import scraper

import json
import os
import sys
import requests
from progress.bar import Bar


# https://stackoverflow.com/questions/4934806/how-can-i-find-scripts-directory
def get_script_path():
    return os.path.dirname(os.path.realpath(sys.argv[0]))


def clone_image_url(item_type):
    _failed_items = []
    _succ_ids = set()
    with open("{}.json".format(item_type)) as f:
        items = json.load(f)

    try:
        os.makedirs(f"{get_script_path()}/statics/{scraper.inv_item_type_choices[item_type]}", 0o755)
    except FileExistsError:
        pass

    bar = Bar(f"downloading images for {scraper.inv_item_type_choices[item_type]}...", max=len(items["en"]))

    for item in items["en"]:
        url = item["image_url"]
        r = requests.get(url)  # timeout=60*5
        _, file_ext = os.path.splitext(url)

        if item['ankama_id'] in _succ_ids:
            bar.next()
            continue

        if sys.getsizeof(r.content) > 200:
            _succ_ids.add(item['ankama_id'])

            with open(f"{get_script_path()}/statics/{scraper.inv_item_type_choices[item_type]}/{item['ankama_id']}{file_ext}", 'wb') as f:
                f.write(r.content)
        else:
            _failed_items.append({"ankama_id": item['ankama_id'], "image_url": item["image_url"]})

        bar.next()
    bar.finish()

    with open(f"{get_script_path()}/statics/nf_{item_type}.json", 'w') as f:
        json.dump({"en": _failed_items}, f, indent=4, ensure_ascii=False)


for plural, single in scraper.item_type_choices.items():
    clone_image_url(single)
