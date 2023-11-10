import schedule
import time
import requests
from twilio.rest import Client
import os
from dotenv import find_dotenv, load_dotenv

# find path to .env file in directory
dotenv_path = find_dotenv()
load_dotenv(dotenv_path)

TWILIO_SID = os.getenv("TWILIO_SID")
AUTH_TOKEN = os.getenv("AUTH_TOKEN")
FROM_PHONE = os.getenv("FROM_PHONE")
TO_PHONE = os.getenv("TO_PHONE")

LATITUDE = os.getenv("LATITUDE")        # Latitude of city to get weather info from
LONGITUDE = os.getenv("LONGITUDE")      # Longitude of city to get weather info from
SEND_MESSAGE_TIME = "10:00"             # 24h format
START_TIME = 10                         # integer; hour in 24h format
END_TIME =  19                          # integer; hour in 24h format


"""
Uses Twilio's api to send a text message to designated number for clothing suggestions for the day
"""
def send_text_message(body):
    account_sid = TWILIO_SID
    auth_token = AUTH_TOKEN
    from_phone_number = FROM_PHONE
    to_phone_number = TO_PHONE

    client = Client(account_sid, auth_token)

    message = client.messages.create(
        from_= from_phone_number,
        body = body,
        to = to_phone_number
    )

    print(message.sid)

"""
makes a call to Open Meteo's weather api to collect weather information

@return: data from api call to Open Meteo
"""
def get_weather():
    base_url = f"https://api.open-meteo.com/v1/forecast?latitude={LATITUDE}&longitude={LONGITUDE}&hourly=temperature_2m,precipitation_probability,precipitation,rain,showers,snowfall,snow_depth,cloudcover&daily=uv_index_max&timezone=America%2FLos_Angeles"
    response = requests.get(base_url)

    # check if api call went through; if not, send status code
    if response.status_code == 200:
        print("successfully fetched the data")
    else:
        print(response.status_code)

    data = response.json()
    return data

"""
finds the average from a time window

@param data: the data that is being averaged

@var from_: hour in 24h format; the starting time to average
@var to: hour in 24h format; the ending time to average
@var total: the total of the data being averaged

@return: returns the mean average from said time window
"""
def find_avg(data):
    from_= START_TIME
    to = END_TIME
    total = 0

    for i in range(from_, to):
        total += data[i]
    
    return total / (to - from_)

"""
updates results based on temperature

@param res: results dict that this helper is updating
@param *args: list of arbitrary length of additional arguments required to update results
"""
def temp_updates(res, temp):
    if temp >= 30:
        res["clothing"][3] = 10

        res["footwear"] = 1
    elif temp >= 20:
        res["clothing"][3] += 8

        res["footwear"] += 0.5
    elif temp >= 15:
        res["clothing"][2] += 3
        res["clothing"][3] += 6
    elif temp >= 10:
        res["clothing"][3] += 3
        res["clothing"][2] += 8
        res["clothing"][1] += 5

        res["footwear"] -= 0.1
    elif temp >= 5:
        res["clothing"][2] += 6
        res["clothing"][1] += 8
        res["clothing"][0] += 2

        res["footwear"] -= 0.3
    elif temp >= 0:
        res["clothing"][2] += 3
        res["clothing"][1] += 9
        res["clothing"][3] += 7

        res["footwear"] -= 0.5
    elif temp < -5:
        res["clothing"][0] = 10

        res["footwear"] -= 0.5
    
    res["temperature"] = "{:.1f}".format(temp)

"""
updates results based on weather

@param res: results dict that this helper is updating
@param *args: list of arbitrary length of additional arguments required to update results
"""
def precip_updates(res, precip, showrain, snowfall, snow_depth, cloudcover):
    # if snowing
    if precip > 40 and snowfall > showrain:
        if snow_depth > 3:
            res["footwear"] = -1
        if snowfall < 10:
            res["weather"] = "light snow"

            res["footwear"] -= 0.7
        else:
            res["weather"] = "heavy snow"

            res["footwear"] = -1
        
        return

    # if precip is less than 40%, don't bring umbrella
    if precip < 40:
        res["umbrella"] = False
        
        if cloudcover >= 88:
            res["weather"] = "cloudy"
        elif cloudcover >= 70:
            res["weather"] = "mostly cloudy"
        elif cloudcover >= 51:
            res["weather"] = "partly cloudy"
        elif cloudcover >= 26:
            res["weather"] = "mostly sunny"
        elif cloudcover >= 6:
            res["weather"] = "sunny"
        else:
            res["weather"] = "clear skies"
    # in the case of rain
    else:
        res["umbrella"] = True
        if showrain < 2.5:
            res["weather"] = "light rain"
        elif showrain < 7.6:
            res["weather"] = "moderate rain"
        elif showrain < 50:
            res["weather"] = "heavy rain"

            res["footwear"] = -1
        else:
            res["weather"] = "violent rain"

            res["footwear"] = -1
        
        res["clothing"][0] += 3
        res["clothing"][1] += 4

def sun_updates(res, uv):
    if uv < 3:
        res["sunscreen"] = False
    if uv < 6:
        res["sunscreen"] = False
        
        res["clothing"][3] -= 2
    else:
        res["sunscreen"] = True
        res["clothing"][3] -= 6

