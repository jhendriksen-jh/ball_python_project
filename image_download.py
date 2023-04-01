"""
This will be the code that handles going to websites and downloading images/data
As of 3/12/2023 the website has been updated and this script no longer works 
 - links for ads are deeply nested and aren't easily parsed out anymore
"""

import os
import re
import sys
import json
import time
import uuid
import shutil
import hashlib
import requests
import random

from tqdm import tqdm
from retry import retry
from bs4 import BeautifulSoup
from requests import ConnectTimeout, ReadTimeout, ConnectionError


def get_website_data(url: str):
    """
    collects html information from website
    Args:
        url: website url
    """
    tqdm.write(f"querying {url}")
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; CrOS x86_64 12871.102.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.141 Safari/537.36"
    }
    try:
        html_data = requests.get(url, headers=headers, timeout=1)
        history = html_data.history
        soup = BeautifulSoup(html_data.text, "html.parser")
        return soup, history
    except ConnectTimeout as e:
        tqdm.write(str(e))
        return "CT", None
    except ReadTimeout as e:
        tqdm.write(str(e))
        return "RT", None


def create_content_hash(filepath: str):
    """
    creates md5 hash of image - unique to content
    Args:
        filepath: location of file to be hashed
    """
    md5_hash = hashlib.md5()

    a_file = open(filepath, "rb")
    content = a_file.read()
    md5_hash.update(content)

    digest = md5_hash.hexdigest()
    return digest


def download_images(url: str, html_data, python_details_dict: dict):
    """
    finds and downloads images from url
    Args:
        url: website url
        html_data: all html data
        python_details_dict: metadata details of python from ad
    """
    start_time = time.time()
    img_downloaded = 0
    if len(python_details_dict["traits"]) == 1:
        main_trait = python_details_dict["traits"][0]
    else:
        main_trait = "combo"

    a_matches = html_data.find_all("a")
    href_list = [i for i in a_matches if i.get("itemprop") == "contentUrl"]
    add_id = f"{main_trait}_{uuid.uuid4().hex}"
    for image_ref in href_list:
        image_source = requests.compat.urljoin(url, image_ref["href"])

        if "static" not in image_source:
            img_downloaded += 1
            # tqdm.write(f"\n##### Downloading: {image_source}\n")
            try:
                # images now have source separated from img tag
                # look for href with "/media/raw_images"
                web_connection = requests.get(image_source, timeout=1)
                temp_loc = "/tmp/temp_image.png"
                open(temp_loc, "wb").write(web_connection.content)

                img_content_hash = create_content_hash(temp_loc)

                image_name = f"{main_trait}_{img_content_hash}"
                filepath = (
                    f"/home/jordan/github/datasets/ball_pythons/{main_trait}/{add_id}/"
                )
                os.makedirs(filepath, exist_ok=True)
                shutil.move(temp_loc, f"{filepath}{image_name}.png")
                with open(f"{filepath}{image_name}_metadata.json", "w") as f:
                    json.dump(python_details_dict, f)

            except ConnectTimeout as e:
                tqdm.write(str(e))
                return None
            except ReadTimeout as e:
                tqdm.write(str(e))
                return None
            except ConnectionError as e:
                tqdm.write(str(e))
                return None
    if img_downloaded:
        end_time = time.time()
        tqdm.write(
            f"{img_downloaded} images downloaded in {end_time-start_time} seconds\nfiles saved to {filepath}"
        )
    return img_downloaded


