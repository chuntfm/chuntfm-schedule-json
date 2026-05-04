import argparse
import datetime
import json
import icalendar
import recurring_ical_events
import requests
import re
import pytz
from collections import Counter
import sqlite3
import pandas as pd
import json
import os
import uuid
import hashlib
import hmac


def remove_html_tags(text):
    """Remove html tags from a string"""
    import re

    clean = re.compile("<.*?>")
    return re.sub(clean, "", text)


def fix_html(text):
    """Fix html tags"""
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")

    return text


def event_to_ical(event):
    """
    Convert an event dictionary to an icalendar Event object
    :param event: dictionary with event information
    :return: icalendar Event object
    """

    ical_event = icalendar.Event()

    ical_event.add("uid", event["uid"])
    ical_event.add("summary", event["title"])
    ical_event.add(
        "dtstart", datetime.datetime.fromisoformat(event["startTimestampUTC"])
    )
    ical_event.add("dtend", datetime.datetime.fromisoformat(event["endTimestampUTC"]))
    ical_event.add("description", event["description"])
    ical_event.add(
        "last-modified",
        (
            datetime.datetime.fromisoformat(event["lastModified"])
            if event["lastModified"] is not None
            else None
        ),
    )
    ical_event.add("status", event["status"])
    ical_event.add(
        "url",
        (
            event.get("url", "https://www.chunt.org")
            if event.get("url") is not None
            else "https://www.chunt.org"
        ),
    )

    return ical_event


def dict_to_ical(schedule):

    cal = icalendar.Calendar()

    cal.add("prodid", "-//ChuntFM//Schedule//EN")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("x-wr-calname", "ChuntFM Schedule")
    cal.add("x-wr-timezone", "UTC")
    cal.add("refresh-interval;value=duration", "PT1H")
    cal.add("x-published-ttl", "PT1H")

    for event in schedule:
        cal.add_component(event_to_ical(event))

    return cal


def dict_to_sqlite(schedule, output_file):

    # Create simplified table with id, start, stop, and data columns
    simplified_data = []
    
    for event in schedule:
        simplified_data.append({
            'id': event.get('uid'),
            'start': event.get('startTimestampUTC'),
            'stop': event.get('endTimestampUTC'),
            'data': json.dumps(event)
        })
    
    df = pd.DataFrame(simplified_data)

    # write to disk
    df.to_sql(
        "schedule", sqlite3.connect(output_file), if_exists="replace", index=False
    )


