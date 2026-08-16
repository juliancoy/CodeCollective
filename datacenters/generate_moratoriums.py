#!/usr/bin/env python3
"""Generate the Maryland local data-center moratorium status layer.

County geometry comes from the existing Census TIGERweb-backed power estimate
layer. Policy status is curated from primary local government records so a
proposal is never presented as enacted law.
"""

import argparse
import json
from copy import deepcopy
from datetime import date
from pathlib import Path

from shapely.geometry import mapping, shape


ROOT = Path(__file__).resolve().parent
DEFAULT_GEOMETRY = ROOT / "data" / "power-estimates.json"
DEFAULT_OUTPUT = ROOT / "data" / "moratoriums.json"
DISPLAY_SIMPLIFICATION_DEGREES = 0.001


ACTIONS = {
    "Baltimore County": {
        "status": "enacted", "status_label": "Enacted",
        "action_type": "Temporary moratorium", "legal_instrument": "Bill 3-26",
        "adopted_date": "2026-01-20", "effective_date": "2026-02-03",
        "end_date": "2027-01-01 or earlier under the Act",
        "scope": "Suspends data-center permits and bars County agencies from accepting related applications, petitions, hearings, development plans, or zoning petitions.",
        "source_title": "Baltimore County Bill 3-26 - Zoning Regulations - Data Center Study",
        "source_url": "https://countycouncilweb.s3.amazonaws.com/Bills%202026/b00326.pdf",
    },
    "Baltimore city": {
        "status": "enacted", "status_label": "Enacted",
        "action_type": "Temporary citywide moratorium", "legal_instrument": "Ordinance 26-128 (File 26-0158)",
        "adopted_date": "2026-06-16", "effective_date": None, "end_date": None,
        "scope": "Establishes data centers as a prohibited use citywide for the ordinance's temporary effective period.",
        "source_title": "Baltimore City File 26-0158 - Data Centers - Moratorium",
        "source_url": "https://baltimore.legistar.com/LegislationDetail.aspx?GUID=0F67C3A9-D166-4BFE-91D3-10070032F578&ID=7958934",
    },
    "Calvert County": {
        "status": "pending", "status_label": "Pending",
        "action_type": "Formal advisory proposal", "legal_instrument": "Environmental Commission recommendation",
        "adopted_date": None, "effective_date": None, "end_date": None,
        "scope": "The County Environmental Commission formally recommended at least a 12-month permitting moratorium; the Board of County Commissioners has not enacted it.",
        "source_title": "Calvert County Environmental Commission data-center recommendations",
        "source_url": "https://www.calvertcountymd.gov/DocumentCenter/View/57104/Env-Commission-Proposal-for-CC-BOCC-with-Update-from-Mtg-on-June-02-2026",
    },
    "Caroline County": {
        "status": "enacted", "status_label": "Enacted",
        "action_type": "Temporary moratorium", "legal_instrument": "Resolution 2026-012",
        "adopted_date": "2026-07-21", "effective_date": "2026-07-21", "end_date": "2027-07-21",
        "scope": "Bars new County permits for data-center approval or construction in unincorporated Caroline County for one year; municipalities retain their own zoning authority.",
        "source_title": "Caroline County Resolution 2026-012 - Moratorium on Data Centers",
        "source_url": "https://www.carolinemd.org/DocumentCenter/View/12232/DATA-CENTER-MORATORIUM-RESOLUTION-6-012",
    },
    "Frederick County": {
        "status": "stopped", "status_label": "Stopped",
        "action_type": "Executive / administrative pause", "legal_instrument": "Executive Order 04-2026",
        "adopted_date": "2026-07-01", "effective_date": "2026-07-01", "end_date": "2026-12-31",
        "scope": "County staff are not accepting or processing new Critical Digital Infrastructure facility or related substation applications; previously approved and active construction is exempt.",
        "source_title": "Frederick County - Data Centers",
        "source_url": "https://www.frederickcountymd.gov/9310/Data-Centers",
    },
    "Harford County": {
        "status": "enacted", "status_label": "Enacted",
        "action_type": "Permanent zoning prohibition", "legal_instrument": "Bill 26-011",
        "adopted_date": "2026-06-10", "effective_date": "2026-06-10", "end_date": None,
        "scope": "Prohibits data centers in every Harford County zoning district; this is a permanent ban rather than a temporary moratorium.",
        "source_title": "Harford County Executive signs legislation banning data centers",
        "source_url": "https://www.harfordcountymd.gov/NewsFlash/Home/Detail/1700",
    },
    "Howard County": {
        "status": "enacted", "status_label": "Enacted",
        "action_type": "Temporary moratorium", "legal_instrument": "CB31-2026 (S.M.A.R.T. Siting Act)",
        "adopted_date": "2026-06-04", "effective_date": "2026-08-04", "end_date": "No later than 2028-02-04",
        "scope": "Temporarily stops plan submissions and specified approvals for data-processing centers, subject to the Act's exemptions and earlier sunset conditions.",
        "source_title": "Howard County CB31-2026 legislation record",
        "source_url": "https://apps.howardcountymd.gov/olis/LegislationDetail/15036/CB31-2026",
    },
    "Montgomery County": {
        "status": "enacted", "status_label": "Enacted",
        "action_type": "Countywide zoning prohibition", "legal_instrument": "Ordinance 20-35 (ZTA 26-01)",
        "adopted_date": "2026-07-28", "effective_date": "2026-08-17", "end_date": None,
        "scope": "Removes large data centers as an allowed use in every zone; the enacted transition rule reaches applications lacking a building permit before the effective date.",
        "source_title": "Montgomery County Ordinance 20-35 (ZTA 26-01)",
        "source_url": "https://assets.montgomerycountymd.gov/files/2026-07/Ordinance%2020-35%20%28ZTA%2026-01%29.pdf",
    },
    "Prince George's County": {
        "status": "enacted", "status_label": "Enacted",
        "action_type": "Temporary moratorium", "legal_instrument": "CR-066-2026",
        "adopted_date": "2026-07-07", "effective_date": "2026-07-07", "end_date": "2028-07-07",
        "scope": "Pauses acceptance, processing, review, and approval of specified subdivision, site-plan, building, and grading applications involving qualified data-center uses for two years.",
        "source_title": "Prince George's County CR-066-2026 legislation record",
        "source_url": "https://princegeorgescountymd.legistar.com/LegislationDetail.aspx?GUID=4DA0E757-A8B6-4BFD-A7E5-E83AD62A0B1F&ID=8122087",
    },
    "Queen Anne's County": {
        "status": "enacted", "status_label": "Enacted",
        "action_type": "Temporary moratorium", "legal_instrument": "County Commissioners' moratorium action",
        "adopted_date": "2026-06-04", "effective_date": "2026-06-04", "end_date": "2027-06-04",
        "scope": "Pauses application, approval, and processing of data-center applications countywide for 12 months.",
        "source_title": "Queen Anne's County Commissioners approve temporary moratorium",
        "source_url": "https://www.qac.org/CivicAlerts.aspx?AID=3243",
    },
}


