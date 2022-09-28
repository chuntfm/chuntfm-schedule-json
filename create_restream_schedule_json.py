import argparse
import json
import icalendar
import requests
import re
import sys
import pytz




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

        restream['current'] = dict()

        try:

            show_title = current['song']
            show_date = None

            title_re = re.search('(.*?)@*\s*(chunt\s*fm)\s*(.*)', show_title.strip(), re.IGNORECASE)

            if title_re is not None:
                show_title = title_re.group(1)
                show_date = title_re.group(3)

            restream['current']['show_title'] = show_title.strip()
            restream['current']['description'] = None
            restream['current']['show_date'] = show_date
            restream['current']['on_air_timestamp'] = current['on_air_timestamp']

        except:
            pass


    if args.input_next is not None:
        if args.input_next.startswith('http'):
            next = requests.get(args.input_next).json()
        else:
            next = json.load(open(args.input_next, 'rb'))

        restream['next'] = dict()
        
        try:

            restream['next']['show_title'] = next['song']
            restream['next']['description'] = None

        except:

            pass


    # write out json file
    with open(args.output, 'w') as f:
        json.dump(restream, f, indent=4)

if __name__ == '__main__':
    if sys.gettrace() is not None:
        main(debug=True)
    else:
        main()