def main(args):

    if args.input.startswith("http"):
        cal = icalendar.Calendar.from_ical(requests.get(args.input).text)
    else:
        cal = icalendar.Calendar.from_ical(open(args.input, "rb").read())

    events = []

    # get recurring events for the next three months
    raw_recurring_events = recurring_ical_events.of(cal, components=["VEVENT"]).between(
        (2022, 3, 14), datetime.datetime.now(pytz.utc) + datetime.timedelta(days=31)
    )

    # grouped by uid, add a running id to the uid

    # get ALL events
    raw_events = [e for e in cal.walk()]

    # count UIDs occurences in raw_events
    c = Counter([e["UID"] for e in raw_recurring_events if "UID" in e.keys()])

    # count modified uids
    c_uid_mod = Counter()

    # Non-recurring events without those already in recurring events + recurring events
    raw_events = [e for e in raw_events if "UID" in e.keys() and c[e["UID"]] == 0] + [
        e for e in raw_recurring_events if "UID" in e.keys() and c[e["UID"]] > 0
    ]

    for event in raw_events:

        try:
            # check for EXDATE rules in recurring events
            if "EXDATE" in event.keys():
                if isinstance(event["EXDATE"], icalendar.prop.vDDDLists):
                    exdates = [d.dt for d in event["EXDATE"].dts]
                elif isinstance(event["EXDATE"], list):
                    exdates = [d.dts[0].dt for d in event["EXDATE"]]

                if event["DTSTART"].dt in exdates:
                    continue

        except:
            pass

        # check whether event is actually an event
        if event.name != "VEVENT":
            continue

        # clean description
        description = event.get("description")

        if description is None:
            description = ""

        description = re.sub(
            "Join with Google Meet.*",
            "",
            description,
            flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
        )
        description = re.sub(
            "^[.]+(.|[\n\r\s])*skype(.|[\n\r\s])*",
            "",
            description,
            flags=re.IGNORECASE | re.MULTILINE,
        )
        description = re.sub(
            "^[.]+(.|[\n\r\s])*google(.|[\n\r\s])*",
            "",
            description,
            flags=re.IGNORECASE | re.MULTILINE,
        )
        description = re.sub(
            "^[.]+(.|[\n\r\s])*Google Meet(.|[\n\r\s])*",
            "",
            description,
            flags=re.IGNORECASE | re.MULTILINE,
        )
        description = re.sub(
            "^.*Google Meet(.|[\n\r\s])*",
            "",
            description,
            flags=re.IGNORECASE | re.MULTILINE,
        )
        description = re.sub(
            "^.*meet\.(.|[\n\r\s])*",
            "",
            description,
            flags=re.IGNORECASE | re.MULTILINE,
        )
        description = re.sub(
            "^.*skype\.(.|[\n\r\s])*",
            "",
            description,
            flags=re.IGNORECASE | re.MULTILINE,
        )
        description = re.sub(
            "^.*google\.(.|[\n\r\s])*",
            "",
            description,
            flags=re.IGNORECASE | re.MULTILINE,
        )
        description = re.sub(
            "Dieser Termin enthält einen Videoanruf.*",
            "",
            description,
            flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
        )
        description = re.sub(
            "Teilnehmen.*",
            "",
            description,
            flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
        )
        description = re.sub(
            "This event contains.*",
            "",
            description,
            flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
        )
        description = re.sub(
            "This event has.*",
            "",
            description,
            flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
        )

        description = fix_html(description)

        try:
            partstat = event.get("attendee").params.get("PARTSTAT")
        except:
            partstat = None

        if partstat is not None:
            if partstat == "DECLINED":
                continue
            elif partstat == "NEEDS-ACTION":
                description = remove_html_tags(description)

        # parse possible json in description and add as tags
        description_json = {}

        if "{" in description and "}" in description:

            front, back = description.split("{", 1)
            json_string, end = back.split("}", 1)

            description = end

            json_string = remove_html_tags(json_string)

            json_string = json_string.replace("'", '"')

            try:
                description_json = json.loads("{" + json_string + "}")
            except:
                pass

        try:
            startTimestampUTC = event.get("dtstart").dt.astimezone(pytz.utc)
            startDateUK = event.get("dtstart").dt.astimezone(
                tz=pytz.timezone("Europe/London")
            )
        except:  # all day events
            try:
                startTimestampUTC = datetime.datetime.combine(
                    event.get("dtstart").dt, datetime.datetime.min.time()
                )
                startTimestampUTC = pytz.timezone("UTC").localize(startTimestampUTC)  #

                startDateUK = datetime.datetime.combine(
                    event.get("dtstart").dt, datetime.datetime.min.time()
                )
                startDateUK = pytz.timezone("Europe/London").localize(
                    startDateUK, is_dst=None
                )
            except Exception as e:
                print("Error parsing event: " + event.get("uid"))
                print(e)
                continue
            # Now the date can be localized

        try:
            endTimestampUTC = event.get("dtend").dt.astimezone(pytz.utc)
            endDateUK = event.get("dtend").dt.astimezone(
                tz=pytz.timezone("Europe/London")
            )

        except:  # all day events

            try:

                endTimestampUTC = datetime.datetime.combine(
                    event.get("dtend").dt, datetime.datetime.min.time()
                )
                endTimestampUTC = pytz.timezone("UTC").localize(endTimestampUTC)

                if endTimestampUTC.date() != endTimestampUTC.date():
                    endTimestampUTC = endTimestampUTC - datetime.timedelta(seconds=1)
                    if endTimestampUTC.date() != endTimestampUTC.date():
                        print("Warning: multi day events not yet supported")
                        pass

                endDateUK = datetime.datetime.combine(
                    event.get("dtend").dt, datetime.datetime.min.time()
                )
                # Now the date can be localized
                endDateUK = pytz.timezone("Europe/London").localize(
                    endDateUK, is_dst=None
                )

                if endDateUK.date() != startDateUK.date():
                    endDateUK = endDateUK - datetime.timedelta(seconds=1)
                    if endDateUK.date() != startDateUK.date():
                        print("Warning: multi day events not yet supported")
                        pass
            except Exception as e:
                print("Error parsing event: " + event.get("uid"))
                print(e)
                continue

        """if event.get('uid') in c.keys() and c[event.get('uid')] > 1:

            c_uid_mod.update([event.get('uid')])
            uid = event.get('uid') + '-' + str(c_uid_mod[event.get('uid')])

        else:
            uid = event.get('uid')"""
        # Keep the original UID here; we'll assign numeric suffixes after
        # we've collected and sorted all events so numbering is stable.
        uid = event.get("uid")

        # Extract organizer information
        organizer = None
        if event.get("organizer"):
            try:
                organizer_prop = event.get("organizer")
                # Extract and clean email from organizer property
                organizer_email = str(organizer_prop).replace("MAILTO:", "").replace("mailto:", "").strip().lower()
                
                if organizer_email:
                    if args.plaintext_organizer:
                        organizer = organizer_email
                    elif args.organizer_key:
                        # Use HMAC-SHA256 with user-provided key
                        organizer = hmac.new(
                            args.organizer_key.encode(), 
                            organizer_email.encode(), 
                            hashlib.sha256
                        ).hexdigest()
                    else:
                        organizer = None  # No hashing without key for security
            except Exception:
                organizer = None

        try:
            new_event = {
                "uid": uid,
                "startTimestampUTC": startTimestampUTC.isoformat(),
                "endTimestampUTC": endTimestampUTC.isoformat(),
                "startTimestamp": startDateUK.isoformat(),
                "endTimestamp": endDateUK.isoformat(),
                "dateUK": startDateUK.strftime("%Y-%m-%d"),
                "startTimeUK": startDateUK.strftime("%H:%M"),
                "endTimeUK": endDateUK.strftime("%H:%M"),
                "recurring": c[event.get("uid")] > 1,
                "title": event.get("summary", "").strip(),
                "description": description.strip(),
                "location": event.get("location"),
                "lastModified": (
                    event.get("last-modified").dt.isoformat()
                    if event.get("last-modified") is not None
                    else None
                ),
                "status": event.get("status"),
                "invitationStatus": partstat,
                "url": event.get("url"),
                "organizer": organizer,
            }
        except Exception as e:
            print("Could add event: " + event.get("uid"))
            print(e)
            continue

        new_event.update(description_json)

        events.append(new_event)

    # sort by startTimestamp descending
    # events = sorted(events, key=lambda k: k['startTimestamp'], reverse=False)
    # with open(args.output, 'w') as f:
    #    json.dump(events, f, indent=4)
    # First, sort deterministically so that numbering will be stable.
    events = sorted(
        events,
        key=lambda k: (
            k.get("startTimestamp", ""),
            k.get("uid", ""),
            k.get("endTimestamp", ""),
            k.get("title", ""),
        ),
        reverse=False,
    )

    # Now walk the sorted events and append a numeric suffix to duplicate
    # UIDs. We count occurrences per-original-UID as we go; when the count is
    # greater than 1 we replace the event's uid with 'orig-N'. This approach
    # is independent of the input .ics ordering because it uses the
    # deterministic sort order above.
    uid_counter = {}
    for ev in events:
        u = ev.get("uid")
        if not u:
            continue
        uid_counter[u] = uid_counter.get(u, 0) + 1
        if uid_counter[u] > 1:
            ev["uid"] = f"{u}-{uid_counter[u]}"

    # write to a temporary file in the current working directory and atomically replace
    temp_name = os.path.basename(args.output) + "." + uuid.uuid4().hex + ".tmp"
    temp_path = os.path.join(os.getcwd(), temp_name)
    try:
        with open(temp_path, "w", encoding="utf-8") as tf:
            json.dump(events, tf, indent=4)
            tf.flush()
            try:
                os.fsync(tf.fileno())
            except Exception:
                # os.fsync may not be available on all platforms or filesystems; ignore if it fails
                pass
        # atomic replace
        os.replace(temp_path, args.output)
        temp_path = None
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

    if args.ics:
        cal = dict_to_ical(events)

        with open(args.output.replace(".json", ".ics"), "wb") as f:
            f.write(cal.to_ical())

    if args.sqlite:

        dict_to_sqlite(events, args.output.replace(".json", ".sqlite"))


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-i", "--input", required=True, help="Input .ics file (can be url)"
    )
    parser.add_argument("-o", "--output", required=True, help="Output .json file")
    parser.add_argument(
        "--ics", help="Output a cleaned up .ics file as well", action="store_true"
    )
    parser.add_argument(
        "--sqlite", help="Output a sqlite database file as well", action="store_true"
    )
    parser.add_argument(
        "--plaintext-organizer", help="Keep organizer email in plaintext instead of hashed", action="store_true"
    )
    parser.add_argument(
        "--organizer-key", help="Secret key for HMAC-SHA256 hashing of organizer emails (required for hashing)", type=str
    )

    args = parser.parse_args()

    # Validate organizer arguments
    if not args.plaintext_organizer and not args.organizer_key:
        parser.error("--organizer-key is required when --plaintext-organizer is not set. Either provide a key for secure hashing or use --plaintext-organizer.")

    main(args)