def get_python_details(html_data):
    """
    parses html data from site to find details like traits and weight, saves to file
    Args:
        html_data: html data from webpage
    Returns:
        python_details_dict: dictionary containing python image metadata
    """
    dict_wanted_fields = {
        "Sex:": "sex",
        "Traits:": "traits",
        "Weight:": "weight",
        "Birth:": "dob",
        # "proven_breeder",
        # "price",
    }

    if html_data != "RT" and html_data != "CT":
        raw_details = html_data.find(class_="snake-info-card")
    else:
        return None

    if raw_details and "Ball Python" in str(raw_details):
        info_pattern = r">(.*?)<\/span"
        available_info = raw_details.find_all("div", class_="snake-info-card-row")
        actual_info = {}
        for field in available_info:
            field_str = str(field)
            info_match = re.search(info_pattern, field_str)
            if info_match:
                div_field = info_match.group(1).strip()
                actual_key = dict_wanted_fields.get(div_field)
                if actual_key is not None:
                    actual_info[actual_key] = field_str
            elif "snake-price" in field_str:
                actual_info["price"] = field_str
        # actual_info = raw_details.find_all("dd")
        # actual_info = [str(value).split("dd")[1].replace("</","").replace(">","") for value in actual_info]

        python_details_dict = {"raw_details": raw_details.prettify()}

        traits_pattern = r'">(.*?)</span>'

        for field, raw_div in actual_info.items():
            if field == "sex":
                search_pattern = r'alt="(.*?)" class'
                field_match = re.search(search_pattern, raw_div)
                value = field_match.group(1).strip()
            elif field == "traits":
                trait_chunks = re.findall(traits_pattern, raw_div)
                trait_list = [
                    trait.strip()
                    for trait in trait_chunks
                    if "Trait" not in trait.strip()
                ]
                value = trait_list
            elif field == "price":
                search_pattern = r'">(.*?)</h1>'
                field_match = re.search(search_pattern, raw_div)
                value = field_match.group(1).strip()
            elif field == "dob" or field == "weight":
                value = raw_div.split('">')[-1].split("<")[0]
            python_details_dict[field] = value

        if python_details_dict.get("traits") is not None:
            return python_details_dict
        else:
            return None
    elif raw_details and "Ball Python" not in raw_details:
        tqdm.write("This is not a ball python ad")
        return None
    else:
        return None


@retry(tries=3, delay=0.5, backoff=2)
def get_ball_python_data(url: str):
    """
    handles functions that scrape a website url
    Args:
        url: website url to scrape
    """
    web_start = time.time()
    html_data, history = get_website_data(url)
    web_stop = time.time()
    tqdm.write(f"Website queried in {web_stop - web_start} seconds")
    # with open("./test_ad.html", "w") as f:
    #     f.write(str(html_data.prettify()))

    if html_data:
        python_details_dict = get_python_details(html_data)

        if python_details_dict:
            num_images = download_images(url, html_data, python_details_dict)
            return num_images
        else:
            return None


def check_ad_tracking(url: str):
    with open("/home/jordan/github/datasets/ball_pythons/url_tracking.json", "r") as f:
        tracking_dict = json.load(f)

    if url in tracking_dict:
        return False
    else:
        return True


def update_ad_tracking(url: str, num_imgs: int):
    current_ad = {url: num_imgs}

    with open("/home/jordan/github/datasets/ball_pythons/url_tracking.json", "r") as f:
        tracking_dict = json.load(f)

    tracking_dict.update(current_ad)

    with open("/home/jordan/github/datasets/ball_pythons/url_tracking.json", "w") as f:
        json.dump(tracking_dict, f)


