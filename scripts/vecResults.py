import requests
import pandas as pd
from bs4 import BeautifulSoup

# URL = "https://www.vec.vic.gov.au/results/state-election-results/2022-state-election-results/results-by-district/essendon-district-results/essendon-district-results-by-voting-centre"
URL_BY_YEAR = {
    2018: "https://itsitecoreblobvecprd01.blob.core.windows.net/public-files/historical-results/state2018/fpvbyvotingcentreessendondistrict.html",
    2022: "https://www.vec.vic.gov.au/results/state-election-results/2022-state-election-results/results-by-district/essendon-district-results/essendon-district-results-by-voting-centre"
}

# CANDIDATES = [
#     "Animal Justice",
#     "Freedom",
#     "Greens",
#     "Socialists",
#     "Reason",
#     "Liberal",
#     "Labor",
#     "Family First",
# ]

CANDIDATES_BY_YEAR = {
    2018: [
        "Baker",
        "Greens",
        "DLP",
        "Lawrence",
        "Labor",
        "Liberal",
    ],
    2022: [
        "Animal Justice",
        "Freedom",
        "Greens",
        "Socialists",
        "Reason",
        "Liberal",
        "Labor",
        "Family First",
    ],
}
CANDIDATES = CANDIDATES_BY_YEAR[2022]

EXPECTED_TOTALS = {
    2018: (41472, 2067, 43539),
    2022: (41867, 1761, 43628),
}


def normaliseName(name):
    return " ".join(str(name).strip().split()).casefold()


def getVotingCentres(year=2022):
    if year not in URL_BY_YEAR:
        raise ValueError(f"No results URL for {year}")
    response = requests.get(URL_BY_YEAR[year], timeout=30, headers={
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

    candidates = CANDIDATES_BY_YEAR[year]
    cols = [
        "votingCentre",
        *candidates,
        "informal",
        "totalVotes"
    ]

    rows = []

    for tr in table.find_all("tr"):
        cells = [
            cell.get_text(" ", strip=True)
            for cell in tr.find_all(["td", "th"], recursive=False)
        ]

        if len(cells) != len(cols):
            continue

        try:
            votes = [int(value.replace(",", "")) for value in cells[1:]]
        except ValueError:
            continue

        rows.append([cells[0].strip(), *votes])

    if not rows:
        raise ValueError("No voting centre results found")

    results = pd.DataFrame(rows, columns=cols)

    results["nameKey"] = results["votingCentre"].map(normaliseName)

    if results["nameKey"].duplicated().any():
        raise ValueError("Duplicate voting centre name found")

    results["voteType"] = "ordinary"

    summaryNames = {"ordinary votes total", "total"}
    otherNames = {"absent votes", "early votes",
                  "marked as voted votes", "postal votes", "provisional votes"}

    results.loc[results["nameKey"].isin(otherNames), "voteType"] = "other"
    results.loc[results["nameKey"].isin(
        summaryNames), "voteType"] = "summary"

    validateResults(results, year)
    return results.drop(columns="nameKey")


def validateResults(results, year):
    candidates = CANDIDATES_BY_YEAR[year]
    countColumns = candidates + ["informal", "totalVotes"]

    indexed = results.set_index(
        results["votingCentre"].map(normaliseName)
    )

    required = {
        "ordinary votes total",
        "total",
        "absent votes",
        "early votes",
        "postal votes",
        "provisional votes",
        "marked as voted votes",
    }

    missing = required - set(indexed.index)
    if missing:
        raise ValueError(f"Missing expected results rows: {sorted(missing)}")

    formal, informal, totalVotes = EXPECTED_TOTALS[year]
    district = indexed.loc["total"]

    if int(district[candidates].sum()) != formal:
        raise ValueError("Formal votes do not match VEC total")
    if int(district["informal"]) != informal:
        raise ValueError("Informal votes do not match VEC total")
    if int(district["totalVotes"]) != totalVotes:
        raise ValueError("Total votes does not match VEC total")

    if not (
        results[candidates].sum(axis=1)
        + results["informal"]
        == results["totalVotes"]
    ).all():
        raise ValueError("Candidate counts do not reconcile")

    ordinary = results[results["voteType"] == "ordinary"]
    ordinaryTotal = indexed.loc["ordinary votes total"]

    if not (
        ordinary[countColumns].sum()
        == ordinaryTotal[countColumns]
    ).all():
        raise ValueError("Voting centre totals do not reconcile")

    nonSummary = results[results["voteType"] != "summary"]

    if not (
        nonSummary[countColumns].sum()
        == district[countColumns]
    ).all():
        raise ValueError("District totals do not reconcile")
