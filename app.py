import io
import os
from datetime import datetime, timezone

import boto3
import matplotlib.pyplot as plt
import pandas as pd
import requests
from botocore.exceptions import ClientError

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
S3_BUCKET = os.environ["S3_BUCKET"]
DYNAMODB_TABLE = os.environ["DYNAMODB_TABLE"]

# Charlottesville, VA
CITY = os.environ.get("CITY", "Charlottesville")
LATITUDE = float(os.environ.get("LATITUDE", "38.0293"))
LONGITUDE = float(os.environ.get("LONGITUDE", "-78.4767"))

dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
s3 = boto3.client("s3", region_name=AWS_REGION)


def get_or_create_table():
    client = boto3.client("dynamodb", region_name=AWS_REGION)

    try:
        client.describe_table(TableName=DYNAMODB_TABLE)
    except client.exceptions.ResourceNotFoundException:
        client.create_table(
            TableName=DYNAMODB_TABLE,
            AttributeDefinitions=[
                {"AttributeName": "city", "AttributeType": "S"},
                {"AttributeName": "timestamp", "AttributeType": "S"},
            ],
            KeySchema=[
                {"AttributeName": "city", "KeyType": "HASH"},
                {"AttributeName": "timestamp", "KeyType": "RANGE"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        waiter = client.get_waiter("table_exists")
        waiter.wait(TableName=DYNAMODB_TABLE)

    return dynamodb.Table(DYNAMODB_TABLE)


def fetch_weather():
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "hourly": "temperature_2m,precipitation,cloud_cover,wind_speed_10m",
        "timezone": "auto",
        "forecast_days": 1,
    }

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    hourly = data["hourly"]
    times = hourly["time"]

    now_utc = datetime.now(timezone.utc)

    # choose the latest hourly timestamp not in the future
    parsed = [
        datetime.fromisoformat(t).astimezone(timezone.utc)
        if datetime.fromisoformat(t).tzinfo
        else datetime.fromisoformat(t).replace(tzinfo=timezone.utc)
        for t in times
    ]

    valid_indices = [i for i, t in enumerate(parsed) if t <= now_utc]
    idx = valid_indices[-1] if valid_indices else 0

    return {
        "city": CITY,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M"),
        "temperature_2m": float(hourly["temperature_2m"][idx]),
        "precipitation": float(hourly["precipitation"][idx]),
        "cloud_cover": float(hourly["cloud_cover"][idx]),
        "wind_speed_10m": float(hourly["wind_speed_10m"][idx]),
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
    }


def put_record(table, record):
    table.put_item(
        Item={
            "city": record["city"],
            "timestamp": record["timestamp"],
            "temperature_2m": str(record["temperature_2m"]),
            "precipitation": str(record["precipitation"]),
            "cloud_cover": str(record["cloud_cover"]),
            "wind_speed_10m": str(record["wind_speed_10m"]),
            "latitude": str(record["latitude"]),
            "longitude": str(record["longitude"]),
        }
    )


def load_all_records(table):
    response = table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key("city").eq(CITY)
    )
    items = response.get("Items", [])

    while "LastEvaluatedKey" in response:
        response = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("city").eq(CITY),
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))

    if not items:
        return pd.DataFrame(
            columns=[
                "city",
                "timestamp",
                "temperature_2m",
                "precipitation",
                "cloud_cover",
                "wind_speed_10m",
                "latitude",
                "longitude",
            ]
        )

    df = pd.DataFrame(items)
    for col in ["temperature_2m", "precipitation", "cloud_cover", "wind_speed_10m", "latitude", "longitude"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").drop_duplicates(subset=["city", "timestamp"])
    return df


def upload_csv(df):
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)

    s3.put_object(
        Bucket=S3_BUCKET,
        Key="data.csv",
        Body=csv_buffer.getvalue().encode("utf-8"),
        ContentType="text/csv",
    )

def upload_plot(df):
    if df.empty:
        return

    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"]).sort_values("timestamp")

    latest_time = df["timestamp"].max()
    cutoff = latest_time - pd.Timedelta(hours=72)
    plot_df = df[df["timestamp"] >= cutoff].copy()

    if plot_df.empty:
        return

    precip = pd.to_numeric(plot_df["precipitation"], errors="coerce").fillna(0)
    precip = precip.clip(lower=0)

    temp = pd.to_numeric(plot_df["temperature_2m"], errors="coerce")
    plot_df = plot_df.assign(temperature_2m=temp, precipitation=precip)
    plot_df = plot_df.dropna(subset=["temperature_2m"])

    plt.figure(figsize=(12, 6))

    plt.plot(
        plot_df["timestamp"],
        plot_df["temperature_2m"],
        marker="o",
        label="Temperature (°F)"
    )

    plt.bar(
        plot_df["timestamp"],
        plot_df["precipitation"],
        alpha=0.3,
        label="Precipitation (mm)"
    )

    plt.title(f"{CITY} Weather")
    plt.xlabel("Time")
    plt.ylabel("Value")
    plt.xticks(rotation=45)
    plt.legend()
    plt.tight_layout()

    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format="png")
    plt.close()
    img_buffer.seek(0)

    s3.put_object(
        Bucket=S3_BUCKET,
        Key="plot.png",
        Body=img_buffer.getvalue(),
        ContentType="image/png",
    )

def main():
    table = get_or_create_table()
    record = fetch_weather()
    put_record(table, record)

    df = load_all_records(table)
    upload_csv(df)
    upload_plot(df)

    print(f"Saved record for {record['timestamp']}")
    print(f"Uploaded s3://{S3_BUCKET}/data.csv")
    print(f"Uploaded s3://{S3_BUCKET}/plot.png")


if __name__ == "__main__":
    main()
