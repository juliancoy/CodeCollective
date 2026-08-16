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


MARYLAND_ALL_SECTOR_PRICE_CENTS_PER_KWH_2024 = 15.04
MARYLAND_ALL_SECTOR_PRICE_SOURCE_ID = "eia-retail-sales-md-all-sectors-2024"
HOURS_IN_2024 = 8784


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
        "estimated_power_draw_mw": None,
        "estimated_power_draw_basis": None,
        "estimated_power_draw_confidence": None,
        "estimated_power_draw_source_ids": [],
        "projected_power_demand_mw": None,
        "projected_power_demand_basis": None,
        "projected_power_demand_confidence": None,
        "projected_power_demand_source_ids": [],
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
        "funding_summary": "No facility-specific funder breakdown was identified in the reviewed records.",
        "funding_total_known_usd": None,
        "funding_breakdown": [],
        "funding_source_ids": [],
        "operational_finance_summary": "No facility-specific operating-cost, revenue, or tax-payment detail was isolated in the reviewed records.",
        "estimated_annual_electricity_use_mwh": None,
        "estimated_annual_electricity_cost_usd": None,
        "electricity_cost_rate_cents_per_kwh": None,
        "electricity_cost_basis": None,
        "operational_finance_items": [],
        "operational_finance_source_ids": [],
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
            "facility-specific funder breakdown",
            "facility-specific operating revenue",
            "facility-specific tax payments",
            "facility-specific power purchase agreement or tariff",
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
    curated_data_center(
        id="ainet-one-market-center-baltimore",
        name="AiNET One Market Center",
        operator="AiNET",
        owner=None,
        status_tags=["Year unknown", "Operating", "Directory listed"],
        status_source_ids=["datacentermap-baltimore-2026"],
        plan_detail="Directory-listed colocation and connectivity facility in the 300 West Lexington carrier-hotel building.",
        street_address="300 West Lexington Street", city="Baltimore", county="Baltimore City", postal_code="21201",
        latitude=39.2917, longitude=-76.620038,
        coordinate_method="shared point-address match from existing 300 West Lexington record",
        hardware_detail="DataCenterMap describes One Market Center as a major connected Baltimore colocation facility; site-specific rack count, IT load, and metered demand were not found.",
        hardware_workflow_basis="Directory listing supports the facility identity and colocation/connectivity function; demand and tenant hardware remain estimated.",
        profile_source_ids=["datacentermap-baltimore-2026"],
        source_ids=["datacentermap-baltimore-2026"],
        notes="Shares the 300 West Lexington carrier-hotel building with other listed providers; retained as a separate operator/listing record.",
    ),
    curated_data_center(
        id="crown-castle-baltimore",
        name="Crown Castle Baltimore",
        operator="Crown Castle",
        owner=None,
        status_tags=["Year unknown", "Operating", "Directory listed"],
        status_source_ids=["datacentermap-baltimore-2026"],
        plan_detail="Directory-listed network and colocation presence at 111 Market Place.",
        street_address="111 Market Place", city="Baltimore", county="Baltimore City", postal_code="21202",
        latitude=39.2874338, longitude=-76.6063475,
        coordinate_method="OpenStreetMap Nominatim point-address match",
        hardware_detail="DataCenterMap describes a high-capacity transport and fiber-network provider presence serving Baltimore, Washington, D.C., and Delmarva; facility power totals are not disclosed.",
        hardware_workflow_basis="Directory listing supports the network/facility presence; data-center load is estimated at network-room scale.",
        profile_source_ids=["datacentermap-baltimore-2026"],
        source_ids=["datacentermap-baltimore-2026", "openstreetmap-nominatim-geocoder"],
        notes="Shares the 111 Market Place / Candler Building location with other directory listings; retained as a separate provider/listing record.",
    ),
    curated_data_center(
        id="databank-111-market-place",
        name="DataBank - 111 Market Place",
        operator="DataBank",
        owner=None,
        status_tags=["Year unknown", "Operating", "Directory listed"],
        status_source_ids=["datacentermap-baltimore-2026"],
        plan_detail="Directory-listed downtown Baltimore connectivity facility with metro interconnects to 300 West Lexington.",
        street_address="111 Market Place", city="Baltimore", county="Baltimore City", postal_code="21202",
        latitude=39.2874338, longitude=-76.6063475,
        coordinate_method="OpenStreetMap Nominatim point-address match",
        hardware_detail="DataCenterMap describes direct connections to nine carriers and metro interconnects to DataBank BWI1 at 300 West Lexington; rack count and power totals are not disclosed.",
        hardware_workflow_basis="Directory listing supports the connectivity role; power draw is estimated because no metered or capacity figure was found.",
        profile_source_ids=["datacentermap-baltimore-2026"],
        source_ids=["datacentermap-baltimore-2026", "openstreetmap-nominatim-geocoder"],
        notes="Shares the Candler Building address with other directory-listed providers; retained separately because DataCenterMap lists it separately.",
    ),
    curated_data_center(
        id="infradms-bal01-baltimore",
        name="InfraDMS BAL01",
        operator="InfraDMS",
        owner=None,
        status_tags=["Year unknown", "Operating", "Directory listed"],
        status_source_ids=["datacentermap-baltimore-2026"],
        plan_detail="Directory-listed infrastructure-services data center at One South Street.",
        street_address="1 South Street", city="Baltimore", county="Baltimore City", postal_code="21202",
        latitude=39.2893325, longitude=-76.6105729,
        coordinate_method="OpenStreetMap Nominatim point-address match",
        reported_power_capacity_mw=0.65,
        reported_power_capacity_basis="DataCenterMap directory description says facility highlights include up to 650 kW of power; this is capacity, not metered draw.",
        backup_generator_count=2,
        backup_generator_capacity_mw=1.5,
        backup_generator_detail="Directory description reports dual 750 kW generators.",
        hardware_detail="Directory description reports up to 650 kW of power, dual 750 kW generators, and redundant Liebert systems.",
        hardware_workflow_basis="Directory listing supports facility identity and power-envelope figures; measured grid demand remains estimated.",
        profile_source_ids=["datacentermap-baltimore-2026"],
        source_ids=["datacentermap-baltimore-2026", "openstreetmap-nominatim-geocoder"],
    ),
    curated_data_center(
        id="amazon-cronridge-owings-mills",
        name="Amazon AWS - 11550 Cronridge Drive",
        operator="Amazon AWS",
        owner="Amazon AWS / acquired facility according to directory listing",
        status="directory listed / operating status not independently verified",
        development_status="directory listed / operating status not independently verified",
        status_tags=["Year unknown", "Directory listed", "Operating status unverified"],
        status_source_ids=["datacentermap-baltimore-2026"],
        plan_detail="DataCenterMap lists the Owings Mills Cronridge Drive property as an Amazon AWS acquired data-center facility.",
        street_address="11550 Cronridge Drive", city="Owings Mills", county="Baltimore", postal_code="21117",
        latitude=39.442891, longitude=-76.7721384,
        coordinate_method="OpenStreetMap Nominatim point-address match",
        hardware_detail="Directory listing identifies an acquired Amazon AWS data-center facility; public rack, generator, and grid-demand details were not found in the reviewed listing.",
        likely_workflows_detail="Likely AWS cloud infrastructure if the directory listing is current; workload attribution is an operator inference, not a site-specific disclosure.",
        hardware_workflow_basis="Directory listing supports the facility identity; AWS workload description is an operator inference.",
        profile_source_ids=["datacentermap-baltimore-2026"],
        source_ids=["datacentermap-baltimore-2026", "openstreetmap-nominatim-geocoder"],
    ),
    curated_data_center(
        id="woodlawn-drive-1500-proposal",
        name="1500 Woodlawn Drive data center proposal",
        operator="Unknown Company",
        owner=None,
        status="proposed / directory listed",
        development_status="proposed",
        status_tags=["Not built", "Proposed", "Directory listed"],
        status_source_ids=["datacentermap-baltimore-2026"],
        plan_detail="DataCenterMap describes a proposed 150 MW data-center campus on a 42-acre Baltimore County site with construction expected in June or July 2026.",
        street_address="1500 Woodlawn Drive", city="Baltimore", county="Baltimore", postal_code="21241",
        latitude=39.307986, longitude=-76.7385748,
        coordinate_method="OpenStreetMap Nominatim point-address match",
        site_acres=42,
        reported_power_capacity_mw=150,
        reported_power_capacity_basis="DataCenterMap directory description reports a proposed 150 MW campus; this is planning-scale capacity, not measured demand.",
        hardware_detail="Directory description identifies a proposed 150 MW campus and planned donation of five acres for an electrical substation; no tenant hardware was disclosed.",
        likely_workflows_detail="Likely hyperscale or large enterprise/cloud workloads if built, inferred from the proposed 150 MW campus scale.",
        hardware_workflow_basis="Directory listing supports the proposal scale; workload is a scale-based inference.",
        public_opposition_status="not researched beyond directory listing",
        public_sentiment_label="insufficient evidence",
        sentiment_basis="No facility-specific public sentiment review has been completed for this newly added directory listing.",
        profile_source_ids=["datacentermap-baltimore-2026"],
        source_ids=["datacentermap-baltimore-2026", "openstreetmap-nominatim-geocoder"],
    ),
    curated_data_center(
        id="comcast-nottingham",
        name="Comcast Nottingham",
        operator="Comcast",
        owner=None,
        status_tags=["Year unknown", "Directory listed"],
        status_source_ids=["datacentermap-baltimore-2026"],
        plan_detail="Directory-listed Comcast facility in Nottingham / White Marsh.",
        street_address="8031 Corporate Drive", city="Nottingham", county="Baltimore", postal_code="21236",
        latitude=39.3687901, longitude=-76.4671785,
        coordinate_method="OpenStreetMap Nominatim point-address match",
        hardware_detail="DataCenterMap lists a Comcast Nottingham profile but does not disclose site-specific power, rack, UPS, or generator details in the Baltimore listing.",
        likely_workflows_detail="Likely cable/network headend, transport, edge compute, and enterprise infrastructure support, inferred from Comcast operator identity.",
        hardware_workflow_basis="Directory listing supports the facility identity; workflow is an operator inference.",
        profile_source_ids=["datacentermap-baltimore-2026"],
        source_ids=["datacentermap-baltimore-2026", "openstreetmap-nominatim-geocoder"],
    ),
    curated_data_center(
        id="gi-partners-eternal-rings-laurel",
        name="9800 South Eternal Rings Drive",
        operator="GI Partners",
        owner="GI Partners",
        status="directory listed / hyperscale powered shell",
        development_status="directory listed / hyperscale powered shell",
        status_tags=["Year unknown", "Directory listed", "Powered shell"],
        status_source_ids=["datacentermap-baltimore-2026"],
        plan_detail="DataCenterMap describes a hyperscale powered-shell data center in Laurel, part of a 218,000-square-foot development on 95 acres.",
        street_address="9800 South Eternal Rings Drive", city="Laurel", county="Howard", postal_code="20723",
        latitude=39.1335439, longitude=-76.8515612,
        coordinate_method="OpenStreetMap Nominatim point-address match",
        site_acres=95,
        hardware_detail="Directory listing describes a hyperscale powered shell designed for cloud and computing contracts; no public metered demand or tenant hardware inventory was found.",
        likely_workflows_detail="Likely hyperscale cloud or high-density compute workloads, inferred from powered-shell scale and directory description.",
        hardware_workflow_basis="Directory listing supports the powered-shell identity and scale; power draw and workloads remain estimated.",
        profile_source_ids=["datacentermap-baltimore-2026"],
        source_ids=["datacentermap-baltimore-2026", "openstreetmap-nominatim-geocoder"],
    ),
    curated_data_center(
        id="gi-partners-sandy-farm-severn",
        name="7665 Sandy Farm Road",
        operator="GI Partners",
        owner="GI Partners",
        status="directory listed / hyperscale powered shell",
        development_status="directory listed / hyperscale powered shell",
        status_tags=["Year unknown", "Directory listed", "Powered shell", "Fully leased"],
        status_source_ids=["datacentermap-baltimore-2026"],
        plan_detail="DataCenterMap describes a hyperscale powered-shell data center in Severn developed for cloud and computing contracts and fully leased.",
        street_address="7665 Sandy Farm Road", city="Severn", county="Anne Arundel", postal_code="21144",
        latitude=39.1485935, longitude=-76.6846043,
        coordinate_method="OpenStreetMap Nominatim point-address match",
        hardware_detail="Directory listing describes a fully leased hyperscale powered shell for cloud and computing contracts; no public metered demand or tenant hardware inventory was found.",
        likely_workflows_detail="Likely hyperscale cloud or high-density compute workloads, inferred from powered-shell scale and directory description.",
        hardware_workflow_basis="Directory listing supports the powered-shell identity and lease status; power draw and workloads remain estimated.",
        profile_source_ids=["datacentermap-baltimore-2026"],
        source_ids=["datacentermap-baltimore-2026", "openstreetmap-nominatim-geocoder"],
    ),
    curated_data_center(
        id="lumen-baltimore",
        name="Lumen Baltimore",
        operator="Lumen",
        owner=None,
        status_tags=["Year unknown", "Operating", "Directory listed"],
        status_source_ids=["datacentermap-baltimore-2026"],
        plan_detail="Directory-listed Lumen facility/presence at 300 West Lexington Street.",
        street_address="300 West Lexington Street", city="Baltimore", county="Baltimore City", postal_code="21201",
        latitude=39.2917, longitude=-76.620038,
        coordinate_method="shared point-address match from existing 300 West Lexington record",
        hardware_detail="DataCenterMap lists Lumen Baltimore at 300 West Lexington; site-specific power, rack, UPS, and generator details were not disclosed in the listing.",
        likely_workflows_detail="Likely network transport, carrier interconnection, edge compute, and enterprise connectivity workloads.",
        hardware_workflow_basis="Directory listing supports the facility identity; workload is an operator inference.",
        profile_source_ids=["datacentermap-baltimore-2026"],
        source_ids=["datacentermap-baltimore-2026"],
        notes="Shares the 300 West Lexington carrier-hotel building with other listed providers; retained as a separate provider/listing record.",
    ),
    curated_data_center(
        id="candler-building-baltimore",
        name="Candler Building",
        operator="Unknown Company",
        owner=None,
        status_tags=["Year unknown", "Operating", "Directory listed"],
        status_source_ids=["datacentermap-baltimore-2026"],
        plan_detail="Directory-listed data-center/candler-building entry at 111 Market Place.",
        street_address="111 Market Place", city="Baltimore", county="Baltimore City", postal_code="21202",
        latitude=39.2874338, longitude=-76.6063475,
        coordinate_method="OpenStreetMap Nominatim point-address match",
        hardware_detail="DataCenterMap lists a Candler Building data-center entry but does not disclose operator, power, rack, UPS, or generator details in the Baltimore listing.",
        hardware_workflow_basis="Directory listing supports the location listing only; power draw and workflows are low-confidence estimates.",
        profile_source_ids=["datacentermap-baltimore-2026"],
        source_ids=["datacentermap-baltimore-2026", "openstreetmap-nominatim-geocoder"],
        notes="Shares the 111 Market Place / Candler Building location with other provider listings; retained because DataCenterMap lists it separately.",
    ),
    curated_data_center(
        id="fannie-mae-urbana-tech-center",
        name="Fannie Mae Urbana Technology Center",
        operator="Fannie Mae",
        owner="Fannie Mae",
        year_built=2004,
        year_built_status="documented",
        year_built_basis="JLL sale materials for the Fannie Mae Tech Center list original construction in 2004.",
        development_status="operating / offered for sale",
        status="operating / offered for sale",
        permit_status="operating facility; no current expansion permit decision identified in the reviewed records",
        legal_status="no project-specific legal dispute identified in the reviewed records",
        status_tags=["Built 2004", "Operating", "Offered for sale 2026"],
        year_built_source_ids=["jll-fannie-mae-tech-center-2026"],
        status_source_ids=["frederick-oed-data-centers-2026", "fannie-mae-contact-urbana-tech-center", "jll-fannie-mae-tech-center-2026"],
        plan_detail="Existing Tier III-equivalent enterprise data center with expansion capacity in the existing improvements and an adjacent undeveloped parcel marketed for possible future data-center development.",
        permit_detail="No current facility-specific government expansion permit was identified; JLL describes expansion potential and near-term power availability rather than an issued construction approval.",
        financing_detail="JLL states Fannie Mae is migrating operations to the cloud and intends to divest the Tech Center by year-end 2026; no facility-specific public financing was identified.",
        street_address="9107 Bennett Creek Boulevard",
        city="Frederick",
        county="Frederick",
        postal_code="21704",
        latitude=39.322492,
        longitude=-77.34973,
        coordinate_method="U.S. Census Geocoder street-segment match",
        coordinate_checked_date="2026-08-10",
        building_count=1,
        site_acres=37.26,
        reported_power_capacity_mw=9.8,
        reported_power_capacity_basis="JLL reports 4.3 MW installed critical capacity plus 5.5 MW expansion capacity in existing improvements; this is a facility capacity envelope, not metered demand.",
        backup_generation_fuel="diesel (reported by earlier technical coverage; current official sale materials reviewed here do not enumerate generators)",
        backup_generator_detail="Earlier specialist coverage reported six 2 MW generators; current Fannie Mae and JLL materials reviewed for this update do not publish a generator schedule.",
        ups_technology="UPS system present by data-center design implication; topology and rating not disclosed in the reviewed owner/broker materials.",
        cooling_water_detail="Frederick OED describes redundant utility feeds including water; detailed water consumption was not disclosed.",
        hardware_detail="Frederick OED describes a 220,000-square-foot facility with 90,000 square feet of office space, 60,000 square feet of data-center space, and a 70,000-square-foot MEP facility. JLL lists 245,000 gross square feet, Tier III-equivalent rating, 4.3 MW installed critical capacity, and 5.5 MW expansion capacity.",
        likely_workflows_detail="Enterprise mortgage-finance technology operations and disaster-recovery workloads; JLL states Fannie Mae is migrating operations to the cloud before disposition.",
        hardware_workflow_basis="Fannie Mae owns and lists the Urbana Technology Center; Frederick OED and JLL describe it as an existing data center.",
        profile_source_ids=["frederick-oed-data-centers-2026", "fannie-mae-contact-urbana-tech-center", "jll-fannie-mae-tech-center-2026"],
        source_ids=["frederick-oed-data-centers-2026", "fannie-mae-contact-urbana-tech-center", "jll-fannie-mae-tech-center-2026", "census-geocoder"],
        notes="Frederick OED and JLL report different gross-area figures. Both are retained in the narrative rather than collapsed into a single asserted area.",
    ),
    curated_data_center(
        id="ssa-national-support-center-urbana",
        name="Social Security Administration National Support Center",
        operator="Social Security Administration",
        owner="U.S. General Services Administration",
        year_built=2014,
        year_built_status="documented",
        year_built_basis="Public project profiles and 2014 opening coverage identify the facility as newly opened in 2014.",
        development_status="operating",
        status="operating",
        permit_status="operating federal facility; no current local data-center expansion permit identified in the reviewed records",
        legal_status="no project-specific legal dispute identified in the reviewed records",
        status_tags=["Built 2014", "Operating", "Federal facility", "LEED Gold"],
        year_built_source_ids=["southland-ssa-national-support-center", "som-ssa-national-support-center"],
        status_source_ids=["frederick-oed-data-centers-2026", "southland-ssa-national-support-center"],
        plan_detail="Federal Tier III National Support Center replacing the former National Computer Center and supporting core SSA data operations.",
        permit_detail="No current facility-specific air-permit or development dispute was identified; this is an established federal facility.",
        financing_detail="Federal facility delivered for the U.S. General Services Administration; no local data-center incentive award was identified in the reviewed records.",
        street_address="8999 Bennett Creek Boulevard",
        city="Frederick",
        county="Frederick",
        postal_code="21704",
        latitude=39.316723,
        longitude=-77.351526,
        coordinate_method="U.S. Census Geocoder street-segment match",
        coordinate_checked_date="2026-08-10",
        building_count=1,
        site_acres=63,
        reported_power_capacity_mw=10,
        reported_power_capacity_basis="Southland reports the facility supports approximately 10 MW of IT server load; this is a published IT-load figure, not metered utility demand.",
        backup_generation_fuel="not disclosed in reviewed records",
        backup_generator_detail="Project profiles identify an energy center and resilient federal data-center design but do not disclose a generator count or aggregate generator rating.",
        ups_technology="Tier III data-center UPS equivalent expected; topology and rating not disclosed in reviewed records.",
        cooling_water_detail="Southland reports five independent 100,000-gallon below-grade cooling-tower make-up-water sumps, designed to provide at least three days of cooling-tower make-up water if main water service fails.",
        employees_current=80,
        employees_committed=80,
        hardware_detail="Southland describes a 275,000-square-foot Tier III data center with IT white space, office building, access-control center, approximately 10 MW of IT server load, and roughly 80 employees. SOM describes a 285,000-square-foot facility on 63 acres.",
        likely_workflows_detail="Federal demographic, wage, earnings, benefits, and payment-support data processing for Social Security Administration operations.",
        hardware_workflow_basis="Frederick OED and Southland state the facility maintains earnings, wage, demographic, and benefits information and processes high-volume SSA transactions.",
        profile_source_ids=["frederick-oed-data-centers-2026", "southland-ssa-national-support-center", "som-ssa-national-support-center"],
        source_ids=["frederick-oed-data-centers-2026", "southland-ssa-national-support-center", "som-ssa-national-support-center", "census-geocoder"],
        notes="Frederick OED, Southland, DBIA, and SOM publish slightly different floor-area figures; this record uses Southland's 275,000-square-foot operational profile and retains SOM's 285,000-square-foot figure in the narrative.",
    ),
    curated_data_center(
        id="rowan-bauxite-ii-frederick",
        name="Rowan Bauxite II Data Center",
        operator="Rowan Digital Infrastructure",
        owner="Rowan Digital Infrastructure",
        campus="Quantum Frederick",
        status="site plan approved / planned",
        development_status="site plan approved / planned",
        permit_status="Frederick County Planning Commission agenda identified a site-plan decision for SP22-04 / AP SP276740 on December 11, 2024; no facility-specific MDE air permit package was identified in the reviewed records.",
        legal_status="campus-wide referendum litigation resolved against referendum petitioners; no Bauxite II-specific legal dispute identified in the reviewed records",
        status_tags=["Year unknown", "Planning approved", "Planned", "Quantum Frederick"],
        status_source_ids=["frederick-planning-bauxite-ii-iii-2024", "dcd-rowan-bauxite-ii-iii-approval-2024", "mde-frederick-data-center-hub"],
        plan_detail="Frederick County Planning Commission agenda describes Bauxite II Data Center, Quantum Frederick Section 1, Lot 302, as an 822,620-square-foot Critical Digital Infrastructure Facility on a 111.50-acre site south and west of New Design Road and Manor Woods Road.",
        permit_detail="Local site-plan decision documented; MDE's Frederick data-center hub lists Rowan Bauxite environmental documents but no Bauxite II air-permit decision in the reviewed index.",
        financing_detail="No Bauxite II-specific public financing record was identified in the reviewed records; DCD attributes the project to Rowan at Quantum Frederick.",
        street_address="New Design Road and Manor Woods Road",
        city="Frederick",
        county="Frederick",
        postal_code="21703",
        latitude=39.331036,
        longitude=-77.454889,
        coordinate_method="U.S. Census Geocoder intersection match for planning-agenda location",
        coordinate_checked_date="2026-08-10",
        site_acres=111.5,
        building_count=4,
        reported_power_capacity_mw=None,
        reported_power_capacity_basis="No Bauxite II-specific power capacity was found in the reviewed official agenda or MDE hub.",
        backup_generation_fuel="not disclosed in reviewed records",
        backup_generator_detail="No facility-specific backup-generator count or rating was identified in the reviewed Bauxite II records.",
        ups_technology="UPS likely for hyperscale data-center design, but topology and rating were not disclosed in the reviewed records.",
        hardware_detail="Planned 822,620-square-foot critical digital infrastructure facility; DCD reports it as Rowan's second adjacent Bauxite project at Quantum Frederick.",
        likely_workflows_detail="Likely hyperscale cloud or AI infrastructure for a large tenant; tenant and hardware inventory not disclosed.",
        hardware_workflow_basis="Inferred from Rowan hyperscale campus context and critical digital infrastructure site-plan description.",
        profile_source_ids=["frederick-planning-bauxite-ii-iii-2024", "dcd-rowan-bauxite-ii-iii-approval-2024", "mde-frederick-data-center-hub"],
        source_ids=["frederick-oed-data-centers-2026", "frederick-planning-bauxite-ii-iii-2024", "dcd-rowan-bauxite-ii-iii-approval-2024", "mde-frederick-data-center-hub", "census-geocoder"],
    ),
    curated_data_center(
        id="rowan-bauxite-iii-frederick",
        name="Rowan Bauxite III Data Center",
        operator="Rowan Digital Infrastructure",
        owner="Rowan Digital Infrastructure",
        campus="Quantum Frederick",
        status="site plan approved / planned",
        development_status="site plan approved / planned",
        permit_status="Frederick County Planning Commission agenda identified a site-plan decision for SP22-04 / AP SP276843 on December 11, 2024; MDE lists Bauxite III environmental management and sampling documents.",
        legal_status="campus-wide referendum litigation resolved against referendum petitioners; no Bauxite III-specific legal dispute identified in the reviewed records",
        status_tags=["Year unknown", "Planning approved", "Planned", "Quantum Frederick", "Environmental management plan"],
        status_source_ids=["frederick-planning-bauxite-ii-iii-2024", "dcd-rowan-bauxite-ii-iii-approval-2024", "mde-frederick-data-center-hub"],
        plan_detail="Frederick County Planning Commission agenda describes Bauxite III Data Center, Quantum Frederick Section 1, Lot 102, as a 591,913-square-foot Critical Digital Infrastructure Facility on a 55.08-acre site south and east of Ballenger Creek Pike and Manor Woods Road.",
        permit_detail="Local site-plan decision documented. MDE states Bauxite III is the only Rowan Bauxite parcel within the former Eastalco operations boundary and has state-overseen environmental management plans for remediation and redevelopment.",
        financing_detail="No Bauxite III-specific public financing record was identified in the reviewed records; DCD attributes the project to Rowan at Quantum Frederick.",
        street_address="Ballenger Creek Pike and Manor Woods Road",
        city="Frederick",
        county="Frederick",
        postal_code="21703",
        latitude=39.321172,
        longitude=-77.488391,
        coordinate_method="Approximate intersection point from published Bauxite III vicinity descriptions and U.S. Census Geocoder",
        coordinate_checked_date="2026-08-10",
        site_acres=55.08,
        building_count=3,
        reported_power_capacity_mw=None,
        reported_power_capacity_basis="No Bauxite III-specific power capacity was found in the reviewed official agenda or MDE hub.",
        backup_generation_fuel="not disclosed in reviewed records",
        backup_generator_detail="No facility-specific backup-generator count or rating was identified in the reviewed Bauxite III records.",
        ups_technology="UPS likely for hyperscale data-center design, but topology and rating were not disclosed in the reviewed records.",
        hardware_detail="Planned 591,913-square-foot critical digital infrastructure facility; DCD reports it as Rowan's third adjacent Bauxite project at Quantum Frederick.",
        likely_workflows_detail="Likely hyperscale cloud or AI infrastructure for a large tenant; tenant and hardware inventory not disclosed.",
        hardware_workflow_basis="Inferred from Rowan hyperscale campus context and critical digital infrastructure site-plan description.",
        profile_source_ids=["frederick-planning-bauxite-ii-iii-2024", "dcd-rowan-bauxite-ii-iii-approval-2024", "mde-frederick-data-center-hub"],
        source_ids=["frederick-oed-data-centers-2026", "frederick-planning-bauxite-ii-iii-2024", "dcd-rowan-bauxite-ii-iii-approval-2024", "mde-frederick-data-center-hub", "census-geocoder"],
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
    "rowan-bauxite-ii-frederick": {
        "contestation_score": 3,
        "contestation_label": "high",
        "contestation_category": "campus-wide public and legal",
        "contestation_basis": "No Bauxite II-specific litigation was identified, but it is part of the Quantum Frederick campus that generated a 21,000-signature referendum campaign, litigation, and county development restrictions. DCD also notes the applications advanced through a public Planning Commission process.",
        "contestation_source_ids": ["frederick-planning-bauxite-ii-iii-2024", "dcd-rowan-bauxite-ii-iii-approval-2024", "wypr-frederick-referendum-ruling-2026"],
        "salient_news_source_ids": ["dcd-rowan-bauxite-ii-iii-approval-2024", "wypr-frederick-referendum-ruling-2026"],
    },
    "rowan-bauxite-iii-frederick": {
        "contestation_score": 3,
        "contestation_label": "high",
        "contestation_category": "campus-wide public, legal, and environmental-management context",
        "contestation_basis": "No Bauxite III-specific litigation was identified, but it is part of the Quantum Frederick campus that generated a 21,000-signature referendum campaign, litigation, and county development restrictions. MDE also identifies Bauxite III as the Rowan parcel within the former Eastalco operations boundary with environmental management plans.",
        "contestation_source_ids": ["frederick-planning-bauxite-ii-iii-2024", "dcd-rowan-bauxite-ii-iii-approval-2024", "mde-frederick-data-center-hub", "wypr-frederick-referendum-ruling-2026"],
        "salient_news_source_ids": ["dcd-rowan-bauxite-ii-iii-approval-2024", "wypr-frederick-referendum-ruling-2026"],
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


DATA_CENTER_RECORD_UPDATES = {
    "aligned-iad04-frederick": {
        "street_address": "5601 Manor Woods Road",
        "postal_code": "21703",
        "ups_technology": "Aligned markets 2 MW UPS line-ups for IAD-04; detailed topology and energy duration are not disclosed.",
        "hardware_detail": (
            "Planned hyperscale shells for high-density rack deployments. Aligned's Frederick County page identifies "
            "IAD-04 at 5601 Manor Woods Road on a 75-acre campus designed to Tier III standards, with 3 MW backup "
            "generators, 2 MW UPS line-ups, N+1 block redundancy, 500 kVA PDUs, 415V distribution, Delta3 air cooling, "
            "and DeltaFlow liquid-cooling taps. Maryland permit records remain the source for the full backup-generator fleet."
        ),
        "profile_source_ids": ["aligned-maryland-data-centers", "mde-aligned-issued-air-permit-2025", "mde-aligned-air-permit-application", "mde-frederick-data-center-hub"],
        "source_ids": ["aligned-maryland-data-centers", "frederick-oed-data-centers-2026", "mde-aligned-issued-air-permit-2025", "mde-aligned-final-determination-2025", "mde-aligned-air-permit-application", "frederick-planning-sp275110-2023", "esri-world-geocoder"],
    },
    "amazon-bwi150-153-frederick": {
        "plan_detail": "Amazon Data Services BWI-150 through BWI-153 corresponds to Rowan's Bauxite I development phase within Quantum Frederick, documented in MDE air-permit records as a four-building data-center campus at 3250 Digital Drive.",
        "source_ids": ["mde-amazon-issued-air-permit-2026", "mde-amazon-final-determination-2026", "mde-amazon-air-permit-application", "mde-frederick-data-center-hub", "frederick-oed-data-centers-2026", "esri-world-geocoder"],
        "profile_source_ids": ["aws-global-infrastructure", "mde-amazon-issued-air-permit-2026", "mde-amazon-air-permit-application", "mde-frederick-data-center-hub", "frederick-oed-data-centers-2026"],
    },
    "atmosphere-dickerson": {
        "building_count": 5,
        "plan_detail": "Proposed 360 MW hyperscale campus at the former Dickerson Power Plant site. DCD reports five 226,850-square-foot data-center buildings, and the existing record also tracks the paired battery-energy-storage component described in county and state review materials.",
        "permit_detail": "A Montgomery County conditional-use case and MDE NPDES application 26-DP-3903 entered review. DCD reports the moratorium stopped processing of the stormwater management concept plan and fire access plan; on July 28, 2026 the County Council approved ZTA 26-01 prohibiting large data centers countywide, including this proposal.",
        "legal_status": "DCD reports Atmosphere challenged Montgomery County's six-month data-center permit moratorium after County Executive Marc Elrich issued it on June 12, 2026. Montgomery County also enacted Ordinance 20-35 prohibiting data centers in all zones effective August 17, 2026; its transition rule reaches applications without a building permit before that date.",
        "hardware_detail": "Proposed 360 MW hyperscale campus with five 226,850-square-foot data-center buildings at the former Dickerson Power Plant. DCD reports the owner Terra Energy first submitted plans in 2023. Public filings reviewed do not disclose rack density, server classes, or cooling architecture.",
        "profile_source_ids": ["montgomery-dickerson-case", "mde-atmosphere-npdes", "dcd-atmosphere-moratorium-challenge-2026"],
        "source_ids": ["montgomery-dickerson-case", "mde-atmosphere-npdes", "montgomery-zta-26-01", "dcd-atmosphere-moratorium-challenge-2026", "montgomery-data-center-pause-2026", "esri-world-geocoder"],
        "status_source_ids": ["montgomery-dickerson-case", "mde-atmosphere-npdes", "montgomery-zta-26-01", "dcd-atmosphere-moratorium-challenge-2026"],
    },
}


def apply_record_update(record):
    update = DATA_CENTER_RECORD_UPDATES.get(record["id"])
    if update:
        record.update(update)
    return record


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
    "fannie-mae-urbana-tech-center": ["jll-fannie-mae-tech-center-2026"],
    "ssa-national-support-center-urbana": ["southland-ssa-national-support-center"],
}


ESTIMATED_POWER_DRAWS = {
    "aligned-iad04-frederick": {
        "mw": 300,
        "confidence": "medium",
        "basis": (
            "Estimated normal grid draw from a 508 MW permitted emergency-generator plant for a single hyperscale "
            "facility. The estimate treats backup nameplate as a resilience envelope and applies a conservative "
            "hyperscale load proxy; it is not a metered demand value."
        ),
        "source_ids": ["mde-aligned-air-permit-application", "mde-aligned-issued-air-permit-2025"],
    },
    "amazon-bwi150-153-frederick": {
        "mw": 160,
        "confidence": "medium",
        "basis": (
            "Estimated normal grid draw from the 257.75 MW permitted backup-generator fleet across four Amazon "
            "buildings. Backup nameplate is used only as an order-of-magnitude proxy, not as actual demand."
        ),
        "source_ids": ["mde-amazon-air-permit-application", "mde-amazon-issued-air-permit-2026"],
    },
    "fannie-mae-urbana-tech-center": {
        "mw": 4.3,
        "confidence": "medium",
        "basis": (
            "Uses JLL's published 4.3 MW installed critical capacity as the best public operating-load proxy. "
            "The separate 5.5 MW expansion capacity is retained as facility capacity and is not treated as current draw."
        ),
        "source_ids": ["jll-fannie-mae-tech-center-2026"],
    },
    "ssa-national-support-center-urbana": {
        "mw": 10,
        "confidence": "medium",
        "basis": (
            "Uses Southland's published approximately 10 MW IT server-load figure as the best public load proxy. "
            "This is not a metered utility-demand value."
        ),
        "source_ids": ["southland-ssa-national-support-center"],
    },
    "rowan-bauxite-ii-frederick": {
        "mw": 205.7,
        "confidence": "low",
        "basis": (
            "Estimated from the Frederick Planning Commission's 822,620-square-foot planned facility area using a "
            "0.25 kW-per-square-foot hyperscale planning proxy. No Bauxite II-specific public MW capacity or metered demand was found."
        ),
        "source_ids": ["frederick-planning-bauxite-ii-iii-2024"],
    },
    "rowan-bauxite-iii-frederick": {
        "mw": 148.0,
        "confidence": "low",
        "basis": (
            "Estimated from the Frederick Planning Commission's 591,913-square-foot planned facility area using a "
            "0.25 kW-per-square-foot hyperscale planning proxy. No Bauxite III-specific public MW capacity or metered demand was found."
        ),
        "source_ids": ["frederick-planning-bauxite-ii-iii-2024"],
    },
    "annapolis-state-data-center": {
        "mw": 1,
        "confidence": "low",
        "basis": (
            "Estimated as a small legacy government data center because reviewed budget and facility records do not "
            "publish IT load, service capacity, or metered demand."
        ),
        "source_ids": ["maryland-dgs-annapolis-data-center", "mdp-sdat-parcel-property"],
    },
    "tierpoint-baltimore-bal": {
        "mw": 1.5,
        "confidence": "medium",
        "basis": "Estimated from a documented 3 MW backup-generator envelope for an operating colocation site.",
        "source_ids": ["tierpoint-baltimore", "tierpoint-baltimore-spec"],
    },
    "tierpoint-baltimore-bwi": {
        "mw": 1.25,
        "confidence": "medium",
        "basis": "Estimated from a documented 2.5 MW backup-generator envelope for an operating colocation site.",
        "source_ids": ["tierpoint-bwi", "tierpoint-bwi-spec"],
    },
    "expedient-tide-point": {
        "mw": 1,
        "confidence": "medium",
        "basis": (
            "Estimated operating draw from the operator-stated 1.5 MW critical IT load, using a partial-utilization "
            "proxy because measured utility demand is not public."
        ),
        "source_ids": ["expedient-tide-point-spec"],
    },
    "expedient-owings-mills": {
        "mw": 0.55,
        "confidence": "medium",
        "basis": (
            "Estimated operating draw from the operator-stated 0.8 MW critical IT load, using a partial-utilization "
            "proxy because measured utility demand is not public."
        ),
        "source_ids": ["expedient-owings-mills-spec"],
    },
    "databank-bwi1-baltimore": {
        "mw": 0.4,
        "confidence": "medium",
        "basis": (
            "Estimated operating draw from the published 600 kW critical-power figure. The separate 1.5 MW site-power "
            "figure is not used as normal demand."
        ),
        "source_ids": ["databank-bwi1-2020"],
    },
    "databridge-silver-spring": {
        "mw": 6.5,
        "confidence": "medium",
        "basis": "Estimated from the marketed 10 MW site-power capacity using a partial-utilization proxy.",
        "source_ids": ["databridge-home"],
    },
    "atmosphere-dickerson": {
        "mw": 360,
        "confidence": "high",
        "basis": "Estimated from the proposal's published 360 MW campus scale; it is planning demand, not operating load.",
        "source_ids": ["montgomery-zta-26-01", "dcd-atmosphere-moratorium-challenge-2026"],
    },
    "brightseat-tech-park-landover": {
        "mw": 300,
        "confidence": "low",
        "basis": (
            "Estimated as five large data-center buildings on an 88-acre concept plan, using 60 MW per building "
            "as a planning-scale proxy because utility demand and IT load are not public."
        ),
        "source_ids": ["axios-landover-opposition-2025", "pg-executive-orders-2026"],
    },
    "jhu-bayview-research-data-center": {
        "mw": 5,
        "confidence": "low",
        "basis": (
            "Estimated as a university research data center because public funding records identify the project but "
            "do not disclose utility demand or IT load."
        ),
        "source_ids": ["jhu-bayview-state-grant-2026"],
    },
    "cogent-elkridge": {
        "mw": 5,
        "confidence": "medium",
        "basis": (
            "Estimated from Cogent's 7.50 MW facility-power and 6.17 MW protected-power disclosures using a "
            "partial-utilization proxy; the disclosed values are capacity, not metered draw."
        ),
        "source_ids": ["cogent-elkridge-wholesale-2025", "cogent-elkridge-brochure-2025"],
    },
    "atlantech-rockville": {
        "mw": 0.75,
        "confidence": "low",
        "basis": (
            "Estimated as a small regional colocation facility because reviewed operator pages disclose redundant "
            "power and generators but not rack count, utility demand, or IT load."
        ),
        "source_ids": ["atlantech-data-centers", "atlantech-rockville"],
    },
    "atlantech-silver-spring": {
        "mw": 0.5,
        "confidence": "low",
        "basis": (
            "Estimated as a small regional colocation facility because reviewed operator pages disclose redundant "
            "power and generators but not rack count, utility demand, or IT load."
        ),
        "source_ids": ["atlantech-data-centers", "atlantech-colocation-terms"],
    },
    "ainet-beltsville": {
        "mw": 2,
        "confidence": "low",
        "basis": (
            "Estimated as a small-to-medium AiNET colocation site because public operator and registry records do "
            "not disclose site capacity or metered demand."
        ),
        "source_ids": ["ainet-cybernap", "ainet-data-center-services"],
    },
    "ainet-laurel": {
        "mw": 1.5,
        "confidence": "low",
        "basis": (
            "Estimated as a small AiNET colocation site because public operator and registry records do not disclose "
            "site capacity or metered demand."
        ),
        "source_ids": ["ainet-cybernap", "ainet-data-center-services"],
    },
    "ainet-cybernap-glen-burnie": {
        "mw": 52,
        "confidence": "medium",
        "basis": (
            "Estimated from AiNET's published 80 MW utility-feed capacity using a partial-utilization proxy. The "
            "facility's current operating status remains separately marked as not independently verified."
        ),
        "source_ids": ["ainet-cybernap", "ainet-data-center-services"],
    },
    "ainet-one-market-center-baltimore": {
        "mw": 3,
        "confidence": "low",
        "basis": "Estimated as a multi-provider carrier-hotel colocation presence because the directory listing does not disclose metered demand or power capacity.",
        "source_ids": ["datacentermap-baltimore-2026"],
    },
    "crown-castle-baltimore": {
        "mw": 0.25,
        "confidence": "low",
        "basis": "Estimated as a network-provider facility presence because the directory listing describes transport/fiber services rather than a disclosed data-center power envelope.",
        "source_ids": ["datacentermap-baltimore-2026"],
    },
    "databank-111-market-place": {
        "mw": 0.5,
        "confidence": "low",
        "basis": "Estimated as a smaller carrier-hotel interconnection facility because the directory listing discloses connectivity but not metered demand or power capacity.",
        "source_ids": ["datacentermap-baltimore-2026"],
    },
    "infradms-bal01-baltimore": {
        "mw": 0.45,
        "confidence": "medium",
        "basis": "Estimated from the directory-listed 650 kW power capacity using a partial-utilization proxy; the 650 kW value is capacity, not measured demand.",
        "source_ids": ["datacentermap-baltimore-2026"],
    },
    "amazon-cronridge-owings-mills": {
        "mw": 5,
        "confidence": "low",
        "basis": "Estimated as a small AWS acquired data-center facility because the directory listing identifies the facility but does not disclose power capacity or metered demand.",
        "source_ids": ["datacentermap-baltimore-2026"],
    },
    "woodlawn-drive-1500-proposal": {
        "mw": 150,
        "confidence": "medium",
        "basis": "Estimated from the directory-listed proposed 150 MW campus scale; this is planning demand, not operating load.",
        "source_ids": ["datacentermap-baltimore-2026"],
    },
    "comcast-nottingham": {
        "mw": 0.75,
        "confidence": "low",
        "basis": "Estimated as a Comcast network/edge facility because the directory listing does not disclose power capacity or metered demand.",
        "source_ids": ["datacentermap-baltimore-2026"],
    },
    "gi-partners-eternal-rings-laurel": {
        "mw": 60,
        "confidence": "low",
        "basis": "Estimated as a hyperscale powered-shell facility from the directory-listed 218,000-square-foot development scale; no metered demand was disclosed.",
        "source_ids": ["datacentermap-baltimore-2026"],
    },
    "gi-partners-sandy-farm-severn": {
        "mw": 60,
        "confidence": "low",
        "basis": "Estimated as a fully leased hyperscale powered-shell facility from the directory description; no metered demand or power capacity was disclosed.",
        "source_ids": ["datacentermap-baltimore-2026"],
    },
    "lumen-baltimore": {
        "mw": 1,
        "confidence": "low",
        "basis": "Estimated as a carrier network and interconnection facility presence because the directory listing does not disclose power capacity or metered demand.",
        "source_ids": ["datacentermap-baltimore-2026"],
    },
    "candler-building-baltimore": {
        "mw": 0.5,
        "confidence": "low",
        "basis": "Estimated as a generic carrier-hotel building listing because the directory listing does not disclose operator, power capacity, or metered demand.",
        "source_ids": ["datacentermap-baltimore-2026"],
    },
}


FUNDING_PROFILES = {
    "tierpoint-baltimore-bwi": {
        "summary": "TierPoint announced an initial facility investment exceeding $10 million. The public record reviewed does not identify a facility-specific government award.",
        "total_known_usd": 10_000_000,
        "source_ids": ["tierpoint-bwi-investment"],
        "breakdown": [
            {
                "funder": "TierPoint",
                "amount_usd": 10_000_000,
                "amount_status": "reported minimum",
                "basis": "Announced initial private facility investment exceeding $10 million; chart uses $10 million as a conservative floor.",
                "source_ids": ["tierpoint-bwi-investment"],
            },
        ],
    },
    "expedient-tide-point": {
        "summary": "Expedient reported more than $6 million of upgrades and expansions for its Baltimore data-center footprint during 2011–2013.",
        "total_known_usd": 6_000_000,
        "source_ids": ["expedient-baltimore-investment-2013"],
        "breakdown": [
            {
                "funder": "Expedient",
                "amount_usd": 6_000_000,
                "amount_status": "reported minimum",
                "basis": "Reported upgrades and expansions exceeded $6 million; chart uses $6 million as a conservative floor.",
                "source_ids": ["expedient-baltimore-investment-2013"],
            },
        ],
    },
    "brightseat-tech-park-landover": {
        "summary": "The former Landover Mall concept was reported as a $5 billion development proposal. The reviewed records do not name executed funders or a public award.",
        "total_known_usd": 5_000_000_000,
        "source_ids": ["wbj-landover-concept-2024"],
        "breakdown": [
            {
                "funder": "Unnamed Brightseat Tech Park development sponsor",
                "amount_usd": 5_000_000_000,
                "amount_status": "reported concept value",
                "basis": "Reported $5 billion development concept; not evidence of closed project financing.",
                "source_ids": ["wbj-landover-concept-2024"],
            },
        ],
    },
    "jhu-bayview-research-data-center": {
        "summary": "The project was reported at $196 million, including a $9 million Maryland capital grant approved by the Board of Public Works; the remainder is not broken down by funder in the reviewed record.",
        "total_known_usd": 196_000_000,
        "source_ids": ["jhu-bayview-state-grant-2026"],
        "breakdown": [
            {
                "funder": "Maryland Board of Public Works / State of Maryland",
                "amount_usd": 9_000_000,
                "amount_status": "approved grant",
                "basis": "Board of Public Works approval reported for a Maryland capital grant.",
                "source_ids": ["jhu-bayview-state-grant-2026"],
            },
            {
                "funder": "Johns Hopkins project funds and other non-itemized sources",
                "amount_usd": 187_000_000,
                "amount_status": "derived remainder",
                "basis": "Reported total project cost less the identified $9 million Maryland grant; reviewed records did not publish a more specific funder split.",
                "source_ids": ["jhu-bayview-state-grant-2026"],
            },
        ],
    },
    "cogent-elkridge": {
        "summary": "Cogent sold this facility as part of a ten-property, $225 million portfolio sale to an I Squared Capital-sponsored entity. No Elkridge-specific allocation was disclosed.",
        "total_known_usd": None,
        "source_ids": ["cogent-elkridge-sale-closing-2026"],
        "breakdown": [
            {
                "funder": "I Squared Capital-sponsored acquiring entity",
                "amount_usd": None,
                "amount_status": "portfolio amount not facility allocated",
                "aggregate_amount_usd": 225_000_000,
                "basis": "Aggregate ten-property transaction value was disclosed; no facility allocation was published.",
                "source_ids": ["cogent-elkridge-sale-closing-2026"],
            },
        ],
    },
    "ssa-national-support-center-urbana": {
        "summary": "Federal facility delivered for the U.S. General Services Administration; the reviewed records did not isolate a facility-level funding amount.",
        "total_known_usd": None,
        "source_ids": ["southland-ssa-national-support-center", "som-ssa-national-support-center"],
        "breakdown": [
            {
                "funder": "U.S. General Services Administration",
                "amount_usd": None,
                "amount_status": "amount not isolated",
                "basis": "Responsible federal owner/delivery agency identified; facility-level funding amount not isolated in reviewed sources.",
                "source_ids": ["southland-ssa-national-support-center", "som-ssa-national-support-center"],
            },
        ],
    },
    "annapolis-state-data-center": {
        "summary": "State-owned and operated Maryland facility; reviewed records did not isolate facility-level capital or operating funding.",
        "total_known_usd": None,
        "source_ids": ["maryland-dgs-annapolis-data-center", "maryland-doit-cloud-hosting"],
        "breakdown": [
            {
                "funder": "Maryland Department of General Services / Maryland DoIT",
                "amount_usd": None,
                "amount_status": "amount not isolated",
                "basis": "Responsible state agencies identified; facility-level budget amount not isolated in reviewed sources.",
                "source_ids": ["maryland-dgs-annapolis-data-center", "maryland-doit-cloud-hosting"],
            },
        ],
    },
}


def apply_funding_profile(record):
    profile = FUNDING_PROFILES.get(record["id"])
    if profile:
        record.update(
            {
                "funding_summary": profile["summary"],
                "funding_total_known_usd": profile["total_known_usd"],
                "funding_breakdown": profile["breakdown"],
                "funding_source_ids": profile["source_ids"],
            }
        )
        return record

    if record.get("capital_investment_usd"):
        source_ids = record.get("profile_source_ids", [])
        record.update(
            {
                "funding_summary": "Facility-specific capital investment is published, but reviewed records do not identify a more detailed funder split.",
                "funding_total_known_usd": record["capital_investment_usd"],
                "funding_breakdown": [
                    {
                        "funder": record.get("owner") or record.get("operator") or "Project sponsor",
                        "amount_usd": record["capital_investment_usd"],
                        "amount_status": "reported facility value",
                        "basis": record.get("financing_detail") or "Capital investment figure carried from the source-backed facility record.",
                        "source_ids": source_ids,
                    }
                ],
                "funding_source_ids": source_ids,
            }
        )
        return record

    record.update(
        {
            "funding_summary": record.get("financing_detail") or "No facility-specific funder breakdown was identified in the reviewed records.",
            "funding_total_known_usd": None,
            "funding_breakdown": [],
            "funding_source_ids": [],
        }
    )
    return record


def apply_estimated_power_draw(record):
    demand = record.get("reported_grid_demand_mw")
    if isinstance(demand, (int, float)):
        record.update(
            {
                "estimated_power_draw_mw": float(demand),
                "estimated_power_draw_basis": "Uses the published normal grid-demand value; no separate estimate was needed.",
                "estimated_power_draw_confidence": "high",
                "estimated_power_draw_source_ids": POWER_SCALE_SOURCE_IDS.get(
                    record["id"], record.get("profile_source_ids", [])
                ),
            }
        )
        return record

    estimate = ESTIMATED_POWER_DRAWS.get(record["id"])
    if estimate:
        record.update(
            {
                "estimated_power_draw_mw": float(estimate["mw"]),
                "estimated_power_draw_basis": estimate["basis"],
                "estimated_power_draw_confidence": estimate["confidence"],
                "estimated_power_draw_source_ids": estimate["source_ids"],
            }
        )
        return record

    capacity = record.get("reported_power_capacity_mw")
    if isinstance(capacity, (int, float)):
        estimate_value = round(float(capacity) * 0.67, 3)
        record.update(
            {
                "estimated_power_draw_mw": estimate_value,
                "estimated_power_draw_basis": (
                    "Estimated from published facility power capacity using a two-thirds utilization proxy because "
                    "measured grid demand is not public."
                ),
                "estimated_power_draw_confidence": "low",
                "estimated_power_draw_source_ids": POWER_SCALE_SOURCE_IDS.get(
                    record["id"], record.get("profile_source_ids", [])
                ),
            }
        )
    return record


def apply_operational_finance(record):
    source_ids = set(record.get("estimated_power_draw_source_ids") or record.get("profile_source_ids") or [])
    source_ids.add(MARYLAND_ALL_SECTOR_PRICE_SOURCE_ID)
    annual_mwh = record.get("reported_annual_energy_mwh")
    if isinstance(annual_mwh, (int, float)):
        energy_mwh = float(annual_mwh)
        energy_basis = "Uses published annual energy use from the facility record."
    elif isinstance(record.get("estimated_power_draw_mw"), (int, float)):
        energy_mwh = round(float(record["estimated_power_draw_mw"]) * HOURS_IN_2024, 1)
        energy_basis = (
            f"Estimated as {record['estimated_power_draw_mw']} MW average draw multiplied by {HOURS_IN_2024:,} hours "
            "in 2024. This is a planning proxy, not metered consumption."
        )
    else:
        record.update(
            {
                "operational_finance_summary": (
                    "No facility-specific operating-cost, revenue, tax-payment, or electricity-cost estimate could be "
                    "computed because neither metered annual energy nor a usable demand proxy is public."
                ),
                "estimated_annual_electricity_use_mwh": None,
                "estimated_annual_electricity_cost_usd": None,
                "electricity_cost_rate_cents_per_kwh": MARYLAND_ALL_SECTOR_PRICE_CENTS_PER_KWH_2024,
                "electricity_cost_basis": (
                    "Maryland 2024 all-sector average retail electricity price retained for context; no facility load "
                    "basis was available."
                ),
                "operational_finance_items": [],
                "operational_finance_source_ids": [MARYLAND_ALL_SECTOR_PRICE_SOURCE_ID],
            }
        )
        return record

    electricity_cost = round(energy_mwh * MARYLAND_ALL_SECTOR_PRICE_CENTS_PER_KWH_2024 * 10)
    unbuilt = any(
        term in str(record.get("status") or "").lower()
        for term in ("development", "proposed", "concept", "planned")
    )
    scenario = "if built / fully energized" if unbuilt else "operating planning proxy"
    items = [
        {
            "label": "Electricity energy charge proxy",
            "amount_usd": electricity_cost,
            "amount_status": scenario,
            "basis": (
                f"{energy_basis} Cost applies Maryland's 2024 all-sector average retail electricity price of "
                f"{MARYLAND_ALL_SECTOR_PRICE_CENTS_PER_KWH_2024}¢/kWh. It excludes demand charges, riders, taxes, "
                "capacity charges, transmission-service terms, negotiated tariffs, and power-purchase agreements."
            ),
            "source_ids": sorted(source_ids),
        }
    ]
    if isinstance(record.get("employees_current"), (int, float)) and record["employees_current"] > 0:
        items.append(
            {
                "label": "Published site personnel",
                "amount_usd": None,
                "amount_status": f"{record['employees_current']} people; payroll cost not published",
                "basis": "Headcount is carried from the facility profile; wages, benefits, contractors, and operating payroll were not isolated.",
                "source_ids": record.get("profile_source_ids", []),
            }
        )
    if record.get("tax_incentive_detail"):
        items.append(
            {
                "label": "Tax incentive / exemption context",
                "amount_usd": None,
                "amount_status": "amount not isolated",
                "basis": record["tax_incentive_detail"],
                "source_ids": record.get("source_ids", []),
            }
        )
    if record.get("public_funding_detail"):
        items.append(
            {
                "label": "Public budget or grant context",
                "amount_usd": None,
                "amount_status": "capital context; not operating cost",
                "basis": record["public_funding_detail"],
                "source_ids": record.get("funding_source_ids") or record.get("source_ids", []),
            }
        )

    record.update(
        {
            "operational_finance_summary": (
                f"Estimated annual electricity energy-charge proxy is ${electricity_cost:,} "
                f"({scenario}). Facility-specific operating revenue, property-tax payments, demand charges, negotiated "
                "utility tariffs, and power-purchase terms were not isolated in reviewed records."
            ),
            "estimated_annual_electricity_use_mwh": energy_mwh,
            "estimated_annual_electricity_cost_usd": electricity_cost,
            "electricity_cost_rate_cents_per_kwh": MARYLAND_ALL_SECTOR_PRICE_CENTS_PER_KWH_2024,
            "electricity_cost_basis": items[0]["basis"],
            "operational_finance_items": items,
            "operational_finance_source_ids": sorted(source_ids),
        }
    )
    return record


def apply_projected_power_demand(record):
    status = str(record.get("status") or "").lower()
    unbuilt = any(term in status for term in ("development", "proposed", "concept", "planned"))
    estimate = record.get("estimated_power_draw_mw")
    if unbuilt and isinstance(estimate, (int, float)):
        record.update(
            {
                "projected_power_demand_mw": float(estimate),
                "projected_power_demand_basis": record.get("estimated_power_draw_basis"),
                "projected_power_demand_confidence": record.get("estimated_power_draw_confidence"),
                "projected_power_demand_source_ids": record.get("estimated_power_draw_source_ids", []),
            }
        )
    else:
        record.update(
            {
                "projected_power_demand_mw": None,
                "projected_power_demand_basis": None,
                "projected_power_demand_confidence": None,
                "projected_power_demand_source_ids": [],
            }
        )
    return record


def classify_data_center_power(record):
    demand = record.get("reported_grid_demand_mw")
    estimate = record.get("estimated_power_draw_mw")
    capacity = record.get("reported_power_capacity_mw")
    if isinstance(demand, (int, float)):
        value = float(demand)
        value_kind = "reported grid demand"
        tag_prefix = "Draw"
        detail = "Classified from publicly reported normal grid demand."
    elif isinstance(estimate, (int, float)):
        value = float(estimate)
        value_kind = "estimated grid demand"
        tag_prefix = "Estimated draw"
        detail = record.get("estimated_power_draw_basis") or "Classified from estimated normal grid demand."
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
                record["id"], record.get("estimated_power_draw_source_ids") or record.get("profile_source_ids", [])
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


def enrich_power_plant_planning_output(record):
    capacity = record.get("nameplate_capacity_mw")
    generation = record.get("net_generation_mwh")
    year = record.get("generation_year")
    source_id = record.get("generation_source_id")
    fields = {
        "planning_sustained_output_mw": None,
        "annual_capacity_factor": None,
        "planning_output_basis": None,
        "planning_output_source_id": source_id,
    }
    if not isinstance(capacity, (int, float)) or capacity <= 0:
        fields["planning_output_basis"] = "No positive nameplate capacity is available to bound annual-average planning output."
        record.update(fields)
        return record
    if not isinstance(generation, (int, float)):
        fields["planning_output_basis"] = "No annual net-generation value is available to calculate annual-average planning output."
        record.update(fields)
        return record

    raw_output = float(generation) / 8760
    bounded_output = min(float(capacity), max(0.0, raw_output))
    fields.update(
        {
            "planning_sustained_output_mw": clean_number(bounded_output),
            "annual_capacity_factor": clean_number(bounded_output / float(capacity), 4),
            "planning_output_basis": (
                f"Annual-average planning output calculated from {year or 'reported'} net generation divided by "
                "8,760 hours and bounded between zero and EIA nameplate capacity. This is a year-round planning "
                "proxy, not a peak, dispatchable, accredited, or reliability-capacity rating."
            ),
        }
    )
    record.update(fields)
    return record


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
    return [
        classify_data_center_power(
            apply_projected_power_demand(
                apply_operational_finance(
                    apply_estimated_power_draw(
                        apply_funding_profile(apply_contestation_profile(apply_record_update(record)))
                    )
                )
            )
        )
        for record in merged
    ]


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
        plants = [
            enrich_power_plant_planning_output(record)
            for record in existing
            if record.get("record_type") == "power_plant"
        ]
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
            enrich_power_plant_planning_output({
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
            })
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
