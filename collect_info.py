'''
A simple script which collects information about NUSMods in one AY.

Information may be outdated because sadness :(

But it should capture all the prerequisites that NUSMods has for that AY.
'''

import requests
import time
import json
import argparse
import re

import tqdm

NUSMODS_API = "https://api.nusmods.com/v2/"

def call_json_api(url, max_retries = 3):
    for i in range(max_retries):
        api_json = requests.get(url, headers = {"Accept": "application/json"})
        if api_json.status_code == 200:
            return json.loads(api_json.content)
        else:
            # Give the request another go before barfing.
            time.sleep(0.1)
    raise Exception("This request didn't go through to NUSMods. Try again later?")

def collect_info(args):

    # Load the module list and cache it
    # module_list_request = requests.get(
    #                     f"{NUSMODS_API}/{args.acad_year}/moduleList.json", 
    #                     headers = {"Accept": "application/json"}
    #                 )
    # # print(module_list_request.content)
    # module_list_json = json.loads(module_list_request.content)
    module_list_json = call_json_api(
                            f"{NUSMODS_API}/{args.acad_year}/moduleList.json"
                        )

    with open("modlist.json", "w") as f:
        f.write(json.dumps(module_list_json))

    # Using the module list, dig out the following information from each module:
    # - Module Credits
    # - Prereq Tree
    # - Module Name
    with open("modlist.json", "r") as f:
        module_list_json = json.loads(f.read())
        module_list = [
                        module_json["moduleCode"] 
                        for module_json in module_list_json
                    ] 

    all_modules_dict = {}
    for module_code in tqdm.tqdm(module_list):
        module_info_dict = {}
        # module_info_request = requests.get(
        #                     f"{NUSMODS_API}/{args.acad_year}/modules/{module_code}.json", 
        #                     headers = {"Accept": "application/json"}
        #                 )
        # detailed_module_json = json.loads(module_info_request.content)
        detailed_module_json = call_json_api(
                                f"{NUSMODS_API}/{args.acad_year}/modules/{module_code}.json"
                            )
        for key in ["moduleCredit", "prereqTree", "fulfilRequirements", "title"]:
            if key in detailed_module_json:
                module_info_dict[key] = detailed_module_json[key]
        
        all_modules_dict[module_code] = module_info_dict
        
    # Checkpoint all the information we just collected.
    with open("mod_info.json", "w") as f:
        f.write(json.dumps(all_modules_dict))

if __name__ == "__main__":
    # Pending archaeological findings that date NUS beyond the 20th century 
    valid_acad_year = re.compile(r'^(19|20)[0-9]{2}-(19|20)[0-9]{2}$', re.M)
    parser = argparse.ArgumentParser()
    parser.add_argument('--acad_year', type="str", default=None, 
            help=(
                    "Specify the academic year (AY) to retrieve data from. "
                    "Full year must be specified, without the 'AY' prefix"
                    "(e.g. '2024-2025' instead of '24-25' or 'AY24-25'). "
                    "If 'None', defaults to current AY."
                )
            )

    args = parser.parse_args()

    assert valid_acad_year.match(args.acad_year), (
        "Please check your AY format and try again"
    )
    collect_info(args)