from io import BytesIO
import pandas as pd
import requests

LOCATION_URL = "https://www.vec.vic.gov.au/-/media/d6faeb7027634194bf56150194ecd7f6.xlsx"


def cleanColumn(name):
    return " ".join(str(name).lower().replace("_", " ").split())


def findColumns(columns, possibleNames):
    for column in columns:
        if cleanColumn(column) in possibleNames:
            return column
    return None


def getVotingLocations():
    response = requests.get(
        LOCATION_URL,
        timeout=30,
        headers={"User-Agent": "VicVotesResearch/0.1"}
    )
    response.raise_for_status()

    data = pd.read_excel(
        BytesIO(response.content),
        sheet_name=None
    )["VC Locations"]

    locations = data[data["Electorates"].astype(
        str).str.contains("Essendon", case=False, na=False)].copy()

    locations = locations[
        locations["ElectionName"].astype(str).str.contains("2022", na=False)
    ].copy()

    locations = locations[["VotingLocationName", "VenueName",
                           "VotingLocationTypeDesc", "PhysicalSuburb", "Lat", "Long"]].copy()

    locations = locations.rename(
        columns={
            "VotingLocationName": "votingCentre",
            "VenueName": "venue",
            "VotingLocationTypeDesc": "locationType",
            "PhysicalSuburb": "suburb",
            "Lat": "latitude",
            "Long": "longitude"
        }
    )

    locations["latitude"] = pd.to_numeric(
        locations["latitude"], errors="coerce")
    locations["longitude"] = pd.to_numeric(
        locations["longitude"], errors="coerce")

    locations = locations.dropna(
        subset=["votingCentre", "latitude", "longitude"]
    )

    locations = locations[
        locations["latitude"].between(-39, -37) &
        locations["longitude"].between(144, 146)
    ]

    if locations.empty:
        raise ValueError("No Essendon voting locations found.")

    return locations.reset_index(drop=True)
