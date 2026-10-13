import requests
import pandas as pd
from bs4 import BeautifulSoup

URL = "https://www.vec.vic.gov.au/results/state-election-results/2022-state-election-results/results-by-district/essendon-district-results/essendon-district-results-by-voting-centre"

CANDIDATES = [
    "Animal Justice",
    "Freedom",
    "Greens",
    "Socialists",
    "Reason",
    "Liberal",
    "Labor",
    "Family First",
]

COLUMNS = [
    "votingCentre",
    *CANDIDATES,
    "informal",
    "totalVotes",
]

OTHER_VOTES = [
    "Absent votes",
    "Early votes",
    "Marked As Voted votes",
    "Postal votes",
    "Provisional votes",
]

SUMMARY_ROWS = [
    "Ordinary votes total",
    "Total",
]


def getVotingCentres():
    response = requests.get(URL, timeout=30, headers={
                            "User-Agent": "VictoriaVotesResearch/0.1"})
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    table = None
    for candidateTable in soup.find_all("table"):
        if "Ascot Vale Central" in candidateTable.get_text(" ", strip=True):
            table = candidateTable
            break

    if table is None:
        raise ValueError("Could not find the voting centre results table")

    rows = []

    for tr in table.find_all("tr"):
        cells = [
            cell.get_text(" ", strip=True)
            for cell in tr.find_all(["td", "th"], recursive=False)
        ]

        if len(cells) != len(COLUMNS):
            continue

        name = cells[0]

        try:
            votes = [int(value.replace(",", "")) for value in cells[1:]]
        except ValueError:
            continue

        rows.append([name, *votes])

    if not rows:
        raise ValueError("No voting centre results found")

    results = pd.DataFrame(rows, columns=COLUMNS)

    if results["votingCentre"].duplicated().any():
        raise ValueError("Duplicate voting centre name found")

    results["voteType"] = "ordinary"

    results.loc[results["votingCentre"].isin(OTHER_VOTES), "voteType"] = "other"
    results.loc[results["votingCentre"].isin(
        SUMMARY_ROWS), "voteType"] = "summary"

    validateResults(results)
    return results


def validateResults(results):
    expectedRows = set(OTHER_VOTES + SUMMARY_ROWS)

    missing = expectedRows - set(results["votingCentre"])
    if missing:
        raise ValueError(f"Missing expected results rows: {missing}")

    total = results.set_index("votingCentre").loc["Total"]

    if int(total[CANDIDATES].sum()) != 41867:
        raise ValueError("Formal votes do not match VEC total")
    if int(total["informal"]) != 1761:
        raise ValueError("Informal votes do not match VEC total")
    if int(total["totalVotes"]) != 43628:
        raise ValueError("Total votes does not match VEC total")

    ordinary = results[results["voteType"] == "ordinary"]
    ordinaryTotal = results.set_index(
        "votingCentre").loc["Ordinary votes total"]

    if not (
        ordinary[CANDIDATES + ["informal", "totalVotes"]].sum()
        == ordinaryTotal[CANDIDATES + ["informal", "totalVotes"]]
    ).all():
        raise ValueError("Voting centre totals do not reconcile")

    nonSummary = results[results["voteType"] != "summary"]

    if not (
        nonSummary[CANDIDATES + ["informal", "totalVotes"]].sum()
        == total[CANDIDATES + ["informal", "totalVotes"]]
    ).all():
        raise ValueError("District totals do not reconcile")

    if not (
        results[CANDIDATES].sum(
            axis=1) + results["informal"] == results["totalVotes"]
    ).all:
        raise ValueError("Formal and informal votes do not add up")
