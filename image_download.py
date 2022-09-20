"""
This will be the code that handles going to websites and downloading images/data
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
from tqdm import tqdm
from bs4 import BeautifulSoup
from requests import ConnectTimeout, ReadTimeout


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
        return None, None
    except ReadTimeout as e:
        tqdm.write(str(e))
        return None, None


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

    for image in html_data.find_all("img", class_="img-thumbnail"):
        image_source = requests.compat.urljoin(url, image["src"])

        if "static" not in image_source:
            img_downloaded += 1
            # tqdm.write(f"\n##### Downloading: {image_source}\n")
            try:
                web_connection = requests.get(image_source, timeout=1)
                temp_loc = "/tmp/temp_image.png"
                open(temp_loc, "wb").write(web_connection.content)

                img_content_hash = create_content_hash(temp_loc)

                image_name = f"{main_trait}_{img_content_hash}"
                filepath = (
                    f"/home/jordan/Documents/datasets/ball_pythons/{main_trait}/{image_name}/"
                )
                os.makedirs(filepath, exist_ok=True)
                shutil.move(temp_loc,f"{filepath}{image_name}.png")
                with open(f"{filepath}{image_name}_metadata.json", "w") as f:
                    json.dump(python_details_dict, f)

                end_time = time.time()
                tqdm.write(f"{img_downloaded} images downloaded in {end_time-start_time} seconds\nfiles saved to {filepath}")
                return img_downloaded

            except ConnectTimeout as e:
                tqdm.write(str(e))
                return None
            except ReadTimeout as e:
                tqdm.write(str(e))
                return None


def get_python_details(html_data):
    """
    parses html data from site to find details like traits and weight, saves to file
    Args:
        html_data: html data from webpage
    Returns:
        python_details_dict: dictionary containing python image metadata
    """
    list_wanted_fields = [
        "sex",
        "traits",
        "weight",
        "dob",
        "proven_breeder",
        "price",
    ]
    raw_details = html_data.find(class_="details")

    if raw_details:
        available_info = raw_details.find_all("dt")
        available_info = [str(field).split('"')[1] for field in available_info]

        actual_info = raw_details.find_all("dd")
        actual_info = [str(value).split("dd")[1].replace("</","").replace(">","") for value in actual_info]
        
        python_details_dict = {
            "raw_details": raw_details.prettify()
        }

        traits_pattern = r"badge.*span"

        for field, value in zip(available_info, actual_info):
            if field in list_wanted_fields:
                if field == "sex":
                    value = value.split('"')[1]
                elif field == "traits":
                    trait_chunks = re.findall(traits_pattern, value)
                    trait_list = []
                    for trait in trait_chunks:
                        trait = trait.replace("span","").split('"')[-1]
                        trait_list.append(trait)
                    value = trait_list
                elif field == "price":
                    value = value.split('"')[-1]
                else:
                    pass
                python_details_dict[field] = value

        return python_details_dict
    else:
        return None


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

    if html_data:
        python_details_dict = get_python_details(html_data)

        if python_details_dict:
            num_images = download_images(url, html_data, python_details_dict)
            return num_images
        else:
            return None


def check_ad_tracking(url: str):
    with open("/home/jordan/Documents/datasets/ball_pythons/url_tracking.json", "r") as f:
        tracking_dict = json.load(f)

    if url in tracking_dict:
        return False
    else:
        return True


def update_ad_tracking(url:str, num_imgs: int):
    current_ad = {url: num_imgs}

    with open("/home/jordan/Documents/datasets/ball_pythons/url_tracking.json", "r") as f:
        tracking_dict = json.load(f)

    tracking_dict.update(current_ad)

    with open("/home/jordan/Documents/datasets/ball_pythons/url_tracking.json", "w") as f: 
        json.dump(tracking_dict, f) 


def find_ball_python_ads(url:str, num_ads: int):
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
            url = url.split("?")[0]
            url = f"{url}?page={page_num}&sort=lg"
            url = f"{url}?page={page_num}"

            html_data, history = get_website_data(url)
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
    url_list = [
        # "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/normal",
        # "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/banana",
        # "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/axanthic%20(vpi)",
        # "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/clown",
        # "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/hypo",
        # "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/pastel",
        # "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/piebald",
        # "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/pinstripe",
        # "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/yellow%20belly",
        # "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/acid",
        # "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/albino",
        # "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/axanthic%20(tsk)",
        # "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/bamboo",
        # "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/black%20pastel",
        # "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/cinnamon",
        # "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/desert%20ghost",
        # "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/enchi",
        # "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/fire",
        # "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/ghi",
        # "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/leopard",
        # "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/mojave",
        # "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/lesser",
        "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/mahogany",
        "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/coral%20glow",
        "https://www.morphmarket.com/us/c/reptiles/pythons/ball-pythons/gene/butter",
    ]

    for url in url_list:
        find_ball_python_ads(url, int(num_ads))


if __name__ == "__main__":
    # url = sys.argv[1]
    # get_ball_python_data(url)
    # find_ball_python_ads(url)
    num_ads = sys.argv[1]
    check_chosen_urls(num_ads)
