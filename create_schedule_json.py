import argparse
import datetime
import json
import icalendar
import recurring_ical_events
import requests
import re
import sys
import pytz
from collections import Counter

def remove_html_tags(text):
    """Remove html tags from a string"""
    import re
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)


def fix_html(text):
    """Fix html tags"""
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')

    return text





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

    # get recurring events for the next three months
    raw_recurring_events = recurring_ical_events.of(cal).between((2022,3,14), datetime.datetime.now(pytz.utc) + datetime.timedelta(days=100))

    # get ALL events
    raw_events = [e for e in cal.walk()]

    # count UIDs occurences in raw_events
    c = Counter([e['UID'] for e in raw_events])

    # non-recurring events without constraint + recurring events 3 months into to the future
    raw_events = [e for e in raw_events if c[e['UID']] == 1] + [e for e in raw_recurring_events if c[e['UID']] > 1]


    for event in raw_events:

        # clean description
        description = event.get('description')

        if description is None:
            description = ''

        description = re.sub('Join with Google Meet.*', '', description, flags=re.IGNORECASE|re.MULTILINE|re.DOTALL)
        description = re.sub('^[.]+(.|[\n\r\s])*skype(.|[\n\r\s])*', '', description, flags=re.IGNORECASE|re.MULTILINE)
        description = re.sub('^[.]+(.|[\n\r\s])*google(.|[\n\r\s])*', '', description, flags=re.IGNORECASE|re.MULTILINE)
        description = re.sub('^[.]+(.|[\n\r\s])*Google Meet(.|[\n\r\s])*', '', description, flags=re.IGNORECASE|re.MULTILINE)
        description = re.sub('^.*Google Meet(.|[\n\r\s])*', '', description, flags=re.IGNORECASE|re.MULTILINE)
        description = re.sub('^.*meet\.(.|[\n\r\s])*', '', description, flags=re.IGNORECASE|re.MULTILINE)
        description = re.sub('^.*skype\.(.|[\n\r\s])*', '', description, flags=re.IGNORECASE|re.MULTILINE)
        description = re.sub('^.*google\.(.|[\n\r\s])*', '', description, flags=re.IGNORECASE|re.MULTILINE)
        description = re.sub('Dieser Termin enthält einen Videoanruf.*', '', description, flags=re.IGNORECASE|re.MULTILINE|re.DOTALL)
        description = re.sub('Teilnehmen.*', '', description, flags=re.IGNORECASE|re.MULTILINE|re.DOTALL)
        description = re.sub('This event contains.*', '', description, flags=re.IGNORECASE|re.MULTILINE|re.DOTALL)
        description = re.sub('This event has.*', '', description, flags=re.IGNORECASE|re.MULTILINE|re.DOTALL)

        description = fix_html(description)

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

        try:
            startDateUK =  event.get('dtstart').dt.astimezone(tz=pytz.timezone('Europe/London'))
        except: # all day events
            startDateUK = datetime.datetime.combine(event.get('dtstart').dt, datetime.datetime.min.time())
            # Now the date can be localized
            startDateUK = pytz.timezone("Europe/London").localize(startDateUK, is_dst=None)

        try:
            endDateUK =  event.get('dtend').dt.astimezone(tz=pytz.timezone('Europe/London'))

        except: # all day events
            endDateUK = datetime.datetime.combine(event.get('dtend').dt, datetime.datetime.min.time())
            # Now the date can be localized
            endDateUK = pytz.timezone("Europe/London").localize(endDateUK, is_dst=None)

            if endDateUK.date() != startDateUK.date():
                endDateUK = endDateUK - datetime.timedelta(seconds=1)
                if endDateUK.date() != startDateUK.date():
                    print('Warning: multi day events not yet supported')
                    pass

        new_event ={
        'uid': event.get('uid'),
        'startTimestamp': event.get('dtstart').dt.isoformat(),
        'endTimestamp': event.get('dtend').dt.isoformat(),
        'dateUK': startDateUK.strftime('%Y-%m-%d'),
        'startTimeUK': startDateUK.strftime('%H:%M'),
        'endTimeUK': endDateUK.strftime('%H:%M'),
        'recurring': c[event.get('uid')] > 1,
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