#!/usr/bin/env python3
"""Update the unified infrastructure inventory with EIA-derived power plants.

The EIA workbooks are intentionally not committed because each archive is over
20 MB. Download the final annual EIA-860 and EIA-923 archives, extract them,
and pass their plant, generator, and generation/fuel workbooks to this script.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path

import pandas as pd


def clean_number(value, digits=3):
    if pd.isna(value):
        return None
    return round(float(value), digits)


GENERATOR_STATUS_LABELS = {
    "OP": "Operating",
    "SB": "Standby",
    "OA": "Out of service - return expected",
    "OS": "Out of service",
}


def curated_data_center(**values):
    record = {
        "id": None,
        "record_type": "data_center",
        "technology_tags": ["Colocation", "Carrier connectivity", "Diesel backup generation"],
        "name": None,
        "operator": None,
        "owner": None,
        "campus": None,
        "status": "operating",
        "year_built": None,
        "year_built_status": "unknown",
        "year_built_basis": "No authoritative construction year was identified in the reviewed records.",
        "development_status": "operating",
        "permit_status": "historical construction and occupancy permits not researched",
        "air_permit_status": "no facility-specific air-permit decision identified in the reviewed records",
        "legal_status": "no project-specific legal dispute identified in the reviewed records",
        "status_tags": ["Year unknown", "Operating"],
        "year_built_source_ids": [],
        "status_source_ids": [],
        "plan_detail": None,
        "permit_detail": "No current facility-specific government permit package was identified; operator and industry records support the facility listing.",
        "financing_detail": "No facility-specific public financing or tax-exemption award was identified in the reviewed records.",
        "street_address": None,
        "city": None,
        "county": None,
        "state": "MD",
        "postal_code": None,
        "latitude": None,
        "longitude": None,
        "coordinate_method": "Esri World Geocoding Service point-address match",
        "coordinate_checked_date": "2026-08-09",
        "building_count": None,
        "site_acres": None,
        "utility": None,
        "reported_power_capacity_mw": None,
        "reported_power_capacity_basis": None,
        "reported_grid_demand_mw": None,
        "reported_annual_energy_mwh": None,
        "reported_pue": None,
        "on_site_natural_gas_power_plant": "not identified in reviewed records",
        "on_site_generation_capacity_mw": None,
        "on_site_generation_technology": None,
        "backup_generation_fuel": "diesel",
        "backup_generator_count": None,
        "backup_generator_capacity_mw": None,
        "backup_generator_detail": "Backup generators are described by the operator, but a complete count and aggregate rating were not disclosed.",
        "ups_technology": "UPS documented; topology and energy duration not disclosed",
        "ups_capacity_mw": None,
        "ups_energy_mwh": None,
        "cooling_water_detail": None,
        "employees_current": None,
        "employees_committed": None,
        "capital_investment_usd": None,
        "tax_incentive_detail": None,
        "public_funding_detail": None,
        "public_opposition_status": "no facility-specific evidence identified",
        "public_sentiment_score": None,
        "public_sentiment_label": "insufficient evidence",
        "sentiment_basis": "No representative facility-specific public sentiment record was identified.",
        "sentiment_source_ids": [],
        "sentiment_assessed_date": "2026-08-09",
        "sentiment_confidence": "insufficient",
        "contestation_score": 0,
        "contestation_label": "none identified",
        "contestation_category": "none identified",
        "contestation_basis": "A renewed search found no credible facility-specific public, regulatory, or legal controversy.",
        "contestation_source_ids": [],
        "salient_news_source_ids": [],
        "contestation_assessed_date": "2026-08-09",
        "hardware_detail": None,
        "likely_workflows_detail": "Likely regional colocation, network interconnection, managed hosting, private-cloud, and disaster-recovery workloads.",
        "hardware_workflow_basis": "Operator service descriptions support the facility functions; tenant hardware is not publicly inventoried.",
        "profile_source_ids": [],
        "last_verified_date": "2026-08-09",
        "source_ids": [],
        "not_disclosed_fields": [
            "facility grid demand",
            "annual electricity use",
            "PUE",
            "UPS energy duration",
            "current and committed site employment",
            "facility-specific tax benefits",
        ],
        "notes": "Building age and total property area do not establish the age or footprint of the data-center installation within the structure.",
    }
    record.update(values)
    return record


CURATED_DATA_CENTER_ADDITIONS = [
    curated_data_center(
        id="cogent-elkridge",
        name="Cogent Elkridge",
        operator="Cogent Communications (facility service materials remain published after the June 2026 property sale)",
        owner="I Squared Capital-sponsored entity; exact legal entity not disclosed in the reviewed closing announcement",
        year_built=1985,
        year_built_status="documented",
        year_built_basis="A Cogent sale listing reported by Data Center Dynamics identifies 1985 as the building year; SDAT does not publish a YEARBLT value for this parcel.",
        status_tags=["Built 1985", "Operating", "Ownership changed 2026"],
        year_built_source_ids=["dcd-cogent-elkridge-2025", "mdp-sdat-parcel-property"],
        status_source_ids=["cogent-elkridge-brochure-2025", "cogent-elkridge-sale-closing-2026"],
        plan_detail="Carrier-neutral retail and wholesale colocation facility serving the Baltimore-Washington corridor.",
        financing_detail="Cogent sold this facility with nine others to an I Squared Capital-sponsored entity for $225 million in aggregate; no facility allocation was disclosed.",
        street_address="6050 Race Road", city="Elkridge", county="Howard", postal_code="21075",
        latitude=39.203478, longitude=-76.712408, building_count=1, site_acres=5.1,
        utility="CPV Retail Energy / BGE identified in Cogent wholesale materials",
        reported_power_capacity_mw=7.5,
        reported_power_capacity_basis="Cogent reports 7.50 MW of facility power and 6.17 MW of protected power; neither value is measured grid demand.",
        backup_generator_detail="Operator brochure documents multiple diesel generators in 750 kW and 1,500 kW configurations without unit counts.",
        ups_technology="Two 250 kVA UPS units with multiple strings of East Penn AVR95-23 batteries",
        cooling_water_detail="Operator brochure lists multiple HVAC chillers plus water and air handling units; consumption is not disclosed.",
        hardware_detail="61,734-square-foot secure facility with 29,182 square feet of raised floor, 10,131 square feet of non-raised technical space, APC cabinets, wave service, and carrier-neutral connectivity.",
        profile_source_ids=["cogent-elkridge-brochure-2025", "cogent-elkridge-wholesale-2025"],
        source_ids=["cogent-elkridge-brochure-2025", "cogent-elkridge-wholesale-2025", "cogent-elkridge-sale-closing-2026", "dcd-cogent-elkridge-2025", "peeringdb-md-facilities", "mdp-sdat-parcel-property", "esri-world-geocoder"],
        notes="The June 29, 2026 sale transferred the real estate to an unnamed I Squared Capital-sponsored entity. Cogent's current facility materials remain the best public service description, but the post-closing operating arrangement is not disclosed.",
    ),
    curated_data_center(
        id="atlantech-rockville",
        name="Atlantech Online Rockville Data Center",
        operator="Atlantech Online, Inc.", owner=None,
        year_built=1984, year_built_status="documented",
        year_built_basis="The official SDAT parcel record lists 1984 for the structure at 1201 Seven Locks Road; this is not necessarily the first year of data-center service.",
        status_tags=["Built 1984", "Operating"],
        year_built_source_ids=["mdp-sdat-parcel-property"], status_source_ids=["atlantech-data-centers", "atlantech-rockville"],
        plan_detail="Commercial colocation and hosting facility within the Montrose West property.",
        street_address="1201 Seven Locks Road", city="Rockville", county="Montgomery", postal_code="20854",
        latitude=39.064239, longitude=-77.160231,
        hardware_detail="Operator documents colocation, redundant power and cooling, private cages, biometric access, diesel generation, UPS, and carrier connectivity; rack and power totals are not disclosed.",
        profile_source_ids=["atlantech-data-centers", "atlantech-rockville"],
        source_ids=["atlantech-data-centers", "atlantech-rockville", "peeringdb-md-facilities", "mdp-sdat-parcel-property", "esri-world-geocoder"],
    ),
    curated_data_center(
        id="atlantech-silver-spring",
        name="Atlantech Online Silver Spring Data Center",
        operator="Atlantech Online, Inc.", owner=None,
        year_built=1987, year_built_status="documented",
        year_built_basis="The official SDAT parcel record lists 1987 for the structure at 1010 Wayne Avenue; this is not necessarily the first year of data-center service.",
        status_tags=["Built 1987", "Operating"],
        year_built_source_ids=["mdp-sdat-parcel-property"], status_source_ids=["atlantech-data-centers", "atlantech-colocation-terms"],
        plan_detail="Commercial colocation and hosting facility; Atlantech's service terms identify this as its default colocation facility.",
        street_address="1010 Wayne Avenue, Suite 630", city="Silver Spring", county="Montgomery", postal_code="20910",
        latitude=38.993604, longitude=-77.027789,
        hardware_detail="Operator documents escorted access, redundant power grids, diesel generation, UPS, environmental controls, colocation, and hosting; site-specific rack and power totals are not disclosed.",
        profile_source_ids=["atlantech-data-centers", "atlantech-colocation-terms"],
        source_ids=["atlantech-data-centers", "atlantech-colocation-terms", "peeringdb-md-facilities", "mdp-sdat-parcel-property", "esri-world-geocoder"],
    ),
    curated_data_center(
        id="ainet-beltsville",
        name="AiNET Beltsville Data Center",
        operator="AiNET Corporation", owner=None,
        year_built=1978, year_built_status="documented",
        year_built_basis="The official SDAT parcel record lists 1978 for the structure at 11700 Montgomery Road; this is not necessarily the first year of data-center service.",
        status_tags=["Built 1978", "Operating"],
        year_built_source_ids=["mdp-sdat-parcel-property"], status_source_ids=["ainet-cybernap", "peeringdb-md-facilities"],
        plan_detail="AiNET colocation and network facility identified by the operator as an existing Maryland data center.",
        street_address="11700 Montgomery Road", city="Beltsville", county="Prince George's", postal_code="20705",
        latitude=39.052828, longitude=-76.925905,
        hardware_detail="AiNET identifies Beltsville as a colocation location with protected power, carrier connectivity, cloud storage access, and support services; site-specific totals are not disclosed.",
        profile_source_ids=["ainet-cybernap", "ainet-data-center-services"],
        source_ids=["ainet-cybernap", "ainet-global-cloud-connect", "ainet-data-center-services", "peeringdb-md-facilities", "mdp-sdat-parcel-property", "esri-world-geocoder"],
    ),
    curated_data_center(
        id="ainet-laurel",
        name="AiNET Laurel Data Center",
        operator="AiNET Corporation", owner=None,
        status_tags=["Year unknown", "Operating"],
        year_built_source_ids=["mdp-sdat-parcel-property"], status_source_ids=["ainet-cybernap", "peeringdb-md-facilities"],
        plan_detail="AiNET colocation and network facility identified by the operator as an existing Maryland data center.",
        street_address="312 Laurel Avenue", city="Laurel", county="Prince George's", postal_code="20707",
        latitude=39.101395, longitude=-76.84801,
        year_built_basis="The operator and registry establish the facility address, but the point did not intersect a published SDAT parcel year and no authoritative construction year was identified.",
        hardware_detail="AiNET identifies Laurel as a colocation location with protected power, carrier connectivity, cloud storage access, and support services; site-specific totals are not disclosed.",
        profile_source_ids=["ainet-cybernap", "ainet-data-center-services"],
        source_ids=["ainet-cybernap", "ainet-global-cloud-connect", "ainet-data-center-services", "peeringdb-md-facilities", "mdp-sdat-parcel-property", "esri-world-geocoder"],
    ),
    curated_data_center(
        id="ainet-cybernap-glen-burnie",
        name="AiNET CyberNAP",
        operator="AiNET Corporation", owner=None,
        status="listed / operating status not independently verified",
        year_built=1987, year_built_status="documented",
        year_built_basis="The official SDAT parcel record lists 1987 for the large commercial structure at 7900 Ritchie Highway; the data-center fit-out date is not disclosed.",
        development_status="listed / operating status not independently verified",
        status_tags=["Built 1987", "Listed facility", "Operating status unverified"],
        year_built_source_ids=["mdp-sdat-parcel-property"], status_source_ids=["ainet-cybernap", "peeringdb-md-facilities"],
        plan_detail="AiNET describes a 300,000-square-foot carrier-neutral CyberNAP facility with high-density colocation capacity; its operator page retains future-tense opening language, so current operation is not inferred solely from that page.",
        street_address="7900 Ritchie Highway", city="Glen Burnie", county="Anne Arundel", postal_code="21061",
        latitude=39.138531, longitude=-76.605979, site_acres=15,
        reported_power_capacity_mw=80,
        reported_power_capacity_basis="AiNET describes two independent 80 MW utility feeds; this is infrastructure capacity, not operating demand or IT load.",
        hardware_detail="Operator describes a 300,000-square-foot carrier hotel with more than 25 kW-per-cabinet capability, concentric security zones, cloud-storage access, and two independent utility feeds.",
        profile_source_ids=["ainet-cybernap", "ainet-data-center-services"],
        source_ids=["ainet-cybernap", "ainet-global-cloud-connect", "ainet-data-center-services", "peeringdb-md-facilities", "mdp-sdat-parcel-property", "esri-world-geocoder"],
        notes="The parcel structure is larger than AiNET's stated data-center area. The operator page uses future-tense opening language while PeeringDB lists the facility; current operating status therefore remains explicitly unverified.",
    ),
]


CONTESTATION_PROFILES = {
    "aligned-iad04-frederick": {
        "contestation_score": 3,
        "contestation_label": "high",
        "contestation_category": "public and regulatory",
        "contestation_basis": "IAD04 drew adverse permit comments and a split 4-3 planning approval. It is also part of the Quantum Frederick campus at the center of a 21,000-signature referendum campaign, litigation, and a subsequent county development pause; the referendum dispute was campus-wide, not an action against IAD04 alone.",
        "contestation_source_ids": ["mde-aligned-final-determination-2025", "dcd-aligned-planning-approval-2023", "wypr-frederick-referendum-ruling-2026"],
        "salient_news_source_ids": ["wypr-frederick-referendum-ruling-2026", "dcd-aligned-planning-approval-2023"],
    },
    "amazon-bwi150-153-frederick": {
        "contestation_score": 4,
        "contestation_label": "very high",
        "contestation_category": "public, permitting, and legal",
        "contestation_basis": "Amazon's Bauxite I permit for 99 diesel backup generators was highly contested, and the project lies within the Quantum Frederick campus that prompted a 21,000-signature referendum campaign, court proceedings, and a county pause. The referendum concerned the wider data-center zone, not only Amazon.",
        "contestation_source_ids": ["mde-amazon-final-determination-2026", "fnp-amazon-99-generators-2026", "wypr-frederick-referendum-ruling-2026"],
        "salient_news_source_ids": ["fnp-amazon-99-generators-2026", "wypr-frederick-referendum-ruling-2026"],
    },
    "annapolis-state-data-center": {
        "contestation_score": 1,
        "contestation_label": "low",
        "contestation_category": "government modernization policy",
        "contestation_basis": "The reviewed dispute concerns proposed legislation mandating retirement of the state's legacy mainframe environment, not local opposition to the Annapolis facility or its land use.",
        "contestation_source_ids": ["mdh-hb1167-opposition-2026"],
        "salient_news_source_ids": [],
    },
    "atmosphere-dickerson": {
        "contestation_score": 4,
        "contestation_label": "very high",
        "contestation_category": "public, permitting, and legal",
        "contestation_basis": "The proposed 360 MW campus generated organized testimony and county action, was stopped by a permit moratorium and zoning prohibition, and its developer challenged the county's treatment of pending approvals.",
        "contestation_source_ids": ["montgomery-zta-26-01", "dcd-atmosphere-moratorium-challenge-2026", "montgomery-data-center-pause-2026"],
        "salient_news_source_ids": ["dcd-atmosphere-moratorium-challenge-2026", "montgomery-data-center-pause-2026"],
    },
    "brightseat-tech-park-landover": {
        "contestation_score": 4,
        "contestation_label": "very high",
        "contestation_category": "organized public and political",
        "contestation_basis": "Nearly 24,000 petition signatures, rallies, sustained resident opposition, and county moratoria make this one of Maryland's most contested proposals. The evidence is unusually site-specific to the former Landover Mall plan.",
        "contestation_source_ids": ["banner-landover-moratorium-2026", "axios-landover-opposition-2025", "pg-executive-orders-2026"],
        "salient_news_source_ids": ["banner-landover-moratorium-2026", "axios-landover-opposition-2025"],
    },
    "jhu-bayview-research-data-center": {
        "contestation_score": 1,
        "contestation_label": "low / indirect",
        "contestation_category": "citywide policy context",
        "contestation_basis": "The project received public funding while Baltimore debated and enacted a broader pause. No substantial project-specific opposition campaign or legal challenge was found, and statutory research and higher-education exclusions may apply.",
        "contestation_source_ids": ["jhu-bayview-state-grant-2026", "baltimore-ordinance-26-128"],
        "salient_news_source_ids": ["jhu-bayview-state-grant-2026"],
    },
    "ainet-beltsville": {
        "contestation_score": 2,
        "contestation_label": "moderate",
        "contestation_category": "operator and federal-contract legal allegation",
        "contestation_basis": "A federal indictment alleges that a company led by AiNET's founder misrepresented the Beltsville data center's certification in an SEC contract. These remain allegations, not a conviction, and are distinct from public opposition to the site's land use.",
        "contestation_source_ids": ["doj-beltsville-data-center-indictment-2024", "dcd-ainet-beltsville-indictment-2024"],
        "salient_news_source_ids": ["dcd-ainet-beltsville-indictment-2024", "doj-beltsville-data-center-indictment-2024"],
    },
}


def apply_contestation_profile(record):
    defaults = {
        "contestation_score": 0,
        "contestation_label": "none identified",
        "contestation_category": "none identified",
        "contestation_basis": "A renewed search found no credible facility-specific public, regulatory, or legal controversy. Broader jurisdictional policy debates are not attributed to an established facility without site-specific evidence.",
        "contestation_source_ids": [],
        "salient_news_source_ids": [],
        "contestation_assessed_date": "2026-08-09",
    }
    record.update(defaults)
    record.update(CONTESTATION_PROFILES.get(record["id"], {}))
    return record


POWER_SCALE_SOURCE_IDS = {
    "expedient-tide-point": ["expedient-tide-point-spec"],
    "expedient-owings-mills": ["expedient-owings-mills-spec"],
    "databank-bwi1-baltimore": ["databank-bwi1-2020"],
    "databridge-silver-spring": ["databridge-home"],
    "cogent-elkridge": ["cogent-elkridge-wholesale-2025"],
    "ainet-cybernap-glen-burnie": ["ainet-cybernap"],
}


def classify_data_center_power(record):
    demand = record.get("reported_grid_demand_mw")
    capacity = record.get("reported_power_capacity_mw")
    if isinstance(demand, (int, float)):
        value = float(demand)
        value_kind = "reported grid demand"
        tag_prefix = "Draw"
        detail = "Classified from publicly reported normal grid demand."
    elif isinstance(capacity, (int, float)):
        value = float(capacity)
        value_kind = "reported power-capacity proxy"
        tag_prefix = "Power envelope"
        detail = (
            "Classified from a published facility, critical-power, protected-power, or utility-feed capacity. "
            "This is an upper-envelope proxy, not measured operating draw."
        )
    else:
        value = None
        value_kind = "undisclosed"
        tag_prefix = "Power draw"
        detail = (
            "No normal grid-demand or facility power-capacity figure was identified in the reviewed records. "
            "Backup-generator nameplate capacity is intentionally excluded."
        )

    if value is None:
        power_class, label, tag = "unknown", "Undisclosed", f"{tag_prefix} undisclosed"
    elif value < 1:
        power_class, label, tag = "sub-megawatt", "Sub-megawatt", f"{tag_prefix}: under 1 MW"
    elif value < 5:
        power_class, label, tag = "small", "Small", f"{tag_prefix}: 1 to under 5 MW"
    elif value < 20:
        power_class, label, tag = "medium", "Medium", f"{tag_prefix}: 5 to under 20 MW"
    elif value < 100:
        power_class, label, tag = "large", "Large", f"{tag_prefix}: 20 to under 100 MW"
    else:
        power_class, label, tag = "very-large", "Very large", f"{tag_prefix}: 100 MW or more"

    record.update(
        {
            "power_scale_class": power_class,
            "power_scale_label": label,
            "power_scale_mw": value,
            "power_scale_value_kind": value_kind,
            "power_scale_detail": detail,
            "power_scale_tag": tag,
            "power_scale_source_ids": POWER_SCALE_SOURCE_IDS.get(
                record["id"], record.get("profile_source_ids", [])
            ),
        }
    )
    return record


def plant_status_metadata(status_codes):
    labels = [GENERATOR_STATUS_LABELS.get(code, code) for code in status_codes]
    if status_codes == ["OP"]:
        development_status = "operating"
    elif status_codes == ["SB"]:
        development_status = "standby / backup"
    elif status_codes == ["OA"]:
        development_status = "temporarily out of service"
    elif "OP" in status_codes and "SB" in status_codes:
        development_status = "operating with standby generators"
    elif "OP" in status_codes and ({"OA", "OS"} & set(status_codes)):
        development_status = "operating with out-of-service generators"
    else:
        development_status = "mixed operable-generator status"
    return development_status, labels


def coordinate_decimal_places(value):
    return max(0, -Decimal(str(value)).as_tuple().exponent)


def add_coordinate_confidence(records):
    coordinate_counts = Counter((record["latitude"], record["longitude"]) for record in records)
    for record in records:
        latitude_places = coordinate_decimal_places(record["latitude"])
        longitude_places = coordinate_decimal_places(record["longitude"])
        minimum_places = min(latitude_places, longitude_places)
        shared_count = coordinate_counts[(record["latitude"], record["longitude"])]

        if shared_count > 1:
            confidence = "low"
            basis = (
                f"This EIA coordinate is shared by {shared_count} plant records and cannot distinguish "
                "the individual installations; retain wider aerial context."
            )
        elif minimum_places >= 5:
            confidence = "high"
            basis = (
                "Unique EIA coordinate with at least five decimal places in both axes; suitable for tighter "
                "aerial context, but decimal precision is not surveyed accuracy."
            )
        elif minimum_places >= 4:
            confidence = "medium"
            basis = (
                "Unique EIA coordinate with at least four decimal places in both axes; suitable for tighter "
                "aerial context, but may identify the plant, campus, array, or reporting address."
            )
        else:
            confidence = "low"
            basis = (
                "At least one EIA coordinate axis has fewer than four decimal places; retain wider aerial "
                "context until permits, parcels, address records, or visible infrastructure verify the site."
            )

        tight_frame = confidence in {"high", "medium"}
        record.update(
            {
                "coordinate_confidence": confidence,
                "coordinate_confidence_basis": basis,
                "latitude_decimal_places": latitude_places,
                "longitude_decimal_places": longitude_places,
                "shared_coordinate_count": shared_count,
                "aerial_frame_width_m": 700 if tight_frame else 2750,
                "aerial_frame_height_m": 650 if tight_frame else 2000,
            }
        )
    return records


def load_data_centers(output):
    if not output.exists():
        raise SystemExit(
            f"{output} must already contain the curated data-center records before EIA regeneration"
        )
    records = [
        record
        for record in json.loads(output.read_text())
        if record.get("record_type") == "data_center"
    ]
    additions_by_id = {record["id"]: record for record in CURATED_DATA_CENTER_ADDITIONS}
    merged = [additions_by_id.get(record["id"], record) for record in records]
    existing_ids = {record["id"] for record in records}
    merged.extend(record for record in CURATED_DATA_CENTER_ADDITIONS if record["id"] not in existing_ids)
    return [classify_data_center_power(apply_contestation_profile(record)) for record in merged]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plant-workbook", type=Path)
    parser.add_argument("--generator-workbook", type=Path)
    parser.add_argument("--generation-workbook", type=Path)
    parser.add_argument("--year", type=int)
    parser.add_argument("--state", default="MD")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--curated-only", action="store_true", help="refresh curated data-center fields without EIA workbooks")
    args = parser.parse_args()

    if args.curated_only:
        existing = json.loads(args.output.read_text())
        plants = [record for record in existing if record.get("record_type") == "power_plant"]
        args.output.write_text(json.dumps(load_data_centers(args.output) + plants, indent=2) + "\n")
        return

    if not all((args.plant_workbook, args.generator_workbook, args.generation_workbook, args.year)):
        parser.error("EIA workbook paths and --year are required unless --curated-only is used")

    plants = pd.read_excel(args.plant_workbook, sheet_name="Plant", header=1)
    generators = pd.read_excel(args.generator_workbook, sheet_name="Operable", header=1)
    generation = pd.read_excel(
        args.generation_workbook,
        sheet_name="Page 1 Generation and Fuel Data",
        header=5,
    )

    plants = plants[plants["State"] == args.state].copy()
    generators = generators[generators["State"] == args.state].copy()
    generation = generation[generation["Plant State"] == args.state].copy()

    generator_summary = {}
    for plant_code, rows in generators.groupby("Plant Code"):
        capacity = pd.to_numeric(rows["Nameplate Capacity (MW)"], errors="coerce")
        technology_capacity = (
            rows.assign(_capacity=capacity)
            .groupby("Technology", dropna=True)["_capacity"]
            .sum()
            .sort_values(ascending=False)
        )
        primary_technology = technology_capacity.index[0] if len(technology_capacity) else None
        fuels = [str(value) for value in rows["Energy Source 1"].dropna() if str(value).strip()]
        operating_years = pd.to_numeric(rows["Operating Year"], errors="coerce").dropna()
        status_codes = sorted(
            {str(value).strip() for value in rows["Status"].dropna() if str(value).strip()}
        )
        development_status, status_tags = plant_status_metadata(status_codes)
        generator_summary[int(plant_code)] = {
            "nameplate_capacity_mw": clean_number(capacity.sum()),
            "generator_count": int(len(rows)),
            "primary_technology": primary_technology,
            "technology_tags": [str(value) for value in technology_capacity.index],
            "energy_source_codes": sorted(set(fuels)),
            "year_built": int(operating_years.min()) if len(operating_years) else None,
            "generator_status_codes": status_codes,
            "development_status": development_status,
            "status_tags": status_tags,
        }

    generation_summary = {}
    for plant_code, rows in generation.groupby("Plant Id"):
        net = pd.to_numeric(rows["Net Generation\n(Megawatthours)"], errors="coerce")
        fuel_rows = rows.assign(_net=net.fillna(0)).sort_values("_net", ascending=False)
        fuel_codes = [
            str(value)
            for value in fuel_rows["Reported\nFuel Type Code"].dropna()
            if str(value).strip()
        ]
        generation_summary[int(plant_code)] = {
            "net_generation_mwh": clean_number(net.sum(min_count=1)),
            "reported_fuel_codes": list(dict.fromkeys(fuel_codes)),
        }

    records = []
    for _, plant in plants.sort_values(["County", "Plant Name"]).iterrows():
        plant_code = int(plant["Plant Code"])
        generator = generator_summary.get(plant_code, {})
        produced = generation_summary.get(plant_code, {})
        if not generator:
            continue
        records.append(
            {
                "id": f"eia-{plant_code}",
                "record_type": "power_plant",
                "eia_plant_code": plant_code,
                "name": str(plant["Plant Name"]).strip(),
                "operator": str(plant["Utility Name"]).strip(),
                "street_address": None if pd.isna(plant["Street Address"]) else str(plant["Street Address"]).strip(),
                "city": None if pd.isna(plant["City"]) else str(plant["City"]).strip(),
                "county": None if pd.isna(plant["County"]) else str(plant["County"]).strip(),
                "state": args.state,
                "postal_code": None if pd.isna(plant["Zip"]) else str(plant["Zip"]).strip(),
                "latitude": clean_number(plant["Latitude"], 6),
                "longitude": clean_number(plant["Longitude"], 6),
                "primary_technology": generator.get("primary_technology"),
                "technology_tags": generator.get("technology_tags", []),
                "energy_source_codes": generator.get("energy_source_codes", []),
                "nameplate_capacity_mw": generator.get("nameplate_capacity_mw"),
                "generator_count": generator.get("generator_count"),
                "net_generation_mwh": produced.get("net_generation_mwh"),
                "generation_year": args.year,
                "generation_fuel_codes": produced.get("reported_fuel_codes", []),
                "year_built": generator.get("year_built"),
                "year_built_status": "documented" if generator.get("year_built") else "unknown",
                "year_built_basis": (
                    "Earliest operating year among the plant's operable generators in final "
                    f"{args.year} Form EIA-860. This is not necessarily the construction year of every structure."
                ),
                "development_status": generator.get("development_status"),
                "generator_status_codes": generator.get("generator_status_codes", []),
                "status_tags": generator.get("status_tags", []),
                "permit_status": "not researched at plant level",
                "air_permit_status": "not included in this inventory; Form EIA-860 does not report air-permit decisions",
                "legal_status": "not researched at plant level",
                "year_built_source_ids": [f"eia-860-{args.year}-final"],
                "status_source_ids": [f"eia-860-{args.year}-final"],
                "capacity_source_id": f"eia-860-{args.year}-final",
                "generation_source_id": f"eia-923-{args.year}-final",
            }
        )

    add_coordinate_confidence(records)
    infrastructure = load_data_centers(args.output) + records
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(infrastructure, indent=2, ensure_ascii=False) + "\n")
    technologies = Counter(record["primary_technology"] for record in records)
    print(f"Wrote {len(infrastructure)} infrastructure records ({len(records)} plants) to {args.output}")
    print("Technologies:", dict(technologies.most_common()))


if __name__ == "__main__":
    main()
