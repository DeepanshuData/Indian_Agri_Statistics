import requests

url = "https://api.open-meteo.com/v1/forecast"

params={
    "latitude":19.66,
    "longitude":78.53,
    "current":"temperature_2m,relative_humidity_2m,precipitation"
}

response=requests.get(url,params=params)

print(response.json())

data=response.json()

print(data)

