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
from bs4 import BeautifulSoup


def get_website_data(url: str):
    """
    collects html information from website
    Args:
        url: website url
    """
    print(f"querying {url}")
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; CrOS x86_64 12871.102.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.141 Safari/537.36"
    }
    html_data = requests.get(url, headers=headers, timeout=2)
    print("finished query")
    soup = BeautifulSoup(html_data.text, "html.parser")
    return soup


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


def download_images(html_data, python_details_dict: dict):
    """
    finds and downloads images from url
    Args:
        url: website url
        traits: supposed traits of images being downloaded
    """
    start_time = time.time()
    img_downloaded = 0
    if len(python_details_dict["traits"]) == 1:
        main_trait = python_details_dict["traits"][0]
    else:
        main_trait = "combo"

    for image in html_data.find_all("img"):
        image_source = requests.compat.urljoin(url, image["src"])

        if "static" not in image_source:
            img_downloaded += 1
            print(f"\n##### Downloading: {image_source}\n")
            web_connection = requests.get(image_source, timeout=2)

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
    print(f"{img_downloaded} images downloaded in {end_time-start_time} seconds\nfiles saved to {filepath}")


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


def get_ball_python_data(url: str):
    """
    handles functions that scrape a website url
    Args:
        url: website url to scrape
    """
    web_start = time.time()
    html_data = get_website_data(url)
    web_stop = time.time()
    print(f"Website queried in {web_stop - web_start} seconds")

    python_details_dict = get_python_details(html_data)

    download_images(html_data, python_details_dict)


def find_ball_python_ads(url:str):
    """
    function that looks at webpage earlier in hierarchy to find subpages
    Args:
        url: webpage with ads to look at
    """


if __name__ == "__main__":
    url = sys.argv[1]
    # get_ball_python_data(url)
    data = get_website_data(url)
    print(data)
