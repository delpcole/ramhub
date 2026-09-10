import base64
import csv
import json
import time

import requests

SCHOOL_LEGACY_ID = 14046
SCHOOL_NAME = "Farmingdale State College"
SCHOOL_GID = base64.b64encode(f"School-{SCHOOL_LEGACY_ID}".encode()).decode()

HEADERS = {
    "Authorization": "Basic dGVzdDp0ZXN0",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Content-Type": "application/json",
    "Referer": f"https://www.ratemyprofessors.com/search/professors/{SCHOOL_LEGACY_ID}",
}

QUERY = """
query TeacherSearchQuery($query: TeacherSearchQuery!, $count: Int!, $cursor: String) {
  search: newSearch {
    teachers(query: $query, first: $count, after: $cursor) {
      resultCount
      pageInfo { hasNextPage endCursor }
      edges {
        node {
          id
          legacyId
          firstName
          lastName
          department
          avgRating
          avgDifficulty
          numRatings
          wouldTakeAgainPercent
          courseCodes { courseName courseCount }
        }
      }
    }
  }
}
"""


def run():
    profs = []
    cursor = None
    while True:
        variables = {
            "query": {"text": "", "schoolID": SCHOOL_GID, "fallback": False},
            "count": 100,
            "cursor": cursor,
        }
        r = requests.post(
            "https://www.ratemyprofessors.com/graphql",
            json={"query": QUERY, "variables": variables},
            headers=HEADERS,
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()["data"]["search"]["teachers"]
        for e in data["edges"]:
            n = e["node"]
            n["firstName"] = (n.get("firstName") or "").strip()
            n["lastName"] = (n.get("lastName") or "").strip()
            n["department"] = (n.get("department") or "").strip()
            profs.append(n)
        print(f"fetched {len(profs)} / {data['resultCount']}")
        if not data["pageInfo"]["hasNextPage"]:
            break
        cursor = data["pageInfo"]["endCursor"]
        time.sleep(0.5)
    return profs


if __name__ == "__main__":
    profs = run()
    # de-dup by legacyId
    seen = {}
    for p in profs:
        seen[p["legacyId"]] = p
    profs = sorted(seen.values(), key=lambda p: (p["lastName"].lower(), p["firstName"].lower()))

    with open("farmingdale_professors.json", "w") as f:
        json.dump(profs, f, indent=2)

    with open("farmingdale_professors.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "last_name",
                "first_name",
                "department",
                "avg_rating",
                "avg_difficulty",
                "num_ratings",
                "would_take_again_pct",
                "top_courses",
                "legacy_id",
                "profile_url",
            ]
        )
        for p in profs:
            courses = "; ".join(
                f"{c['courseName']} ({c['courseCount']})"
                for c in sorted(p.get("courseCodes", []), key=lambda c: -c["courseCount"])[:5]
            )
            wta = p["wouldTakeAgainPercent"]
            wta = "" if wta is None or wta < 0 else round(wta, 1)
            w.writerow(
                [
                    p["lastName"],
                    p["firstName"],
                    p["department"],
                    p["avgRating"] or "",
                    p["avgDifficulty"] or "",
                    p["numRatings"],
                    wta,
                    courses,
                    p["legacyId"],
                    f"https://www.ratemyprofessors.com/professor/{p['legacyId']}",
                ]
            )

    print(f"\nTotal unique professors: {len(profs)}")