"""
helper for determine(); determines what clothes you should wear
"""
def determine_clothing(res):
    clothing = res["clothing"]
    max_clothing = clothing[0]
    index_clothing = 0

    for i in range(1, len(clothing)):
        if clothing[i] > max_clothing:
            max_clothing = clothing[i]
            index_clothing = i
    
    match index_clothing:
        case 0:
            return "coat"
        case 1:
            return "jacket"
        case 2:
            return "sweater"
        case 3:
            return "t-shirt"

"""
helper for determine(); determines what footwear you should wear
"""
def determine_footwear(res):
    if res["footwear"] > 0.8:
        return "slides"
    elif res["footwear"] < -0.4:
        return "boots"
    else:
        return "sneakers"

"""
determines what you should wear

@return: a list of things to put in text message
"""
def determine(res):
    formatted = {
        "clothes": determine_clothing(res),
        "footwear": determine_footwear(res),
        "umbrella": res["umbrella"],
        "weather": res["weather"],
        "sunscreen": res["sunscreen"],
        "temperature": res["temperature"]
    }

    return formatted



"""
determines what to wear

@param temp: temperature
@param precip: precipitation
@param rain: rainfall
@param shower: shower
@param snowfall: snowfall
@param snow_depth: snow depth
@param uv_index: uv index
@param cloudcover: cloudcover percentage

@return: result of determined clothing options
"""
def what_to_wear(temp, precip, rain, shower, snowfall, snow_depth, uv_index, cloudcover):
    # list of combined values of shower and rain; they are considered the same weather for this script
    showrain = []
    
    temp_avg = find_avg(temp)
    precip_avg = find_avg(precip)
    for i in range(len(rain)):
        showrain.append(rain[i] + shower[i])
    showrain_avg = find_avg(showrain)
    snowfall_avg = find_avg(snowfall)
    snow_depth_avg = find_avg(snow_depth)
    uv = max(uv_index)
    cloudcover_avg = find_avg(cloudcover)

    result = {
        # scale from 0 to 10
        # coat, jacket, sweater, t-shirt
        "clothing": [0]*4,

        # -1 ------- 0 ------- 1
        # boots   sneakers   slides
        "footwear": 0,

        # boolean
        "umbrella": None,

        # status
        "weather": None,

        # boolean
        "sunscreen": None,

        # float
        "temperature": None
    }

    temp_updates(result, temp_avg)
    precip_updates(result, precip_avg, showrain_avg, snowfall_avg, snow_depth_avg, cloudcover_avg)
    sun_updates(result, uv)

    choice = determine(result)

    return choice

"""
converts a time from 24h format to 12h format

@return: a string of the time converted to 12h format
"""
def time_converter(time):
    converted = ""

    match time:
        case 0 | 24:
            converted = "12:00 AM"
        case _ if time < 12:
            converted = str(time) + ":00 AM"
        case 12:
            converted = "12:00 PM"
        case _ if time <= 23:
            converted = str(time % 12) + ":00 PM"
        case _:
            print("invalid time")

    

    return converted

"""
processes text into a text message
[clothes, footwear, umbrella, weather, sunscreen, temperature]

@return: a formatted text message with clothing recommendations
"""
def process_text(text):
    start = time_converter(START_TIME)
    end = time_converter(END_TIME)
    
    conditional_weather_text = ""
    
    if "rain" in text['weather'] or "cloudy" in text['weather']:
        conditional_weather_text = f"Since the weather is {text['weather']}, you {'will' if text['umbrella'] else 'will not'} need to bring an umbrella. "
    else:
        conditional_weather_text = f"Today will be {text['weather']}! Enjoy the weather! "
    
    clothing_rec = (
        f"Good morning! Today's average temperature from {start} to {end} is {str(text['temperature']) + '°C'}.\n"
        f"Make sure to at least wear a {text['clothes']} and {text['footwear']} today.\n"
        + conditional_weather_text +
        f"\n{'Remember to apply sunscreen today!' if text['sunscreen'] else 'You do not need to apply sunscreen today'}"
    )

    return clothing_rec

"""
gathers weather data at selected location (in this case Vancouver), and sends a text message for clothing recommendations for the day
"""
def send_clothing_rec():
    weather_data = get_weather()
    temp_celsius = weather_data["hourly"]["temperature_2m"]
    precip_proba = weather_data["hourly"]["precipitation_probability"]
    rain_mm = weather_data["hourly"]["rain"]
    shower_mm = weather_data["hourly"]["showers"]
    snowfall = weather_data["hourly"]["snowfall"]
    snow_depth = weather_data["hourly"]["snow_depth"]
    uv_index = weather_data["daily"]["uv_index_max"]
    cloudcover = weather_data["hourly"]["cloudcover"]

    body = process_text(what_to_wear(temp_celsius, precip_proba, rain_mm, shower_mm, snowfall, snow_depth, uv_index, cloudcover))

    send_text_message(body)


"""
runs the scheduling process
"""
def main():
    schedule.every().day.at(SEND_MESSAGE_TIME).do(send_clothing_rec)
    print("Ready to send message at scheduled time!")

    while True:
        schedule.run_pending()
        time.sleep(1)

# main()
if __name__ == "__main__":
    main()