def find_ball_python_ads(url: str, num_ads: int):
    """
    function that looks at webpage earlier in hierarchy to find subpages
    Args:
        url: webpage with ads to look at
        num_ads: number of adds to look at
    """
    more_pages = True
    page_num = 1
    num_ads_viewed = 0
    with tqdm(total=num_ads, desc="total adds for morph - ") as pbar:
        while more_pages:
            initial_connection = False
            url = url.split("?")[0]
            url = f"{url}?page={page_num}&ordering=traits"
            # url = f"{url}?page={page_num}"
            while not initial_connection:
                html_data, history = get_website_data(url)
                if html_data != "RT" and html_data != "CT":
                    initial_connection = True
            if history:
                break
            if not html_data:
                break

            ads_list = []
            not_ads_list = []
            for link in html_data.find_all("a", href=True):
                link_href = link["href"]
                try:
                    last_int = int(link_href[-1])
                except:
                    last_int = None
                if "ball-pythons/" in link_href and last_int is not None:
                    ad_link = requests.compat.urljoin(url, link_href)
                    ads_list.append(ad_link)
                else:
                    not_ads_list.append(link_href)

            for ad_url in tqdm(ads_list, desc="ads in page - "):
                should_ingest = check_ad_tracking(ad_url)
                if should_ingest:
                    try:
                        num_images = get_ball_python_data(ad_url)
                        if num_images:
                            update_ad_tracking(ad_url, num_images)
                        else:
                            num_images = 0
                            update_ad_tracking(ad_url, num_images)
                        num_ads_viewed += 1
                        pbar.update(1)
                    except ConnectTimeout as e:
                        tqdm.write(str(e))
                        continue
                    except ReadTimeout as e:
                        tqdm.write(str(e))
                        continue

                if num_ads_viewed >= num_ads:
                    break

            if num_ads_viewed >= num_ads:
                break

            page_num += 1


def check_chosen_urls(num_ads: int):
    """
    looks at num_ads for each url in list
    Args:
        num_ads: number of ads to look at per url
    """
    # url_list = [
    #     "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/normal",
    #     "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/banana",
    #     "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/axanthic%20(vpi)",
    #     "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/clown",
    #     "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/hypo",
    #     "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/pastel",
    #     "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/piebald",
    #     "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/pinstripe",
    #     "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/yellow%20belly",
    #     "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/acid",
    #     "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/albino",
    #     "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/axanthic%20(tsk)",
    #     "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/bamboo",
    #     "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/black%20pastel",
    #     "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/cinnamon",
    #     "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/desert%20ghost",
    #     "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/enchi",
    #     "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/fire",c
    #     "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/ghi",
    #     "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/leopard",
    #     "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/mojave",
    #     "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/lesser",
    #     "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/mahogany",
    #     "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/coral%20glow",
    #     "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/butter",
    # ]
    url_list = [
        "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons?state=for_sale"
    ]

    for url in url_list:
        find_ball_python_ads(url, int(num_ads))


def check_random_ad_url(num_ads):
    """
    creates random URL to check for images
    """
    base_url = "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/"

    total_imgs = 0
    counter = 0
    checked = 0
    start_time = time.time()
    rand_list = []
    rand_list.extend(list(range(999999, 2000000)))
    rand_list.extend(list(range(1200000, 1650000)))
    rand_list.extend(list(range(1400000, 1600000)))
    with tqdm(total=num_ads, desc="total adds - ") as pbar:
        while counter < num_ads:
            checked += 1
            rand_num = random.sample(rand_list, 1)[0]
            ad_url = base_url + f"{rand_num}"

            should_ingest = check_ad_tracking(ad_url)
            if should_ingest:
                try:
                    num_images = get_ball_python_data(ad_url)

                    if num_images:
                        update_ad_tracking(ad_url, num_images)
                        counter += 1
                        total_imgs += num_images
                        pbar.update(1)
                    else:
                        num_images = 0

                    sleep_time = random.randint(2,7)
                    time.sleep(sleep_time)

                except ConnectTimeout as e:
                    tqdm.write(str(e))
                    continue
                except ReadTimeout as e:
                    tqdm.write(str(e))
                    continue
            else:
                tqdm.write("Ad previously processed")

    print(
        f"{counter} ads processed and {checked} urls checked in {time.time() - start_time} seconds with {total_imgs} images downloaded"
    )


if __name__ == "__main__":
    # url = sys.argv[1]
    # get_ball_python_data(url)
    # find_ball_python_ads(url)
    num_ads = int(sys.argv[1])
    check_random_ad_url(num_ads)
