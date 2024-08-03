'''
Orchestrates the entire collection and graphing procedure in one shot.
'''

import re
import datetime
import argparse

from collect_info import collect_info
from construct_graph import construct_graph
from render_subgraph import render_subgraph

if __name__ == "__main__":
    # Pending archaeological findings that date NUS beyond the 20th century 
    valid_acad_year = re.compile(r'^(19|20)[0-9]{2}-(19|20)[0-9]{2}$', re.M)
    
    parser = argparse.ArgumentParser()
    
    parser.add_argument('--collect_data', 
        action = "store_true", 
        help = "Whether or not to collect data from NUSMods API."
    )
    parser.add_argument('--modlist', type = str,
        default = "CS1101S,ST2334",
        help = "Comma-separated module names (No spaces please!)"
    )
    parser.add_argument('--acad_year', type = str, default = None, 
            help=(
                    "Specify the academic year (AY) to retrieve data from. "
                    "Full year must be specified, without the 'AY' prefix"
                    "(e.g. '2024-2025' instead of '24-25' or 'AY24-25'). "
                    "If 'None', defaults to current AY."
                )
            )
    args = parser.parse_args()

    if not args.acad_year:
        tdy = datetime.datetime.today()
        curr_mth, curr_year = tdy.month, tdy.year
        args.acad_year = f"{curr_year}-{curr_year + 1}"

    assert valid_acad_year.match(args.acad_year), (
        "Please check your AY format and try again"
    )
    args = parser.parse_args()

    collect_info(args)
    construct_graph()
    render_subgraph(args)