# Weather Pipeline

A simple end-to-end data pipeline that collects hourly weather data, stores it in AWS, and visualizes trends over time.

## Overview

This project pulls Charlottesville weather data, stores it in DynamoDB, and generates a continuously updating plot saved to S3. It runs automatically on a schedule using Kubernetes CronJobs.

## Data Source 

Weather data is sourced from the Open-Meteo API, a free, open-source weather API that provides historical and forecast data without requiring an API key. For this pipeline, the Charlottesville, VA coordinates are used to request hourly observations including temperature (°C), precipitation (inches), wind speed (m/s), and cloud cover (%). Open-Meteo aggregates data from national weather services (including NOAA) and global forecast models, making it a reliable source for localized meteorological data.

## Pipeline Details

The pipeline runs as a Kubernetes CronJob every 15 minutes and executes the following steps:

Fetch: A Python script calls the Open-Meteo API for the current hour's weather observations at the Charlottesville coordinates.

Transform: The raw JSON response is parsed and flattened into a structured record with a UTC timestamp as the unique identifier.

Store: The record is written to a DynamoDB table (weather-data), using the timestamp as the partition key to prevent duplicate entries on re-runs.

Visualize: All records from the past 3 days are queried from DynamoDB, loaded into a pandas DataFrame, and used to render a time-series plot.

Upload: The data and plot(saved as a PNG) are uploaded to a designated S3 bucket and continuously update to reflect new incoming data.

## Data Dictionary

Each pipeline run appends one row to DynamoDB with the following fields:

| Field                 | Type    | Description                                                                 |
|----------------------|--------|-----------------------------------------------------------------------------|
| `timestamp`          | String | UTC datetime of the observation. Partition key.                             |
| `city`               | String | Name of the city for the weather observation.                               |
| `latitude`           | Float  | Latitude coordinate of the observation location.                            |
| `longitude`          | Float  | Longitude coordinate of the observation location.                           |
| `temperature_2m`     | Float  | Air temperature in degrees Celsius (°C).                                    |
| `precipitation`      | Float  | Hourly precipitation accumulation in inches.                                |
| `cloud_cover`        | Integer| Percentage of sky covered by clouds (0–100%).                               |
| `wind_speed_10m`     | Float  | Wind speed in miles per second (m/s).                                       |

The generated visualization is a time-series plot spanning a 72-hour period, showing both temperature and wind speed trends in Charlottesville. Temperature is shown as a continuous line, revealing clear daily cycles with cooler early mornings and warmer afternoon peaks, while wind speed is overlaid as a secondary dotted line, highlighting more irregular fluctuations and short-term variability. Together, the plot provides a comparative view of how these two weather variables evolve over time.

## Tech Stack

- Python (requests, pandas, matplotlib, boto3)
- AWS (DynamoDB, S3, IAM)
- Docker
- Kubernetes (CronJobs)
