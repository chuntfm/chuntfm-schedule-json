import argparse
import json
import icalendar
import requests
import re
import sys
import pytz

def remove_html_tags(text):
    """Remove html tags from a string"""
    import re
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)



def main(debug = False):

    parser = argparse.ArgumentParser()
    parser.add_argument('-i','--input', required=not debug, help='Input .ics file (can be url)')
    parser.add_argument('-o', '--output', required=not debug, help='Output .json file')
    args = parser.parse_args()

    ## debug
    if sys.gettrace() is not None:
        args.input = 'https://calendar.google.com/calendar/ical/chuntfm%40gmail.com/public/basic.ics'
        args.output = 'schedule.json'


    if args.input.startswith('http'):
        cal = icalendar.Calendar.from_ical(requests.get(args.input).text)
    else:
        cal = icalendar.Calendar.from_ical(open(args.input, 'rb').read())

    events = []

    for event in cal.walk('vevent'):



        # clean description
        description = event.get('description')

        if description is None:
            description = ''

        description = re.sub('Dieser Termin enthält einen Videoanruf.*', '', description, flags=re.IGNORECASE|re.MULTILINE|re.DOTALL)
        description = re.sub('Teilnehmen.*', '', description, flags=re.IGNORECASE|re.MULTILINE|re.DOTALL)
        description = re.sub('This event contains.*', '', description, flags=re.IGNORECASE|re.MULTILINE|re.DOTALL)
        description = re.sub('This event has.*', '', description, flags=re.IGNORECASE|re.MULTILINE|re.DOTALL)


        try:
            partstat = event.get('attendee').params.get('PARTSTAT')
        except:
            partstat = None

        if partstat is not None:
            if partstat == 'DECLINED':
                continue
            elif partstat == 'NEEDS-ACTION':
                description = remove_html_tags(description)

        # parse possible json in description and add as tags
        description_json = {}

        if '{' in description and '}' in description:

            front, back = description.split('{', 1)
            json_string, end = back.split('}', 1)

            description = end

            json_string = remove_html_tags(json_string)

            json_string = json_string.replace("'", '"')

            try:
                description_json = json.loads('{' + json_string + '}')
            except:
                pass


        new_event ={
            'uid': event.get('uid'),
            'startTimestamp': event.get('dtstart').dt.isoformat(),
            'endTimestamp': event.get('dtend').dt.isoformat(),
            'dateUK': event.get('dtstart').dt.astimezone(tz=pytz.timezone('Europe/London')).strftime('%Y-%m-%d'),
            'startTimeUK': event.get('dtstart').dt.astimezone(tz=pytz.timezone('Europe/London')).strftime('%H:%M'),
            'endTimeUK': event.get('dtend').dt.astimezone(tz=pytz.timezone('Europe/London')).strftime('%H:%M'),
            'title': event.get('summary', '').strip(),
            'description': description.strip(),
            'location': event.get('location'),
            'lastModified': event.get('last-modified').dt.isoformat(),
            'status': event.get('status'),
            'invitationStatus': partstat,
            'url': event.get('url'),
        }

        new_event.update(description_json)

        events.append(new_event)

    # sort by startTimestamp descending
    events = sorted(events, key=lambda k: k['startTimestamp'], reverse=False)

    with open(args.output, 'w') as f:
        json.dump(events, f, indent=4)

if __name__ == '__main__':
    if sys.gettrace() is not None:
        main(debug=True)
    else:
        main()