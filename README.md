Weather Dashboard Setup

This application has been updated to be "cloud-native." It contains no hardcoded secrets or locations. You must provide these values via Environment Variables.

1. Prerequisites

Python 3.8+

An OpenWeatherMap API Key

2. Running Locally

You can set the variables directly in your terminal command before running streamlit.

Mac/Linux:

export OPENWEATHER_API_KEY="your_actual_api_key_here"
export DEFAULT_LATITUDE="40.7128"
export DEFAULT_LONGITUDE="-74.0060"

streamlit run weather_dashboard.py


Windows (PowerShell):

$env:OPENWEATHER_API_KEY="your_actual_api_key_here"
$env:DEFAULT_LATITUDE="40.7128"
$env:DEFAULT_LONGITUDE="-74.0060"

streamlit run weather_dashboard.py


3. Running with Docker

This structure is perfect for Docker. You don't need to rebuild your image to change the location or the key; you just change the docker run command.

Example Docker Command:

docker run -p 8501:8501 \
  -e OPENWEATHER_API_KEY="your_actual_api_key_here" \
  -e DEFAULT_LATITUDE="51.5074" \
  -e DEFAULT_LONGITUDE="-0.1278" \
  my-weather-app
