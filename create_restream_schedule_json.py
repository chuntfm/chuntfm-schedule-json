import argparse
import json
import icalendar
import requests
import re
import sys
import pytz


def parse_title(stream_dict):
    """
    Parse title
    :param title:
    :return: dict with show_title, show_date, description, url, slug
    """

    restream = {}

    show_title = None
    show_date = None
    show_url = None
    show_slug = None


    try:

        # try to split along commas
        title_parts = stream_dict['song'].split(',')
        if len(title_parts) == 3:
            show_title = title_parts[0]
            show_url = title_parts[1]
            show_slug = title_parts[2]
        else:
            # split between title and url
            title_parts = re.split(',\s*(?=http|null)', stream_dict['song'])
            if len(title_parts) > 1:
                show_title = title_parts[0]

                re.split(',\s*(?=null|[a-z]+)', title_parts[1])

                if len(title_parts) > 1:
                    show_url = title_parts[0]
                    show_slug = title_parts[1]

            else:
                show_title = stream_dict['song']

        # parse title for date

        title_re = re.search('(.*?)@*\s*(chunt\s*fm)\s*(.*)', show_title.strip(), re.IGNORECASE)

        if title_re is not None:
            show_title = title_re.group(1)
            show_date = title_re.group(3)


        restream['on_air_timestamp'] = stream_dict['on_air_timestamp']

    except:
        pass

    restream['show_title'] = show_title.strip()
    restream['description'] = None
    restream['show_date'] = show_date
    restream['show_url'] = show_url
    restream['show_slug'] = show_slug

    return restream

def main(debug = False):

    parser = argparse.ArgumentParser()
    parser.add_argument('-icur','--input-current', required=not debug, default= None, help='Input .json file (can be url)')
    parser.add_argument('-inext','--input-next', required=False, default=None, help='Input .json file (can be url)')
    parser.add_argument('-o', '--output', default='./restream.json', required=not debug, help='Output .json file')

    args = parser.parse_args()

    ## debug
    if sys.gettrace() is not None:
        args.input_current = 'http://116.203.52.102/cfm-fallback/current.json'
        args.input_next = 'http://116.203.52.102/cfm-fallback/next.json'


    restream = {'current': None,
                'next': None}

    if args.input_current is not None:
        if args.input_current.startswith('http'):
            current = requests.get(args.input_current).json()
        else:
            current = json.load(open(args.input_current, 'rb'))

        try:
            restream['current'] = parse_title(current)
        except:
            restream['current'] = {}



    if args.input_next is not None:
        if args.input_next.startswith('http'):
            next = requests.get(args.input_next).json()
        else:
            next = json.load(open(args.input_next, 'rb'))

        restream['next'] = dict()

        try:

            restream['next'] = parse_title(current)

        except:

            restream['next'] = {}


    # write out json file
    with open(args.output, 'w') as f:
        json.dump(restream, f, indent=4)

if __name__ == '__main__':
    if sys.gettrace() is not None:
        main(debug=True)
    else:
        main()