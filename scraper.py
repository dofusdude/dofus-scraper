"""
Dofus Scraper: Multilingual scraping of the Dofus encyclopedia.
Copyright (C) 2021 Christopher Sieh
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import cfscrape
from bs4 import BeautifulSoup
import time
import requests
import re
import json
import threading
import argparse
import logging
import os.path
from progress.spinner import Spinner
from progress.bar import Bar
import os

### CONFIG ###

with open("config.json") as f:
    config_json = json.load(f)
    API_KEY = config_json["api-key"]
    API_URL = config_json["api-url"]

### ###
_weapons = dict()
_consumables = dict()
_equipments = dict()
_sets = dict()
_resources = dict()
_pets = dict()

_init_load_json_resources = None
_init_load_json_consumables = None
_init_load_json_equipment = None
_init_load_json_weapons = None
_init_load_json_sets = None
_init_load_json_pets = None

_weapons_nf = []
_consumables_nf = []
_equipments_nf = []
_sets_nf = []
_resources_nf = []
_pets_nf = []

# scrape specifics
item_type_choices = {"weapons": "weapon", "consumables": "consumable", "equipment": "equipment",
                     "resources": "resource", "pets": "pet", "sets": "set"}
inv_item_type_choices = {v: k for k, v in item_type_choices.items()}
languages = ["en", "fr", "de", "es", "pt", "it"]

headers = {"Authorization": f"Bearer {API_KEY}"}
session = requests.Session()
scraper = cfscrape.create_scraper(sess=session)

dofus_base_url = "https://www.dofus.com"

ency_base_url = dofus_base_url + "/de/mmorpg/leitfaden"

resources_base_url = ency_base_url + "/ressourcen?size=96&page=1"

weapon_base_url = ency_base_url + "/waffen?size=96&page=1"
consumable_base_url = ency_base_url + "/konsumgueter?size=96&page=1"
equip_base_url = ency_base_url + "/ausruestung?size=96&page=1"
set_base_url = ency_base_url + "/sets?size=96&page=1"
pet_base_url = ency_base_url + "/vertraute?size=96&page=1"

langdict = dict()
langdict["de,level"] = "Stufe: "
langdict["en,level"] = "Level: "
langdict["es,level"] = "Nivel: "
langdict["it,level"] = "Livello: "
langdict["fr,level"] = "Niveau : "
langdict["pt,level"] = "Nível: "


def numbersFromString(str):
    return re.findall(r'-?[0-9]\d*', str)


def addLangArrIfNotExist(obj, lang):
    if lang not in obj:
        obj[lang] = []


def scrape_resource(item_ref):
    item_html = scraper.get(dofus_base_url + item_ref).content
    item_soup = BeautifulSoup(item_html, 'html.parser')
    # get all langs
    lang_links = item_soup.find("div", {"class": "ak-box-lang"}).find_all("a")
    item_id = numbersFromString(item_ref)[0]

    # swap to get english to front
    lang_links[0], lang_links[1] = lang_links[1], lang_links[0]

    for lang in lang_links:
        curr_lang = str(lang['hreflang'])
        item_link = dofus_base_url + lang['href']
        item_link = item_link[0:item_link.index(str(item_id)) + len(str(item_id))]
        item_html = scraper.get(item_link)
        if item_html.status_code == 404:
            _resources_nf.append(item_link.replace(dofus_base_url, ""))
            break
        item_soup = BeautifulSoup(item_html.text, 'html.parser')

        item_detail = item_soup.find("div", {"class": "ak-encyclo-detail-right"})
        item_name = item_soup.find("h1", {"class": "ak-return-link"}).text.strip()
        item_type = item_soup.find("div", {"class": "ak-encyclo-detail-type"}).find("span").text
        item_level = str(item_soup.find("div", {"class": "ak-encyclo-detail-level"}).text).replace(
            langdict[curr_lang + ",level"], "")
        item_desc = item_detail.find("div", {"class": "ak-panel-content"}).text.strip()
        item_image = item_soup.find("img", {"class": "img-maxresponsive"})['src']

        joined = "/".join(item_image.split("/")[-3:])
        item_image = "https://static.ankama.com/dofus/www/game/" + joined

        item_recepit_container = item_soup.find("div", {"class": "ak-crafts"})
        item_receipt = None
        if item_recepit_container is not None:
            item_receipt = []
            item_recepit_container = item_recepit_container.find_all("div", {"class": "col-sm-6"})
            for receipt_item in item_recepit_container:
                receipt_item_id = int(numbersFromString(receipt_item.find("a")['href'].split('/')[-1])[0])
                receipt_item_quantity = int(
                    numbersFromString(receipt_item.find("div", {"class": "ak-front"}).text.strip())[0])
                receipt_item_type = receipt_item.find("div", {"class": "ak-text"}).text.strip()
                item_receipt_obj = dict()
                item_receipt_obj['item_id'] = receipt_item_id
                item_receipt_obj['quantity'] = int(receipt_item_quantity)
                item_receipt_obj['item_type'] = receipt_item_type
                item_receipt.append(item_receipt_obj)

        # send to api
        obj = {
            "ankama_id": item_id,
            "type": item_type,
            "description": item_desc.replace('\n', " ").replace("\r\n", " ") if item_desc else None,
            "name": item_name,
            "image_url": item_image,
            "ankama_url": item_link,
            "level": int(item_level),
            "recipe": item_receipt
        }

        addLangArrIfNotExist(_resources, curr_lang)
        _resources[curr_lang].append(obj)


def scrape_pet(item_ref):
    item_html = scraper.get(dofus_base_url + item_ref).content
    item_soup = BeautifulSoup(item_html, 'html.parser')
    # get all langs
    lang_links = item_soup.find("div", {"class": "ak-box-lang"}).find_all("a")
    item_id = numbersFromString(item_ref)[0]

    # swap to get english to front
    lang_links[0], lang_links[1] = lang_links[1], lang_links[0]

    for lang in lang_links:
        curr_lang = str(lang['hreflang'])
        item_link = dofus_base_url + lang['href']
        item_link = item_link[0:item_link.index(str(item_id)) + len(str(item_id))]
        item_html = scraper.get(item_link)
        if item_html.status_code == 404:
            _pets_nf.append(item_link.replace(dofus_base_url, ""))
            break
        item_soup = BeautifulSoup(item_html.text, 'html.parser')

        item_detail = item_soup.find("div", {"class": "ak-encyclo-detail-right"})
        item_name = item_soup.find("h1", {"class": "ak-return-link"}).text.strip()
        item_type = item_soup.find("div", {"class": "ak-encyclo-detail-type"}).find("span").text
        item_level = str(item_soup.find("div", {"class": "ak-encyclo-detail-level"}).text).replace(
            langdict[curr_lang + ",level"], "")
        item_desc = item_detail.find("div", {"class": "ak-panel-content"}).text.strip()
        item_image = item_soup.find("img", {"class": "img-maxresponsive"})['src']

        joined = "/".join(item_image.split("/")[-3:])
        item_image = "https://static.ankama.com/dofus/www/game/" + joined

        # pet specific
        item_effects = item_detail.find_all("div", {"class": "col-sm-6"})

        item_dict = dict()

        item_dict['conditions'] = None
        item_dict['characteristics'] = None

        if len(item_effects) == 2:  # effects and conditions
            # effects can be still displayed single, check via <select> tag in effects
            if item_effects[0].find("select"):
                item_effects_container = item_effects[0]
                item_conditions_container = item_effects[1]
            else:
                item_effects_container = item_effects[1]
                item_conditions_container = item_effects[0]

            # conditions
            item_char_title = item_conditions_container.find("div", {"class": {"ak-panel-content"}})
            if item_char_title:
                item_conditions = item_char_title.text.strip()
                item_dict['conditions'] = item_conditions.replace('\n', " ").replace("\r\n",
                                                                                     " ") if item_conditions else None
            else:
                item_conditions = None

            pet_level_html = scraper.post(item_link, headers={
                "Accept": "text/html, */*; q=0.01",
                "Accept-Language": "de,en-US;q=0.7,en;q=0.3",
                "Accept-Encoding": "gzip, deflate, br",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest",
                "DNT": "1",
                "Connection": "keep-alive",
                "Pragma": "no-cache",
                "Cache-Control": "no-cache",
                "TE": "Trailers",
                "X-PJAX": "true",
                "X-PJAX-Container": ".ak-item-details-container"},
                                          data="level=100&_pjax=.ak-item-details-container").text
            pet_level_soup = BeautifulSoup(pet_level_html, 'html.parser')
            pet_effects = pet_level_soup.find_all("div", {"class": "ak-title"})

            if len(pet_effects) == 0:
                item_dict["characteristics"] = None
            else:
                item_dict["characteristics"] = []
            for item_effect_el in pet_effects:
                item_effect_dict = dict()
                item_effect_dict['value'] = None
                item_effect_dict['name'] = ""

                item_effect_el = item_effect_el.text.strip()
                if not (item_effect_el.startswith('-') or (
                        item_effect_el.startswith('+') or item_effect_el[0].isdigit())):
                    item_effect_dict['name'] = item_effect_el  # special like jahash
                else:
                    effect_numbers = numbersFromString(item_effect_el)
                    item_effect_dict['value'] = effect_numbers[0]

                    # all after last digits are effects
                    effect_str = item_effect_el[
                                 item_effect_el.index(effect_numbers[-1]) + len(str(effect_numbers[-1])):].strip()
                    item_effect_dict['name'] = effect_str

                item_dict['characteristics'].append(item_effect_dict)

        # send to api
        obj = {
            "ankama_id": item_id,
            "type": item_type,
            "description": item_desc.replace('\n', " ").replace("\r\n", " ") if item_desc else None,
            "name": item_name,
            "image_url": item_image,
            "ankama_url": item_link,
            "level": int(item_level),
            "characteristics": item_dict["characteristics"],
            "conditions": item_dict["conditions"].replace('\n', " ").replace("\r\n", " ") if item_dict[
                "conditions"] else None
        }

        addLangArrIfNotExist(_pets, curr_lang)
        _pets[curr_lang].append(obj)


def scrape_set(item_ref):
    item_html = scraper.get(dofus_base_url + item_ref).content
    item_soup = BeautifulSoup(item_html, 'html.parser')
    # get all langs
    lang_links = item_soup.find("div", {"class": "ak-box-lang"}).find_all("a")
    item_id = numbersFromString(item_ref)[0]

    # swap to get english to front
    lang_links[0], lang_links[1] = lang_links[1], lang_links[0]

    for lang in lang_links:
        item_dict = dict()
        curr_lang = str(lang['hreflang'])
        item_link = dofus_base_url + lang['href']
        item_link = item_link[0:item_link.index(str(item_id)) + len(str(item_id))]
        item_html = scraper.get(item_link)
        if item_html.status_code == 404:
            _sets_nf.append(item_link.replace(dofus_base_url, ""))
            break
        item_soup = BeautifulSoup(item_html.text, 'html.parser')

        set_name = item_soup.find("h1", {"class": "ak-return-link"}).text.strip()
        set_level = str(item_soup.find("div", {"class": "ak-encyclo-detail-level"}).text).replace(
            langdict[curr_lang + ",level"], "")
        set_id = numbersFromString(item_ref)[0]
        set_image = item_soup.find("img", {"class": "img-maxresponsive"})['src']

        item_dict['name'] = set_name
        item_dict['ankama_id'] = set_id
        item_dict['ankama_url'] = item_link
        item_dict['image_url'] = set_image
        item_dict['level'] = int(set_level)

        set_contains_container = item_soup.find("div", {"class": "ak-set-composition"}).find("tbody")
        set_contains_elements = set_contains_container.find_all("tr")
        set_contains = []

        for set_contains_element in set_contains_elements:
            equip_id = \
                numbersFromString(set_contains_element.find("span", {"class": "ak-linker"}).find("a")['href'].strip())[
                    0]
            equip_type = set_contains_element.find("div", {"class": "ak-item-type-info"}).text.strip()
            # el_dict = dict()
            # el_dict['ankama_id'] = equip_id
            # el_dict['type'] = equip_type
            set_contains.append(equip_id)

        item_dict['items'] = set_contains

        bonus_selector = item_soup.find("select", {"class": "ak-set-bonus-select"})
        bonus_selector_options = bonus_selector.find_all("option")
        set_bonus_list = item_soup.find_all("div", {"class": "set-bonus-list"})

        item_dict["effects"] = []
        i = 0
        for bonus_soup in set_bonus_list:
            effect_list = bonus_soup.find_all("div", {"class": "ak-title"})
            effect_combo = dict()
            effect_combo['quantity'] = bonus_selector_options[i]["value"]
            effect_combo['bonus'] = []
            i += 1

            for item_effect_el in effect_list:
                item_effect_dict = dict()
                item_effect_dict['value'] = None
                item_effect_dict['name'] = ""

                item_effect_el = item_effect_el.text.strip()
                if not (item_effect_el.startswith('-') or (
                        item_effect_el.startswith('+') or item_effect_el[0].isdigit())):
                    item_effect_dict['name'] = item_effect_el  # special like jahash
                else:
                    effect_numbers = numbersFromString(item_effect_el)
                    item_effect_dict['value'] = effect_numbers[0]

                    # all after last digits are effects
                    effect_str = item_effect_el[
                                 item_effect_el.index(effect_numbers[-1]) + len(str(effect_numbers[-1])):].strip()
                    item_effect_dict['name'] = effect_str

                effect_combo['bonus'].append(item_effect_dict)
            item_dict['effects'].append(effect_combo)

        # send to api
        addLangArrIfNotExist(_sets, curr_lang)
        _sets[curr_lang].append(item_dict)


def scrape_consumable(item_ref):
    item_html = scraper.get(dofus_base_url + item_ref).content
    item_soup = BeautifulSoup(item_html, 'html.parser')
    # get all langs
    lang_links = item_soup.find("div", {"class": "ak-box-lang"}).find_all("a")
    item_id = numbersFromString(item_ref)[0]

    # swap to get english to front
    lang_links[0], lang_links[1] = lang_links[1], lang_links[0]

    for lang in lang_links:
        item_dict = dict()
        curr_lang = str(lang['hreflang'])
        item_link = dofus_base_url + lang['href']
        item_link = item_link[0:item_link.index(str(item_id)) + len(str(item_id))]
        item_html = scraper.get(item_link)
        if item_html.status_code == 404:
            _consumables_nf.append(item_link.replace(dofus_base_url, ""))
            break
        item_soup = BeautifulSoup(item_html.text, 'html.parser')

        item_detail = item_soup.find("div", {"class": "ak-encyclo-detail-right"})
        item_name = item_soup.find("h1", {"class": "ak-return-link"}).text.strip()
        item_type = item_soup.find("div", {"class": "ak-encyclo-detail-type"}).find("span").text
        item_level = str(item_soup.find("div", {"class": "ak-encyclo-detail-level"}).text).replace(
            langdict[curr_lang + ",level"], "")
        item_id = numbersFromString(item_ref)[0]
        item_desc = item_detail.find("div", {"class": "ak-panel-content"}).text.strip()
        item_image = item_soup.find("img", {"class": "img-maxresponsive"})['src']

        joined = "/".join(item_image.split("/")[-3:])
        item_image = "https://static.ankama.com/dofus/www/game/" + joined

        item_dict['name'] = item_name
        item_dict['type'] = item_type
        item_dict['ankama_id'] = item_id
        item_dict['description'] = item_desc.replace('\n', " ").replace("\r\n", " ") if item_desc else None
        item_dict['image_url'] = item_image
        item_dict['level'] = int(item_level)

        item_effects = item_detail.find_all("div", {"class": "ak-panel-content"})
        item_dict['effects'] = None
        item_dict['conditions'] = None
        item_dict['ankama_url'] = item_link
        item_effect_array = []
        item_require = None
        effects = []  # give back as string array but on server: find closest bonus without numbers, extract numbers and set bonus
        if len(item_effects) == 3:  # only effect
            item_effect_cont = item_effects[-1].find_all("div", {"class": "ak-title"})
            for item_effect in item_effect_cont:
                item_effect_array.append(item_effect.text.strip())

        elif len(item_effects) == 4:
            item_effect_cont = item_effects[-1].find_all("div", {"class": "ak-title"})
            for item_effect in item_effect_cont:
                item_effect_array.append(item_effect.text.strip())
            item_require = item_effects[-1].find("div", {"class": "ak-title"}).text.strip()

        item_dict['effects'] = item_effect_array
        item_dict['conditions'] = item_require.replace('\n', " ").replace("\r\n", " ") if item_require else None
        item_recepit_container = item_soup.find("div", {"class": "ak-crafts"})
        item_receipt = None
        if item_recepit_container is not None:
            item_receipt = []
            item_recepit_container = item_recepit_container.find_all("div", {"class": "col-sm-6"})
            for receipt_item in item_recepit_container:
                receipt_item_id = int(numbersFromString(receipt_item.find("a")['href'].split('/')[-1])[0])
                receipt_item_quantity = int(
                    numbersFromString(receipt_item.find("div", {"class": "ak-front"}).text.strip())[0])
                receipt_item_type = receipt_item.find("div", {"class": "ak-text"}).text.strip()
                item_receipt_obj = {
                    'item_id': receipt_item_id,
                    'item_quantity': int(receipt_item_quantity),
                    'item_type': receipt_item_type
                }
                item_receipt.append(item_receipt_obj)

        item_dict['recipe'] = item_receipt

        # send to api
        addLangArrIfNotExist(_consumables, curr_lang)
        _consumables[curr_lang].append(item_dict)


def scrape_weapon(item_ref):
    item_html = scraper.get(dofus_base_url + item_ref).content
    item_soup = BeautifulSoup(item_html, 'html.parser')
    # get all langs
    lang_links = item_soup.find("div", {"class": "ak-box-lang"}).find_all("a")
    item_id = numbersFromString(item_ref)[0]

    # swap to get english to front
    lang_links[0], lang_links[1] = lang_links[1], lang_links[0]

    for lang in lang_links:
        item_dict = dict()
        curr_lang = str(lang['hreflang'])
        item_link = dofus_base_url + lang['href']
        item_link = item_link[0:item_link.index(str(item_id)) + len(str(item_id))]
        item_html = scraper.get(item_link)
        if item_html.status_code == 404:
            _weapons_nf.append(item_link.replace(dofus_base_url, ""))
            break
        item_soup = BeautifulSoup(item_html.text, 'html.parser')

        item_detail = item_soup.find("div", {"class": "ak-encyclo-detail-right"})
        item_name = item_soup.find("h1", {"class": "ak-return-link"}).text.strip()
        item_type = item_soup.find("div", {"class": "ak-encyclo-detail-type"}).find("span").text
        item_level = str(item_soup.find("div", {"class": "ak-encyclo-detail-level"}).text).replace(
            langdict[curr_lang + ",level"], "")
        item_desc = item_detail.find("div", {"class": "ak-panel-content"}).text.strip()
        item_image = item_soup.find("img", {"class": "img-maxresponsive"})['src']

        joined = "/".join(item_image.split("/")[-3:])
        item_image = "https://static.ankama.com/dofus/www/game/" + joined

        item_dict['name'] = item_name
        item_dict['type'] = item_type
        item_dict['ankama_id'] = item_id
        item_dict['ankama_url'] = item_link
        item_dict['description'] = item_desc.replace('\n', " ").replace("\r\n", " ") if item_desc else None
        item_dict['image_url'] = item_image
        item_dict['level'] = int(item_level)

        item_effects = item_detail.find_all("div", {"class": "col-sm-6"})

        item_dict['conditions'] = None
        item_dict['characteristics'] = None
        item_dict['effects'] = None

        if len(item_effects) == 2:  # effects and characteristics, optional conditions
            item_characteristics_container = item_effects[1]
            item_effects_container = item_effects[0]

            # conditions
            item_char_title = item_characteristics_container.find_all("div", {"class": {"ak-panel-content"}})
            # print(item_char_title)
            if len(item_char_title) == 2:
                item_conditions = item_char_title[-1].text.strip()
            else:
                item_conditions = None

            item_dict['conditions'] = item_conditions.replace('\n', " ").replace("\r\n",
                                                                                 " ") if item_conditions else item_conditions

            # characteristics
            item_characteristics_container = item_characteristics_container.find_all("div",
                                                                                     {"class": "ak-list-element"})[:-1]
            item_characteristics = []
            for item_char in item_characteristics_container:
                item_characteristic = dict()
                item_char_title = item_char.find("div", {"class": "ak-title"}).text.strip().split(':')
                item_char_attribute = item_char_title[0].strip()
                item_char_attribute_value = item_char_title[1].strip()
                item_characteristic['name'] = item_char_attribute
                item_characteristic['value'] = item_char_attribute_value
                item_characteristics.append(item_characteristic)

            item_dict['characteristics'] = item_characteristics

            # effects
            item_effect_list = item_effects_container.find_all("div", {"class": "ak-title"})
            item_effect_dicts = []

            for item_effect_el in item_effect_list:
                item_effect_dict = dict()
                item_effect_dict['min'] = None
                item_effect_dict['max'] = None
                item_effect_dict['type'] = ""

                item_effect_el = item_effect_el.text.strip()
                if not (item_effect_el.startswith('-') or (
                        item_effect_el.startswith('+') or item_effect_el[0].isdigit())):
                    item_effect_dict['type'] = item_effect_el  # special like jahash
                else:
                    effect_numbers = numbersFromString(item_effect_el)
                    item_effect_dict['min'] = effect_numbers[0]
                    if len(effect_numbers) > 1:
                        item_effect_dict['max'] = effect_numbers[1]

                    # all after last digits are effects
                    effect_str = item_effect_el[
                                 item_effect_el.index(effect_numbers[-1]) + len(str(effect_numbers[-1])):].strip()
                    item_effect_dict['type'] = effect_str

                item_effect_dicts.append(item_effect_dict)
            item_dict['effects'] = item_effect_dicts

        item_recepit_container = item_soup.find("div", {"class": "ak-crafts"})
        item_receipt = None
        if item_recepit_container is not None:
            item_receipt = []
            item_recepit_container = item_recepit_container.find_all("div", {"class": "col-sm-6"})
            for receipt_item in item_recepit_container:
                receipt_item_id = int(numbersFromString(receipt_item.find("a")['href'].split('/')[-1])[0])
                receipt_item_quantity = int(
                    numbersFromString(receipt_item.find("div", {"class": "ak-front"}).text.strip())[0])
                receipt_item_type = receipt_item.find("div", {"class": "ak-text"}).text.strip()
                item_receipt_obj = dict()
                item_receipt_obj['item_id'] = receipt_item_id
                item_receipt_obj['quantity'] = int(receipt_item_quantity)
                item_receipt_obj['item_type'] = receipt_item_type
                item_receipt.append(item_receipt_obj)

        item_dict['recipe'] = item_receipt

        # send to api
        addLangArrIfNotExist(_weapons, curr_lang)
        _weapons[curr_lang].append(item_dict)


def scrape_equipment(item_ref):
    item_html = scraper.get(dofus_base_url + item_ref).content
    item_soup = BeautifulSoup(item_html, 'html.parser')
    # get all langs
    lang_links = item_soup.find("div", {"class": "ak-box-lang"}).find_all("a")
    item_id = numbersFromString(item_ref)[0]

    # swap to get english to front
    lang_links[0], lang_links[1] = lang_links[1], lang_links[0]

    for lang in lang_links:
        item_dict = dict()
        curr_lang = str(lang['hreflang'])
        item_link = dofus_base_url + lang['href']
        item_link = item_link[0:item_link.index(str(item_id)) + len(str(item_id))]
        item_html = scraper.get(item_link)
        if item_html.status_code == 404:
            _equipments_nf.append(item_link.replace(dofus_base_url, ""))
            break
        item_soup = BeautifulSoup(item_html.text, 'html.parser')

        item_detail = item_soup.find("div", {"class": "ak-encyclo-detail-right"})
        item_name = item_soup.find("h1", {"class": "ak-return-link"}).text.strip()
        item_type = item_soup.find("div", {"class": "ak-encyclo-detail-type"}).find("span").text
        item_level = str(item_soup.find("div", {"class": "ak-encyclo-detail-level"}).text).replace(
            langdict[curr_lang + ",level"], "")
        item_id = numbersFromString(item_ref)[0]
        item_desc = item_detail.find("div", {"class": "ak-panel-content"}).text.strip()
        item_image = item_soup.find("img", {"class": "img-maxresponsive"})['src']

        joined = "/".join(item_image.split("/")[-3:])
        item_image = "https://static.ankama.com/dofus/www/game/" + joined

        item_dict['name'] = item_name
        item_dict['type'] = item_type
        item_dict['ankama_id'] = item_id
        item_dict['ankama_url'] = item_link
        item_dict['description'] = item_desc.replace('\n', " ").replace("\r\n", " ") if item_desc else None
        item_dict['image_url'] = item_image
        item_dict['level'] = int(item_level)

        item_effects = item_detail.find_all("div", {"class": "col-sm-6"})

        item_dict['effects'] = None
        item_dict['conditions'] = None

        if len(item_effects) == 2:  # effects and characteristics, optional conditions
            item_characteristics_container = item_effects[1]
            item_effects_container = item_effects[0]

            # conditions
            item_char_title = item_characteristics_container.find_all("div", {"class": {"ak-panel-content"}})
            if len(item_char_title) == 1:
                item_conditions = item_char_title[0].text.strip()
            else:
                item_conditions = None

            item_dict['conditions'] = item_conditions.replace('\n', " ").replace("\r\n",
                                                                                 " ") if item_conditions else None

            # effects
            item_effect_list = item_effects_container.find_all("div", {"class": "ak-title"})
            item_effect_dicts = []

            for item_effect_el in item_effect_list:
                item_effect_dict = dict()
                item_effect_dict['min'] = None
                item_effect_dict['max'] = None
                item_effect_dict['type'] = ""

                item_effect_el = str(item_effect_el.text.strip())
                if not (item_effect_el.startswith('-') or (
                        item_effect_el.startswith('+') or item_effect_el[0].isdigit())):
                    item_effect_dict['type'] = item_effect_el  # special like jahash
                else:
                    effect_numbers = numbersFromString(item_effect_el)
                    item_effect_dict['min'] = effect_numbers[0]
                    if len(effect_numbers) > 1:
                        item_effect_dict['max'] = effect_numbers[1]

                    # all after last digits are effects
                    effect_str = str(item_effect_el[
                                     item_effect_el.index(effect_numbers[-1]) + len(str(effect_numbers[-1])):].strip())
                    item_effect_dict['type'] = effect_str

                item_effect_dicts.append(item_effect_dict)

            item_dict['effects'] = item_effect_dicts

        item_recepit_container = item_soup.find("div", {"class": "ak-crafts"})
        item_receipt = None
        if item_recepit_container is not None:
            item_receipt = []
            item_recepit_container = item_recepit_container.find_all("div", {"class": "col-sm-6"})
            for receipt_item in item_recepit_container:
                receipt_item_id = int(numbersFromString(receipt_item.find("a")['href'].split('/')[-1])[0])
                receipt_item_quantity = int(
                    numbersFromString(receipt_item.find("div", {"class": "ak-front"}).text.strip())[0])
                receipt_item_type = receipt_item.find("div", {"class": "ak-text"}).text.strip()
                item_receipt_obj = dict()
                item_receipt_obj['item_id'] = receipt_item_id
                item_receipt_obj['quantity'] = int(receipt_item_quantity)
                item_receipt_obj['item_type'] = receipt_item_type
                item_receipt.append(item_receipt_obj)

        item_dict['recipe'] = item_receipt

        # send to api
        addLangArrIfNotExist(_equipments, curr_lang)
        _equipments[curr_lang].append(item_dict)


def scrape_list(type, start_url):
    iterate_link = start_url

    # be sure to be on last page
    html = scraper.get(iterate_link).text
    soup = BeautifulSoup(html, 'html.parser')

    pagination_div = soup.find("div", {"class": "ak-pagination"})
    buttons_pagination = pagination_div.find_all("li")

    last_page_button = buttons_pagination[-1]
    last_page_link = str(last_page_button.find("a")['href'])
    last_page_number = int(buttons_pagination[-3].find("a").text)
    nitems = (last_page_number - 1) * 96  # all items before this page
    first_iter = True

    iterate_link = dofus_base_url + last_page_link

    while True:
        successful = False
        res_rows = None
        while not successful:
            try:
                html = scraper.get(iterate_link).text
                soup = BeautifulSoup(html, 'html.parser')
                main_container = soup.find("div", {"class": "ak-main-center"})
                table = main_container.find("table", {"class": {"ak-table", "ak-panel"}}).find("tbody")
                res_rows = table.find_all("tr")
                successful = True
            except AttributeError:
                successful = False
                logging.debug("attribute error, sleeping a sec")
                time.sleep(1)

        if first_iter:
            nitems += len(res_rows)
            first_iter = False

        for row in res_rows:
            # follow each link
            item_ref = str(row.find("a")['href'])
            successful = False
            while not successful:
                # first in main language, then go through all
                try:
                    if type == "resource":
                        scrape_resource(item_ref)
                    elif type == "consumable":
                        scrape_consumable(item_ref)
                    elif type == "weapon":
                        scrape_weapon(item_ref)
                    elif type == "equipment":
                        scrape_equipment(item_ref)
                    elif type == "set":
                        scrape_set(item_ref)
                    elif type == "pet":
                        scrape_pet(item_ref)
                    else:
                        pass
                    logging.info("added {}".format(item_ref))
                    successful = True
                    time.sleep(0.85)
                except AttributeError:
                    successful = False
                    logging.debug("{} attribute error, sleeping 2 secs".format(item_ref))
                    time.sleep(2)

        # next page
        soup.find_all("li", {"class": "page-dist-1"})
        pagination_div = soup.find("div", {"class": "ak-pagination"})
        prev_button = pagination_div.find_all("li")[1]
        prev_link = str(prev_button.find("a")['href'])
        if prev_link.startswith("javascript"):
            logging.info("all elements through")
            break

        iterate_link = dofus_base_url + prev_link
    return nitems


def search_element(ankama_id, lang="en"):
    global _init_load_json_resources, _init_load_json_sets, _init_load_json_weapons, _init_load_json_equipment, _init_load_json_consumables, _init_load_json_pets
    data = None
    for item_type in item_type_choices.values():
        if item_type == "resource":
            if _init_load_json_resources is None:
                with open("{}.json".format(item_type)) as f:
                    _init_load_json_resources = json.load(f)
            data = _init_load_json_resources
        if item_type == "consumable":
            if _init_load_json_consumables is None:
                with open("{}.json".format(item_type)) as f:
                    _init_load_json_consumables = json.load(f)
            data = _init_load_json_consumables
        if item_type == "equipment":
            if _init_load_json_equipment is None:
                with open("{}.json".format(item_type)) as f:
                    _init_load_json_equipment = json.load(f)
            data = _init_load_json_equipment
        if item_type == "weapon":
            if _init_load_json_weapons is None:
                with open("{}.json".format(item_type)) as f:
                    _init_load_json_weapons = json.load(f)
            data = _init_load_json_weapons
        if item_type == "set":
            if _init_load_json_sets is None:
                with open("{}.json".format(item_type)) as f:
                    _init_load_json_sets = json.load(f)
            data = _init_load_json_sets
        if item_type == "pet":
            if _init_load_json_pets is None:
                with open("{}.json".format(item_type)) as f:
                    _init_load_json_pets = json.load(f)
            data = _init_load_json_pets

        for item in data[lang]:
            if int(item["ankama_id"]) == int(ankama_id):
                return item, item_type

    return False, False


def ensure_recipe_exists(item_element):
    # not found recipe, so insert the all recipes before posting again
    logging.info(f"ensuring recipe for {item_element['ankama_id']}.")
    if "recipe" in item_element and item_element["recipe"]:
        for recipe_element in item_element["recipe"]:

            # look in all files for this id
            found_en_element, found_item_type = search_element(str(recipe_element["item_id"]))

            if not found_en_element:
                logging.error(f"item with ankama_id {recipe_element['item_id']} could not be found in local files.")
                exit(1)

            # when found, send this specific to api first, only english one needed
            # logging.info(f"adding {found_en_element['ankama_id']} ({found_item_type})")
            url = f"{API_URL}/en/{inv_item_type_choices[found_item_type]}"
            x = requests.post(url, json=found_en_element, headers=headers)
            if x.status_code == 404:
                if "recipe" in found_en_element and found_en_element["recipe"]:
                    ensure_recipe_exists(found_en_element)
                else:
                    print(f"could not add atomic item {found_en_element['ankama_id']}.")
                    exit(1)
            elif x.status_code == 400:
                # logging.info(f"item {recipe_element['item_id']} already exists")
                pass
            elif x.status_code >= 500:
                logging.info(f"item {recipe_element['item_id']} response {x.status_code}")
                exit(1)
            else:
                # logging.info("added a recipe element")
                pass

    return True


def add_to_failed_items(item_type, lang, failed_item):
    api_fails_path = f"{item_type}_api_fails.json"

    # read json
    if os.path.isfile(api_fails_path):
        with open(api_fails_path) as f:
            items_data = json.load(f)
    else:
        items_data = dict()

    addLangArrIfNotExist(items_data, lang)

    if lang in items_data:
        # check if already inside
        for item in items_data[lang]:
            if item['ankama_id'] == failed_item['ankama_id']:
                return False

    items_data[lang].append(failed_item)

    with open(api_fails_path, 'w') as f:
        json.dump(items_data, f, indent=4, ensure_ascii=False)


def remove_from_failed_items(item_type, lang, failed_item):
    api_fails_path = f"{item_type}_api_fails.json"

    # read json
    if os.path.isfile(api_fails_path):
        with open(api_fails_path) as f:
            items_data = json.load(f)
    else:
        items_data = dict()

    addLangArrIfNotExist(items_data, lang)

    if lang in items_data:
        # check if already inside
        for i in range(len(items_data[lang])):
            if items_data[lang][i]['ankama_id'] == failed_item['ankama_id']:
                items_data[lang].pop(i)
                break
    else:
        return True

    with open(api_fails_path, 'w') as f:
        json.dump(items_data, f, indent=4, ensure_ascii=False)

    return True


def send_to_api(item_type, only_languages=False, create=None):
    # load json object
    with open("{}.json".format(item_type)) as f:
        items_data = json.load(f)

    for lang, items in items_data.items():
        if lang == "en":  # POST when english to create object
            if only_languages:
                continue

            bar = Bar(f"english base create {inv_item_type_choices[item_type]}...", max=len(items_data[lang]))
            for item_element in items:
                url = f"{API_URL}/{lang}/{inv_item_type_choices[item_type]}"
                x = requests.post(url, json=item_element, headers=headers)

                if x.status_code == 404 and not item_type == "set":  # add the missing item first
                    ensure_recipe_exists(item_element)

                # try again
                x = requests.post(url, json=item_element, headers=headers)
                if x.status_code == 404 and not item_type == "set":
                    time.sleep(0.5)
                    x = requests.post(url, json=item_element, headers=headers)
                    if x.status_code == 404:
                        logging.warning(f"ensuring recipe for {item_element['ankama_id']} did NOT work.")
                        add_to_failed_items(item_type, lang, item_element)
                elif x.ok:
                    logging.info(f"successfully added item {item_element['ankama_id']}")
                elif x.status_code == 400:
                    # logging.info(f"item {item_element['ankama_id']} already exists.")
                    pass
                else:
                    logging.error(f"unknown error for item {item_element['ankama_id']}")
                    exit(0)

                bar.next()
            bar.finish()

        else:
            if create:
                break
            bar = Bar(f"updating language '{lang}' {inv_item_type_choices[item_type]}...", max=len(items_data[lang]))
            for item_element in items:
                url = f"{API_URL}/{lang}/{inv_item_type_choices[item_type]}/{item_element['ankama_id']}/lang"
                x = requests.put(url, json=item_element, headers=headers)
                if x.status_code == 404:
                    item_en, _ = search_element(item_element['ankama_id'])
                    url = f"{API_URL}/en/{inv_item_type_choices[item_type]}"
                    x = requests.post(url, json=item_en, headers=headers)
                    if x.status_code == 404:
                        print(
                            f"item {item_element['ankama_id']} not found in english. insert en first, then other languages.")
                        exit(1)
                elif x.status_code == 400:
                    pass
                elif not x.ok:
                    logging.error(f"could not add item {item_element['ankama_id']} with API. Response from server: {x}")
                    add_to_failed_items(item_type, lang, item_element)
                else:
                    # logging.debug(f"added {item_element['name']} ({lang})")
                    pass

                bar.next()

            bar.finish()


def ankaid_exists(ankama_id, arr):
    for el in arr:
        if "ankama_id" in el and el['ankama_id'] == ankama_id:
            return True
    return False


def scrape_type(type):
    if type == "weapon":
        base_url = weapon_base_url
        result_list = _weapons
        not_found_list = _weapons_nf
    elif type == "resource":
        base_url = resources_base_url
        result_list = _resources
        not_found_list = _resources_nf
    elif type == "consumable":
        base_url = consumable_base_url
        result_list = _consumables
        not_found_list = _consumables_nf
    elif type == "equipment":
        base_url = equip_base_url
        result_list = _equipments
        not_found_list = _equipments_nf
    elif type == "set":
        base_url = set_base_url
        result_list = _sets
        not_found_list = _sets_nf
    elif type == "pet":
        base_url = pet_base_url
        result_list = _pets
        not_found_list = _pets_nf
    else:
        logging.error("type {} not known".format(type))
        return False

    print(f"started {type}...")

    # scrape to object
    nitems = scrape_list(type, base_url)

    print(f"...finished {type}")

    ngot_items = len(result_list["en"]) + len(not_found_list)

    if nitems != ngot_items:
        logging.warning(f"only got {nitems} from {ngot_items} type {type}")

    # write object to file
    with open("{}.json".format(type), 'w') as f:
        json.dump(result_list, f, indent=4, ensure_ascii=False)

    # document not found elements
    if not_found_list:
        with open("{}_404.json".format(type), 'w') as f:
            json.dump(not_found_list, f, indent=4, ensure_ascii=False)


def scrape_not_found(type):
    global _resources_nf, _consumables_nf, _weapons_nf, _equipments_nf, _sets_nf

    logging.debug(f"scraping 404s of type: {type}")

    _NF_JSON_PATH = f"{type}_404.json"
    _DATA_JSON_PATH = f"{type}.json"

    # no 404 file -> skip
    if not os.path.isfile(_NF_JSON_PATH):
        return False

    with open(_NF_JSON_PATH) as f:
        not_found = json.load(f)

    # no content -> skip
    if not not_found:
        logging.debug("no 404s in file")
        return False

    if not os.path.isfile(_DATA_JSON_PATH):
        logging.debug("data file not exists, create new dict")
        orig_data = dict()
    else:
        # load all original data already scraped
        with open(_DATA_JSON_PATH) as f:
            logging.debug(f"loading file {_DATA_JSON_PATH}")
            orig_data = json.load(f)

    _nf = None
    _elements = None
    _scrape_func = None

    if type == "weapon":

        _nf = _weapons_nf
        _elements = _weapons
        _scrape_func = scrape_weapon

    elif type == "resource":
        _nf = _resources_nf
        _elements = _resources
        _scrape_func = scrape_resource

    elif type == "consumable":
        _nf = _consumables_nf
        _elements = _consumables
        _scrape_func = scrape_consumable

    elif type == "equipment":
        _nf = _equipments_nf
        _elements = _equipments
        _scrape_func = scrape_equipment

    elif type == "set":
        _nf = _sets_nf
        _elements = _sets
        _scrape_func = scrape_set

    elif type == "pet":
        _nf = _pets_nf
        _elements = _pets
        _scrape_func = scrape_pet

    else:
        logging.error(f"type {type} not known, exit")
        return False

    _nf.clear()
    _elements.clear()

    # scrape not found
    for link in not_found:
        logging.debug(f"getting {link}")
        succ = False
        while not succ:
            try:
                _scrape_func(link)
                succ = True
            except AttributeError:
                succ = False
                time.sleep(1)
            except ConnectionError:
                _nf.append(link)
                logging.info(f"{link} added back to not found object")

    # update all elements which are still not found
    if len(_nf) > 0:
        with open(_NF_JSON_PATH, 'w') as f:
            json.dump(_nf, f, indent=4, ensure_ascii=False)
    else:
        if os.path.isfile(_NF_JSON_PATH):
            os.remove(_NF_JSON_PATH)

    # add new found elements
    for lang, el_arr in _elements.items():
        for el_el in el_arr:
            addLangArrIfNotExist(orig_data, lang)
            if not ankaid_exists(el_el['ankama_id'], orig_data[lang]):
                orig_data[lang].append(el_el)

    # write new appended items to file
    with open("{}.json".format(type), 'w') as f:
        json.dump(orig_data, f, indent=4, ensure_ascii=False)


def scrape_add_item(type, link):
    global _resources_nf, _consumables_nf, _weapons_nf, _equipments_nf, _sets_nf

    _DATA_JSON_PATH = f"{type}.json"

    if not os.path.isfile(_DATA_JSON_PATH):
        logging.debug("data file not exists, create new dict")
        orig_data = dict()
    else:
        # load all original data already scraped
        with open(_DATA_JSON_PATH) as f:
            logging.debug(f"loading file {_DATA_JSON_PATH}")
            orig_data = json.load(f)

    _nf = None
    _elements = None
    _scrape_func = None

    if type == "weapon":

        _nf = _weapons_nf
        _elements = _weapons
        _scrape_func = scrape_weapon

    elif type == "resource":
        _nf = _resources_nf
        _elements = _resources
        _scrape_func = scrape_resource

    elif type == "consumable":
        _nf = _consumables_nf
        _elements = _consumables
        _scrape_func = scrape_consumable

    elif type == "equipment":
        _nf = _equipments_nf
        _elements = _equipments
        _scrape_func = scrape_equipment

    elif type == "set":
        _nf = _sets_nf
        _elements = _sets
        _scrape_func = scrape_set

    elif type == "pet":
        _nf = _pets_nf
        _elements = _pets
        _scrape_func = scrape_pet

    else:
        logging.error(f"type {type} not known, exit")
        return False

    _nf.clear()
    _elements.clear()

    # scrape not found

    logging.debug(f"getting {link}")
    succ = False
    while not succ:
        try:
            _scrape_func(link)
            succ = True
        except AttributeError:
            succ = False
            time.sleep(1)
        except ConnectionError:
            _nf.append(link)
            logging.info(f"{link} added back to not found object")

    # update all elements which are still not found
    if len(_nf) > 0:
        print(f"not found {link}")
        exit(1)

    # add new found elements
    for lang, el_arr in _elements.items():
        for el_el in el_arr:
            addLangArrIfNotExist(orig_data, lang)
            if not ankaid_exists(el_el['ankama_id'], orig_data[lang]):
                orig_data[lang].append(el_el)
            else:
                print("already inside")

    # write new appended items to file
    with open("{}.json".format(type), 'w') as f:
        json.dump(orig_data, f, indent=4, ensure_ascii=False)


def scrape_all(args_arr=None):
    logging.debug("creating threads for item types")

    # create threads for each type
    threads = []

    if args_arr:
        for plural, singular in item_type_choices.items():
            if plural in args_arr or args_arr == []:
                threads.append(threading.Thread(target=scrape_type, args=(singular,)))
    else:
        for plural, singular in item_type_choices.items():
            threads.append(threading.Thread(target=scrape_type, args=(singular,)))

    logging.debug(f"{len(threads)} threads ready to be processed")

    # start all
    for t in threads:
        t.start()

    # wait for all finished
    for t in threads:
        t.join()

    logging.info("all jobs finished.")


def all_to_api(given_plural=None, only_languages=None, create=None):
    for plural, singular in item_type_choices.items():
        if not given_plural:
            send_to_api(singular, only_languages, create)
        else:
            if plural in given_plural:
                send_to_api(singular, only_languages, create)


def fails_to_api(only_languages=None):
    for plural, singular in item_type_choices.items():
        if os.path.isfile(f"{singular}_api_fails.json"):
            logging.debug(f"found failed items of type {singular}. starting sending this type to api.")
            return all_to_api(singular, only_languages)


def found_not_included_all_languages():
    for item_type in item_type_choices.values():
        languages_copy = languages.copy()
        with open("{}.json".format(item_type)) as f:
            data = json.load(f)

        # find difference in number of elements per language array
        nelements = dict()
        set_n = set()
        for k, v in data.items():
            nelements[k] = len(v)
            set_n.add(nelements[k])

        if len(set_n) > 1:
            # highest number of elements in which language
            sorted_element_n = {k: v for k, v in sorted(nelements.items(), key=lambda itt: itt[1])}
            logging.debug(f"found different number of elements per language {sorted_element_n}")
            highest_num_lang = list(sorted_element_n.keys())[-1]
            languages_copy.remove(
                highest_num_lang)  # remove the language with highest number of elements to substract from it

            # find differences in set of ankama_ids per language
            item_lang_sets = dict()
            len_ankaid_set = set()
            for lang in languages:
                item_lang_sets[lang] = set()
                for item in data[lang]:
                    item_lang_sets[lang].add(item["ankama_id"])

                len_ankaid_set.add(len(item_lang_sets[lang]))

            # now sure there are different ankama_ids per language
            if len(len_ankaid_set) > 1:
                print("difference in ankama_id per language found")

                # substract the set of ankama_ids of the language with most elements from the other languages
                for l in languages_copy:
                    diff_set = item_lang_sets[highest_num_lang].difference(item_lang_sets[l])
                    if len(diff_set) > 0:
                        print(f"confirmend difference between {highest_num_lang} and {l}: {diff_set}")


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="scrape dofus items")
    group = parser.add_mutually_exclusive_group()

    group.add_argument("--scrape", nargs='*', help="add a item type to scrape", type=str,
                       choices=item_type_choices.keys())
    group.add_argument("--notfound", help="only try to scrape last 404 items", action="store_true",
                       default=False)

    parser.add_argument("--api", nargs='*', help="sends the generated data to the api", type=str,
                        choices=item_type_choices.keys())
    parser.add_argument("-v", "--verbose", help="increase output verbosity", action="store_true")
    parser.add_argument("--failed", help="do api requests to failed items", action="store_true")
    parser.add_argument("--lang", help="only update non english languages", action="store_true")
    parser.add_argument("--check", help="check scraped json files for inconsistencies", action="store_true")
    parser.add_argument("--create", help="only create base item, no language updates", action="store_true")

    args = parser.parse_args()
    logging.root = logging.getLogger('dofus-scraper')

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    if args.scrape is not None:
        scrape_all(args.scrape)

        if "equipment" in args.scrape or len(args.scrape) == 0:
            scrape_add_item("resource", "/en/mmorpg/encyclopedia/resources/13741")
            scrape_add_item("resource", "/en/mmorpg/encyclopedia/resources/23965")
            scrape_add_item("resource", "/en/mmorpg/encyclopedia/resources/23957")
            scrape_add_item("resource", "/en/mmorpg/encyclopedia/resources/13737")

    if args.notfound:
        if not args.verbose:
            spinner = Spinner('Scraping ')

        for _, singular in item_type_choices.items():
            if not args.verbose:
                spinner.next()
            scrape_not_found(singular)

        if not args.verbose:
            spinner.finish()

        # check if there are still files with 404s
        nstill_nf_items = 0
        for item_type in item_type_choices:
            nf_json_path = f"{item_type_choices[item_type]}_404.json"
            if os.path.isfile(nf_json_path):
                with open(nf_json_path) as f:
                    data = json.load(f)
                    nstill_nf_items += len(data)

        if nstill_nf_items > 0:
            print(f"{nstill_nf_items} {'items' if nstill_nf_items > 1 else 'item'} still not found. try again later.")

    if args.check:
        found_not_included_all_languages()

    if args.api is not None:
        all_to_api(args.api, args.lang, args.create)

    if args.failed:
        fails_to_api()

    # clean up files
    for item_type in item_type_choices.values():
        nf_json_path = f"{item_type}_404.json"
        fails_json_path = f"{item_type}_api_fails.json"
        if os.path.isfile(nf_json_path):
            with open(nf_json_path) as f:
                data = json.load(f)
                if not data or len(data) == 0:
                    os.remove(nf_json_path)

        if os.path.isfile(fails_json_path):
            with open(fails_json_path) as f:
                data = json.load(f)
                if not data or len(data) == 0:
                    os.remove(fails_json_path)