def generate(geometry_path: Path) -> dict:
    geometry = json.loads(geometry_path.read_text())
    features = []
    for source_feature in geometry["features"]:
        county = source_feature["properties"]["county"]
        properties = {
            "id": f"md-moratorium-{source_feature['properties']['geoid']}",
            "record_type": "local_data_center_moratorium",
            "county": county, "geoid": source_feature["properties"]["geoid"],
            "status": "none", "status_label": "No identified action",
            "action_type": None, "legal_instrument": None, "adopted_date": None,
            "effective_date": None, "end_date": None,
            "scope": "No enacted moratorium, pending formal moratorium proposal, or active administrative stop was identified in the reviewed local government records.",
            "source_title": None, "source_url": None, "verified_date": date.today().isoformat(),
        }
        properties.update(ACTIONS.get(county, {}))
        display_geometry = mapping(
            shape(deepcopy(source_feature["geometry"])).simplify(
                DISPLAY_SIMPLIFICATION_DEGREES, preserve_topology=True
            )
        )
        features.append({"type": "Feature", "id": int(properties["geoid"]),
                         "geometry": display_geometry, "properties": properties})
    features.sort(key=lambda feature: feature["properties"]["county"])
    counts = {status: sum(f["properties"]["status"] == status for f in features)
              for status in ("enacted", "pending", "stopped", "none")}
    return {
        "type": "FeatureCollection",
        "metadata": {
            "title": "Maryland local data-center moratorium and stop status",
            "generated_date": date.today().isoformat(), "county_equivalent_count": len(features),
            "status_counts": counts,
            "status_definition": {
                "enacted": "A local legislative body enacted a moratorium or prohibition.",
                "pending": "A formal proposal is before or has been transmitted to a local decision-making body but is not enacted.",
                "stopped": "An executive or administrative action is currently stopping new intake or processing without classification here as enacted legislation.",
                "none": "No qualifying current action was identified; the polygon is transparent.",
            },
            "geometry_source": "U.S. Census Bureau TIGERweb county boundaries, via power-estimates.json",
            "geometry_display_simplification_degrees": DISPLAY_SIMPLIFICATION_DEGREES,
            "policy_method": "Curated from primary local government legislation, resolutions, executive records, and official notices; status verified individually.",
        },
        "features": features,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--geometry", type=Path, default=DEFAULT_GEOMETRY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = generate(args.geometry)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {args.output} with {len(result['features'])} county-equivalent features")


if __name__ == "__main__":
    main()
