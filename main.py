import streamlit as st
import salat
import datetime as dt
import requests
import os
import pytz
import hijridate
from bisect import bisect
import inflect
import dotenv

GOOGLE_MAPS_API_URL = 'https://maps.googleapis.com/maps/api/geocode/json'
GEONAMES_API_URL = "http://api.geonames.org/timezoneJSON?formatted=true"


@st.cache_data
def get_geodata(address):
    dotenv.load_dotenv()

    params = {'address': address, 'key': os.getenv('GOOGLE_MAPS_API')}

    # Do the request and get the response data
    req = requests.get(GOOGLE_MAPS_API_URL, params=params)
    res = req.json()

    # Use the first result
    result = res['results'][0]

    geodata = dict()
    geodata['lat'] = result['geometry']['location']['lat']
    geodata['lng'] = result['geometry']['location']['lng']
    geodata['address'] = result['formatted_address']

    return geodata


@st.cache_data
def get_timezone(lat, lng):
    dotenv.load_dotenv()

    params = {'lat': lat, 'lng': lng, 'username': os.getenv('GEONAMES_USERNAME')}
    req = requests.get(GEONAMES_API_URL, params=params)
    res = req.json()

    return res['timezoneId']


def get_before_and_after_prayer(date, lng, lat):
    pt = salat.PrayerTimes(salat.CalculationMethod.ISNA,
                           salat.AsrMethod.STANDARD)
    prayer_times = pt.calc_times(date, pytz.UTC, lng, lat)

    prayer_names_sorted = list(prayer_times.keys())
    prayer_times_sorted = list(prayer_times.values())
    assert prayer_times_sorted == sorted(prayer_times_sorted)

    insert_position = bisect(prayer_times_sorted, input_datetime)
    before = None
    after = None
    if insert_position - 1 >= 0:
        before = prayer_names_sorted[insert_position - 1]
    if insert_position < len(prayer_names_sorted):
        after = prayer_names_sorted[insert_position]
    return before, after


def generate_message(input_datetime, geodata):

    pt = salat.PrayerTimes(salat.CalculationMethod.ISNA,
                           salat.AsrMethod.STANDARD)
    prayer_times = pt.calc_times(input_datetime.date(), pytz.UTC,
                                 geodata['lng'], geodata['lat'])
    prayer_names_sorted = list(prayer_times.keys())
    prayer_times_sorted = list(prayer_times.values())
    assert prayer_times_sorted == sorted(prayer_times_sorted)

    insert_position = bisect(prayer_times_sorted, input_datetime)
    before = None
    after = None
    if insert_position - 1 >= 0:
        before = prayer_names_sorted[insert_position - 1]
    if insert_position < len(prayer_names_sorted):
        after = prayer_names_sorted[insert_position]

    if before:
        before = before.capitalize()
    if after:
        after = after.capitalize()

    output = ""
    if before is None:
        output += "Before " + after
    elif after is None:
        output += "After " + before
    elif before == "Sunrise":
        output += "Between " + before + " and " + after
    else:
        output += "During " + before

    if insert_position > prayer_names_sorted.index("maghrib"):
        hijri_date = hijridate.Gregorian(input_datetime.year,
                                         input_datetime.month,
                                         input_datetime.day + 1).to_hijri()
    else:
        hijri_date = hijridate.Gregorian(input_datetime.year,
                                         input_datetime.month,
                                         input_datetime.day).to_hijri()

    output += " on " + inflect.engine().ordinal(hijri_date.day)
    output += " of " + hijri_date.month_name()
    output += ", " + str(hijri_date.year) + " " + hijri_date.notation()

    return output


# DISPLAY

if __name__ == "__main__":

    address = st.text_input("Enter location (will search on Google Maps)",
                            "1600 amphitheatre parkway mountain view")
    geodata = get_geodata(address)
    timezone_name = get_timezone(geodata['lat'], geodata['lng'])
    st.markdown(f"Parsed as: **{geodata['address']}**")

    col1, col2, col3 = st.columns(3)
    with col1:
        date = st.date_input("Date")
    with col2:
        time = st.time_input("Time (24 hour)")
    with col3:
        timezone = st.selectbox("Timezone",
                                pytz.all_timezones,
                                pytz.all_timezones.index(timezone_name),
                                disabled=True)
    input_datetime = dt.datetime(date.year,
                                 date.month,
                                 date.day,
                                 time.hour,
                                 time.minute,
                                 time.second,
                                 tzinfo=pytz.timezone(timezone))

    message = generate_message(input_datetime, geodata)
    st.markdown("#### " + message)
