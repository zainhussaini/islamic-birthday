import streamlit as st
import salat
import datetime as dt
import requests
import pytz
import hijridate
from bisect import bisect
import inflect

GOOGLE_MAPS_API_URL = 'https://maps.googleapis.com/maps/api/geocode/json'
GEONAMES_API_URL = "http://api.geonames.org/timezoneJSON?formatted=true"

# The date range supported by converter is limited to the period from the
# beginning of 1343 AH (1 August 1924 CE) to the end of 1500 AH (16 November 2077 CE).
HIJRIDATE_MIN = dt.date(1924, 8, 1)
HIJRIDATE_MAX = dt.date(2077, 11, 16)


@st.cache_data
def get_geodata(address):
    params = {'address': address, 'key': st.secrets["GoogleMapsAPI_key"]}

    # Do the request and get the response data
    req = requests.get(GOOGLE_MAPS_API_URL, params=params)
    res = req.json()

    if 'results' not in res or len(res['results']) == 0:
        raise Exception("Result is not valid:", res)

    # Use the first result
    result = res['results'][0]

    geodata = dict()
    geodata['lat'] = result['geometry']['location']['lat']
    geodata['lng'] = result['geometry']['location']['lng']
    geodata['address'] = result['formatted_address']

    return geodata


@st.cache_data
def get_timezone(lat, lng):
    params = {
        'lat': lat,
        'lng': lng,
        'username': st.secrets["GeoNamesAPI_user"]
    }
    req = requests.get(GEONAMES_API_URL, params=params)
    res = req.json()

    if 'timezoneId' not in res:
        raise Exception("Result is not valid:", res)

    return res['timezoneId']


def get_current_time(timezone):
    time = dt.datetime.now(pytz.UTC)
    return time.astimezone(timezone)


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
        date = st.date_input("Date",
                             min_value=HIJRIDATE_MIN,
                             max_value=HIJRIDATE_MAX)
    with col2:
        current_time = get_current_time(pytz.timezone(timezone_name))
        time = st.time_input("Time (24 hour)", current_time)
    with col3:
        timezone = st.selectbox("Timezone (from location)",
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
    st.markdown("""
    <style>
    .big-font {
        font-size:32px !important;
    }
    </style>
    """,
                unsafe_allow_html=True)

    st.markdown(f'<p class="big-font">{message}</p>', unsafe_allow_html=True)
