# Weather Pipeline

A simple end-to-end data pipeline that collects hourly weather data, stores it in AWS, and visualizes trends over time.

## Overview

This project pulls Charlottesville weather data, stores it in DynamoDB, and generates a continuously updating plot saved to S3. It runs automatically on a schedule using Kubernetes CronJobs.

## Features

- Fetches real-time weather data (temperature, precipitation, wind, etc.)
- Stores data in AWS DynamoDB with timestamp-based tracking
- Generates and uploads a time-series visualization to S3
- Runs automatically every 15 minutes using Kubernetes

## Tech Stack

- Python (requests, pandas, matplotlib, boto3)
- AWS (DynamoDB, S3, IAM)
- Docker
- Kubernetes (CronJobs)
