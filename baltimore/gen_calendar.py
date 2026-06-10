import importlib
from pathlib import Path
import sys
from urllib.parse import urlparse

CITY_DIR = Path(__file__).resolve().parent
ROOT_DIR = CITY_DIR.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import scrape_ics
import scrape_mtc


ICS_SOURCES = [
    {
        "url": "https://baltimorenode.org/events/",
        "ics_url": "http://www.google.com/calendar/ical/baltimorenode.org_5jbobahkshgj11vut3cndhppoo%40group.calendar.google.com/public/basic.ics",
        "orgImageUrl": "https://www.baltimorenode.org/wp-content/uploads/2013/11/node-logo.png",
        "tags": ["Makerspace"],
        "group_name": "Baltimore Node",
        "preface": "Node ",
    },
    {
        "url": "https://catonsvillepres.org/events/",
        "ics_url": "https://catonsvillepres.org/events/?ical=1",
        "orgImageUrl": "https://catonsvillepres.org/wp-content/uploads/2023/02/social-sharing.png",
        "tags": ["Religion"],
        "group_name": "Catonsville Presbyterian Church",
    },
    {
        "url": "https://taqwa.net/events/",
        "ics_url": "https://calendar.google.com/calendar/ical/daraltaqwamd%40gmail.com/public/basic.ics",
        "orgImageUrl": "https://taqwa.net/wp-content/uploads/2023/03/logo-w.png",
        "tags": ["Religion"],
        "group_name": "Dar Al-Taqwa",
    },
    {
        "url": "https://ggwo.org/gg-events/",
        "ics_url": "https://ggwo.org/gg-events/?ical=1",
        "orgImageUrl": "https://ggwo.org/wp-content/uploads/2018/11/ggwo-logo-with-world-wide-local-church-800-162-png1.png",
        "tags": ["Religion"],
        "group_name": "Greater Grace World Outreach",
    },
    {
        "url": "https://incarnationbmore.org/events/",
        "ics_url": "https://incarnationbmore.org/events/?ical=1",
        "orgImageUrl": "https://incarnationbmore.org/wp-content/uploads/2022/09/Incarnation-Logo-Words-Color.png",
        "tags": ["Religion"],
        "group_name": "Cathedral of the Incarnation",
    },
    {
        "url": "https://jagganathtemple.org/events/",
        "ics_url": "https://jagganathtemple.org/events/?ical=1",
        "orgImageUrl": "https://jagganathtemple.org/wp-content/uploads/2025/11/cropped-Jagannath-Temple-of-North-America-1.png",
        "tags": ["Religion"],
        "group_name": "Jagannath Temple of North America",
    },
    {
        "url": "https://www.unallocatedspace.org/events/",
        "ics_url": "https://calendar.google.com/calendar/ical/unallocatedspacehq@gmail.com/public/basic.ics",
        "orgImageUrl": "https://www.unallocatedspace.org/wp-content/uploads/2017/03/UnallocatedLogoSmall.png",
        "tags": ["Makerspace"],
        "group_name": "Unallocated Space",
        "preface": "UAS ",
    },
    {
        "url": "https://baltimoreindiegames.com/events/",
        "ics_url": "https://baltimoreindiegames.com/events/list/?ical=1",
        "orgImageUrl": "https://baltimoreindiegames.com/wp-content/uploads/2025/03/BIG_small.png",
        "tags": ["Tech Skills"],
        "group_name": "Baltimore Indie Games",
        "recurring": False,
    },
    {
        "url": "https://chesapeakeclimate.org/",
        "ics_url": "https://calendar.google.com/calendar/ical/c_35ce051bfecc3ebd59f7776829ca549d2dd38e8ab2a50b07bd4243cb1c218c72%40group.calendar.google.com/public/basic.ics",
        "orgImageUrl": "https://chesapeakeclimate.org/wp-content/uploads/2022/02/CCAN-Logo-2022-300RGB-wht-e1643743097559.png",
        "tags": ["Climate & Energy", "Water & Environment"],
        "group_name": "CCAN Baltimore",
        "recurring": False,
    },
    {
        "url": "https://mdgop.org/calendar/",
        "ics_url": "https://mdgop.org/calendar/list/?ical=1",
        "orgImageUrl": "https://mdgop.org/wp-content/uploads/sites/30/2025/10/MDGOP-logo-2.png",
        "tags": ["Politics"],
        "group_name": "Maryland GOP",
        "preface": "",
    },
    {
        "url": "https://maryland-dmmp.com/events/",
        "ics_url": "https://maryland-dmmp.com/events/list/?ical=1",
        "orgImageUrl": "https://maryland-dmmp.com/wp-content/uploads/2022/12/cropped-favicon-32x32.png",
        "tags": ["MarylandGov", "Economic Development", "Infrastructure", "Water"],
        "group_name": "Maryland Port Administration (DMMP)",
        "preface": "",
    },
]

PROCESS_ICS_SOURCES = [
    {
        "cache_filename": "maryland-stem-festival-96ecc18ef7d.ics",
        "url": "https://marylandstemfestival.org/events/month/",
        "orgImageUrl": "https://marylandstemfestival.org/wp-content/uploads/2024/06/Family-Feud-group-Pix-1-scaled-e1717876361661.jpeg",
        "tags": ["Tech Skills"],
        "group_name": "Maryland STEM Festival",
        "preface": "STEMFest ",
    },
]

CUSTOM_SCRAPER_SOURCES = [
    {
        "module": "baltimore.scrape_ottobar",
        "function": "scrape_events",
        "url": "https://theottobar.com/events/",
        "group_name": "Ottobar",
        "orgImageUrl": "https://theottobar.com/wp-content/uploads/2021/07/Ottobar-since-1997-logo-black-1.png",
        "tags": ["Culture"],
    },
    {
        "module": "baltimore.scrape_soundstage",
        "function": "scrape_events",
        "url": "https://www.baltimoresoundstage.com/events-feed/",
        "group_name": "Baltimore Soundstage",
        "orgImageUrl": "https://www.baltimoresoundstage.com/wp-content/themes/baltimore-soundstage-2/assets/img/logo.png",
        "tags": ["Culture"],
    },
    {
        "module": "baltimore.scrape_powerplantlive",
        "function": "scrape_events",
        "url": "https://powerplantlive.com/events-and-entertainment/events",
        "group_name": "Power Plant Live!",
        "orgImageUrl": "https://edge.sitecorecloud.io/cordishc-4m5nplkf/media/Cordish/Images/District-Websites/Power-Plant-Live/Logos/Power-Plant-Live-Logo-Color-177x51.png?h=51&iar=0&w=177&rev=f5dd9c36d71644fda1250d28224ce3d8",
        "tags": ["Culture"],
    },
    {
        "module": "baltimore.scrape_lemondo",
        "function": "scrape_events",
        "url": "https://www.lemondo.org/",
        "group_name": "Le Mondo",
        "orgImageUrl": "https://static.wixstatic.com/media/5c4b5d_cc4aba7ac8e7429989e750359a8dc987%7Emv2.png/v1/fill/w_192,h_192,lg_1,usm_0.66_1.00_0.01/5c4b5d_cc4aba7ac8e7429989e750359a8dc987%7Emv2.png",
        "tags": ["Culture"],
    },
    {
        "module": "baltimore.scrape_rhouse",
        "function": "scrape_events",
        "url": "https://r.housebaltimore.com/",
        "group_name": "R. House",
        "orgImageUrl": "https://r.housebaltimore.com/wp-content/themes/rhouseofficial/img/favicon.png",
        "tags": ["Culture"],
    },
    {
        "module": "baltimore.scrape_mdchamber",
        "function": "scrape_events",
        "url": "https://www.mdchamber.org/events/",
        "group_name": "Maryland Chamber of Commerce",
        "orgImageUrl": "https://www.mdchamber.org/wp-content/uploads/sites/47/2017/09/Maryland-Chamber-logo.png",
        "tags": ["Business", "Economic Development"],
    },
    {
        "module": "baltimore.scrape_greaterbaltimorechamber",
        "function": "scrape_events",
        "url": "https://www.greaterbaltimorechamber.org/calendarandevents/eventcalendar",
        "group_name": "Greater Baltimore Chamber",
        "orgImageUrl": "https://www.google.com/s2/favicons?domain=www.greaterbaltimorechamber.org&sz=256",
        "tags": ["Business", "Economic Development"],
    },
    {
        "module": "baltimore.scrape_transformpikesvillearmory",
        "function": "scrape_events",
        "url": "https://transformpikesvillearmory.org/events",
        "group_name": "Pikesville Armory Foundation",
        "orgImageUrl": "https://transformpikesvillearmory.org/wp-content/uploads/2024/01/PA_Temp_Logo_Horizontal_RustWhite_RGB.png",
        "tags": ["Community", "Culture"],
    },
    {
        "module": "baltimore.scrape_redemmas",
        "function": "scrape_events",
        "url": "https://redemmas.org/events/",
        "group_name": "Red Emma's",
        "orgImageUrl": "https://redemmas.org/static/logo-2096e46fa2115c72698cb268ccbd90c7.png",
        "tags": ["Economic Development", "Community", "Education"],
    },
    {
        "module": "baltimore.scrape_baltimoreorg",
        "function": "scrape_events",
        "url": "https://baltimore.org/events/",
        "group_name": "Visit Baltimore",
        "orgImageUrl": "https://baltimore.org/wp-content/uploads/2024/06/visit-baltimore-logo.svg",
        "tags": ["Community", "Culture"],
    },
    {
        "module": "baltimore.scrape_orioles",
        "function": "scrape_events",
        "url": "https://www.mlb.com/orioles/schedule",
        "group_name": "Baltimore Orioles",
        "orgImageUrl": "https://www.mlbstatic.com/team-logos/team-cap-on-dark/110.svg",
        "tags": ["Culture", "Community", "Economic Development"],
    },
    {
        "module": "baltimore.scrape_bccenter",
        "function": "scrape_events",
        "url": "https://www.bccenter.org/events/",
        "group_name": "Baltimore Convention Center",
        "orgImageUrl": "https://www.bccenter.org/images/logo.png",
        "tags": ["Culture", "Community", "Economic Development"],
    },
    {
        "module": "baltimore.scrape_towsonlodge",
        "function": "scrape_events",
        "url": "https://towsonlodge.us/calendar-%26-events",
        "group_name": "Towson Lodge #79",
        "orgImageUrl": "https://www.google.com/s2/favicons?domain=towsonlodge.us&sz=256",
        "tags": ["Community", "Fraternal"],
    },
    {
        "module": "baltimore.scrape_digitalequitybaltimore",
        "function": "scrape_events",
        "url": "https://www.digitalequitybaltimore.org/general-clean",
        "group_name": "Digital Equity Baltimore",
        "orgImageUrl": "https://static.wixstatic.com/media/8dc51b_7123df01d68e47a1b4b717c89ad4aea7~mv2.png/v1/fill/w_223,h_90,al_c,q_85,usm_0.66_1.00_0.01,enc_avif,quality_auto/BDEC%20(1).png",
        "tags": ["Economic Development", "Digital Equity"],
    },
    {
        "module": "baltimore.scrape_umventures",
        "function": "scrape_events",
        "url": "https://www.umventures.org/events",
        "group_name": "UM Ventures",
        "orgImageUrl": "https://www.umventures.org/sites/default/files/inline-images/UMVentures-Logo_0.png",
        "tags": ["Business", "Startup", "Economic Development"],
    },
    {
        "module": "baltimore.scrape_ccdgroup",
        "function": "scrape_events",
        "url": "https://www.ccdgroup.org/connect",
        "group_name": "Community Co-op Development",
        "orgImageUrl": "https://static.wixstatic.com/media/1eb3be_6b8180d9b60847a1b9a614acdf9afe6f~mv2.png/v1/fill/w_348,h_348,al_c,q_85,usm_0.66_1.00_0.01,enc_avif,quality_auto/CCD%20Inc%20logo%20(white%20bkgrnd%20large)_PNG.png",
        "tags": ["Economic Development", "Community Organizing", "Food Security"],
    },
    {
        "module": "baltimore.scrape_mpa_port_commission",
        "function": "scrape_events",
        "url": "https://mpa.maryland.gov/Pages/port-commission.aspx",
        "group_name": "Maryland Port Commission",
        "orgImageUrl": "https://mpa.maryland.gov/_catalogs/masterpage/images/favicon.ico",
        "tags": ["MarylandGov", "Politics", "Economic Development", "Infrastructure"],
    },
    {
        "module": "baltimore.scrape_baltimoreportalliance",
        "function": "scrape_events",
        "url": "https://www.baltimoreportalliance.org/career-expo/2026-highlights",
        "group_name": "Baltimore Port Alliance",
        "orgImageUrl": "https://www.google.com/s2/favicons?domain=www.baltimoreportalliance.org&sz=256",
        "tags": ["Economic Development", "Workforce", "Infrastructure"],
    },
    {
        "module": "baltimore.scrape_baltimorecounty_dewd",
        "function": "scrape_events",
        "url": "https://www.baltimorecountymd.gov/departments/economic-and-workforce-development",
        "group_name": "Baltimore County DEWD",
        "orgImageUrl": "https://www.google.com/s2/favicons?domain=baltimorecountymd.gov&sz=256",
        "tags": ["MarylandGov", "Economic Development", "Workforce"],
    },
]
def merge_tags(*tag_lists):
    merged = []
    seen = set()

    for tag_list in tag_lists:
        if not tag_list:
            continue
        for tag in tag_list:
            if not tag or tag in seen:
                continue
            seen.add(tag)
            merged.append(tag)

    return merged


def apply_source_tags(events, source_url, source_tags, source_group="", org_image_url=""):
    if not events:
        return []

    normalized_group = str(source_group or "").strip()
    if not normalized_group and source_url:
        normalized_group = urlparse(source_url).netloc.replace("www.", "").strip()

    normalized_events = events if isinstance(events, list) else [events]
    for event in normalized_events:
        if not isinstance(event, dict):
            continue
        event["tags"] = merge_tags(source_tags, event.get("tags"))
        if source_url:
            event.setdefault("source", source_url)
            event["source_url"] = source_url
        if normalized_group:
            event.setdefault("source_group", normalized_group)
            event.setdefault("org_name", normalized_group)
            event.setdefault("orgName", normalized_group)
        if org_image_url:
            event.setdefault("orgImageUrl", org_image_url)

    return normalized_events


def fetch_ics_source(source, city):
    return scrape_ics.fetch_calendar_events(
        ICS_URL=source["ics_url"],
        city=city,
        imageURL=source.get("orgImageUrl") or source.get("image_url", "https://www.unallocatedspace.org/wp-content/uploads/2017/03/UnallocatedLogoSmall.png"),
        eventUrl=source["url"],
        recurring=source.get("recurring", True),
        preface=source.get("preface", ""),
    )


def fetch_cached_ics_source(source):
    return scrape_ics.processICS(
        CACHE_FILENAME=source["cache_filename"],
        imageURL=source.get("orgImageUrl") or source.get("image_url", "https://www.unallocatedspace.org/wp-content/uploads/2017/03/UnallocatedLogoSmall.png"),
        eventUrl=source["url"],
        recurring=source.get("recurring", True),
        preface=source.get("preface", ""),
    )


def collect_events(city="baltimore", error_logger=None):
    new_events = []

    def log_error(message, error, source_url=None, scraper=None, stage="city_collect"):
        print(f"{message}: {error}")
        if error_logger:
            error_logger(
                stage=stage,
                error=error,
                source_url=source_url,
                scraper=scraper,
            )

    scrape_gbc = importlib.import_module("baltimore.scrape_gbc")
    new_events += apply_source_tags(
        scrape_gbc.scrape_gbc_events(),
        "https://gbc.org/events/",
        ["Business"],
    )

    for source in ICS_SOURCES:
        try:
            new_events += apply_source_tags(
                fetch_ics_source(source, city),
                source["url"],
                source.get("tags", []),
                source.get("group_name", ""),
                source.get("orgImageUrl") or source.get("image_url", ""),
            )
        except Exception as e:
            log_error("Error fetching calendar events", e, source["url"], "scrape_ics.fetch_calendar_events")

    try:
        scrape_catonsvilleumc = importlib.import_module("baltimore.scrape_catonsvilleumc")
        new_events += apply_source_tags(
                scrape_catonsvilleumc.scrape_events(),
                "https://www.catonsvilleumc.org/upcoming-events/",
                ["Religion"],
                org_image_url="https://www.catonsvilleumc.org/wp-content/uploads/2021/11/CUMC-Logo-Color.png",
            )
    except Exception as e:
        log_error("Error fetching Catonsville UMC events", e, "https://www.catonsvilleumc.org/upcoming-events/", "baltimore.scrape_catonsvilleumc")

    try:
        scrape_saintmos = importlib.import_module("baltimore.scrape_saintmos")
        new_events += apply_source_tags(
                scrape_saintmos.scrape_events(),
                "https://saintmos.org/gatherings",
                ["Religion"],
                org_image_url="https://images.squarespace-cdn.com/content/v1/602ff95edc8bf42c73c4d24a/1518921092755-Q3BHQ50E6B0K34KM278Q/logo+only.png?format=1500w",
            )
    except Exception as e:
        log_error("Error fetching St. Moses events", e, "https://saintmos.org/gatherings", "baltimore.scrape_saintmos")

    try:
        scrape_haic = importlib.import_module("baltimore.scrape_haic")
        new_events += apply_source_tags(
                scrape_haic.scrape_events(),
                "https://haicbaltimore.org/upcoming-events/",
                ["Religion"],
                org_image_url="https://haicbaltimore.org/wp-content/uploads/2023/10/cropped-HAIC-Logo.png",
            )
    except Exception as e:
        log_error("Error fetching HAIC events", e, "https://haicbaltimore.org/upcoming-events/", "baltimore.scrape_haic")

    try:
        scrape_rccbaltimore = importlib.import_module("baltimore.scrape_rccbaltimore")
        new_events += apply_source_tags(
                scrape_rccbaltimore.scrape_events(),
                "https://www.rccbaltimore.org/events-1",
                ["Religion"],
                org_image_url="https://images.squarespace-cdn.com/content/v1/5c44f0d575f9ee2777410e50/1551248787775-EKX12KBFM0E4QXH7TDNR/RCC+Baltimore+Logo.png",
            )
    except Exception as e:
        log_error("Error fetching Redemption City Church events", e, "https://www.rccbaltimore.org/events-1", "baltimore.scrape_rccbaltimore")

    try:
        scrape_columbiapres = importlib.import_module("baltimore.scrape_columbiapres")
        new_events += apply_source_tags(
                scrape_columbiapres.scrape_events(),
                "https://columbiapres.org/",
                ["Religion"],
                org_image_url="https://columbiapres.org/wp-content/uploads/2020/10/cpc-social-share.jpg",
            )
    except Exception as e:
        log_error("Error fetching Columbia Presbyterian events", e, "https://columbiapres.org/", "baltimore.scrape_columbiapres")

    try:
        scrape_mosaicchristian = importlib.import_module("baltimore.scrape_mosaicchristian")
        new_events += apply_source_tags(
                scrape_mosaicchristian.scrape_events(),
                "https://mosaicchristian.org/events/",
                ["Religion"],
                org_image_url="https://mosaicchristian.org/wp-content/uploads/2023/09/Mosaic-Logo.png",
            )
    except Exception as e:
        log_error("Error fetching Mosaic Christian events", e, "https://mosaicchristian.org/events/", "baltimore.scrape_mosaicchristian")

    try:
        scrape_sjbc = importlib.import_module("baltimore.scrape_sjbc")
        new_events += apply_source_tags(
                scrape_sjbc.scrape_events(),
                "https://sjbc.org/events/",
                ["Religion", "Education", "Community"],
                org_image_url="https://sjbc.org/wp-content/uploads/2023/01/sjbc_logo.png",
            )
    except Exception as e:
        log_error("Error fetching St John Baptist Church events", e, "https://sjbc.org/events/", "baltimore.scrape_sjbc")

    try:
        scrape_calvaryec = importlib.import_module("baltimore.scrape_calvaryec")
        new_events += apply_source_tags(
                scrape_calvaryec.scrape_events(),
                "https://calvaryec.com/events",
                ["Religion"],
                org_image_url="https://calvaryec.com/wp-content/uploads/2022/08/CalvaryEC-Logo.png",
            )
    except Exception as e:
        log_error("Error fetching Calvary Chapel Ellicott City events", e, "https://calvaryec.com/events", "baltimore.scrape_calvaryec")

    try:
        scrape_mtzion = importlib.import_module("baltimore.scrape_mtzion")
        new_events += apply_source_tags(
            scrape_mtzion.scrape_events(),
            "https://www.mtzionbaltimore.org/events/",
            ["Religion"],
        )
    except Exception as e:
        log_error("Error fetching Mt. Zion Church events", e, "https://www.mtzionbaltimore.org/events/", "baltimore.scrape_mtzion")

    try:
        scrape_firstpreshc = importlib.import_module("baltimore.scrape_firstpreshc")
        new_events += apply_source_tags(
            scrape_firstpreshc.scrape_events(),
            "https://www.firstpreshc.org/worship",
            ["Religion"],
        )
    except Exception as e:
        log_error("Error fetching First Presbyterian Howard County events", e, "https://www.firstpreshc.org/worship", "baltimore.scrape_firstpreshc")

    try:
        scrape_bridgeway = importlib.import_module("baltimore.scrape_bridgeway")
        new_events += apply_source_tags(
            scrape_bridgeway.scrape_events(),
            "https://bridgeway.cc/services",
            ["Religion"],
        )
    except Exception as e:
        log_error("Error fetching Bridgeway events", e, "https://bridgeway.cc/services", "baltimore.scrape_bridgeway")

    try:
        scrape_gardenchurch = importlib.import_module("baltimore.scrape_gardenchurch")
        new_events += apply_source_tags(
            scrape_gardenchurch.scrape_events(),
            "https://www.thegardenbaltimore.com/",
            ["Religion"],
        )
    except Exception as e:
        log_error("Error fetching The Garden Church events", e, "https://www.thegardenbaltimore.com/", "baltimore.scrape_gardenchurch")

    try:
        scrape_tedco = importlib.import_module("baltimore.scrape_tedco")
        new_events += apply_source_tags(
            scrape_tedco.scrape_tedco_events(months=2),
            "https://www.tedcomd.com/events/",
            ["Economic Development"],
        )
    except Exception as e:
        log_error("Error fetching tedco", e, "https://www.tedcomd.com/events/", "baltimore.scrape_tedco")

    try:
        scrape_baltsistercities = importlib.import_module("baltimore.scrape_baltsistercities")
        new_events += apply_source_tags(
            scrape_baltsistercities.scrape_baltimore_events(),
            "https://baltimoresistercities.org/events/",
            ["Community", "Culture"],
        )
    except Exception as e:
        log_error("Error fetching Sister Cities", e, "https://baltimoresistercities.org/events/", "baltimore.scrape_baltsistercities")

    for source in CUSTOM_SCRAPER_SOURCES:
        try:
            scraper_module = importlib.import_module(source["module"])
            scraper_fn = getattr(scraper_module, source["function"])
            scraped_events = scraper_fn()
            if not scraped_events:
                log_error(
                    "Custom scraper returned zero events",
                    RuntimeError("ZERO_EVENTS_PARSED"),
                    source["url"],
                    source["module"],
                    stage="ZERO_EVENTS_PARSED",
                )
                continue

            new_events += apply_source_tags(
                scraped_events,
                source["url"],
                source.get("tags", []),
                source.get("group_name", ""),
                source.get("orgImageUrl", ""),
            )
        except Exception as e:
            error_stage = getattr(e, "log_stage", "city_collect")
            log_error(
                f"Error fetching {source.get('group_name', source['url'])} events",
                e,
                source["url"],
                source["module"],
                stage=error_stage,
            )

    try:
        new_events += apply_source_tags(
            scrape_mtc.scrape_mtc_events(),
            "https://members.mdtechcouncil.com/eventcalendar",
            ["Business"],
        )
    except Exception as e:
        log_error("Error fetching MTC", e, "https://members.mdtechcouncil.com/eventcalendar", "scrape_mtc.scrape_mtc_events")

    for source in PROCESS_ICS_SOURCES:
        try:
            new_events += apply_source_tags(
                fetch_cached_ics_source(source),
                source["url"],
                source.get("tags", []),
                source.get("group_name", ""),
            )
        except Exception as e:
            log_error("Error fetching calendar events", e, source["url"], "scrape_ics.processICS")

    try:
        scrape_spark = importlib.import_module("baltimore.scrape_spark")
        new_events += apply_source_tags(
            scrape_spark.scrape_spark_events(),
            "https://sparkcoworking.com/baltimore/",
            ["Economic Development"],
        )
    except Exception as e:
        print(f"Error fetching calendar events: {e}")

    try:
        scrape_bwtech = importlib.import_module("baltimore.scrape_bwtech")
        new_events += apply_source_tags(
            scrape_bwtech.scrape_events(),
            "https://bwtech.umbc.edu/events/",
            ["Economic Development"],
        )
    except Exception as e:
        print(f"Error fetching calendar events: {e}")

    try:
        scrape_startup = importlib.import_module("baltimore.scrape_starTUp")
        new_events += apply_source_tags(
            scrape_startup.scrape_towson_events(),
            "https://www.towson.edu/startup/about/events.html",
            ["Business"],
        )
    except Exception as e:
        print(f"Error fetching calendar events: {e}")

    try:
        scrape_innovatemd = importlib.import_module("baltimore.scrape_innovatemd")
        new_events += apply_source_tags(
            scrape_innovatemd.scrape_all(),
            "https://innovationmaryland.org/events/",
            ["Economic Development"],
        )
    except Exception as e:
        print(f"Error fetching calendar events: {e}")

    try:
        scrape_wssc = importlib.import_module("baltimore.scrape_wssc")
        new_events += apply_source_tags(
            scrape_wssc.scrape_all_wssc_events(),
            "https://www.wsscwater.com/events",
            ["Water"],
        )
    except Exception as e:
        print(f"Error fetching WSSC events: {e}")

    try:
        scrape_bluewaterbaltimore = importlib.import_module("baltimore.scrape_bluewaterbaltimore")
        new_events += apply_source_tags(
            scrape_bluewaterbaltimore.scrape_events(city=city),
            "https://bluewaterbaltimore.org/events/",
            ["Water"],
        )
    except Exception as e:
        print(f"Error fetching Blue Water Baltimore events: {e}")

    try:
        scrape_waterfrontpartnership = importlib.import_module("baltimore.scrape_waterfrontpartnership")
        new_events += apply_source_tags(
            scrape_waterfrontpartnership.scrape_events(),
            "https://waterfrontpartnership.org/events/",
            ["Culture"],
        )
    except Exception as e:
        print(f"Error fetching Waterfront Partnership events: {e}")

    try:
        scrape_chesapeakewea = importlib.import_module("baltimore.scrape_chesapeakewea")
        new_events += apply_source_tags(
            scrape_chesapeakewea.scrape_events(),
            "https://chesapeakewea.org/events/",
            ["Water", "Professional Association", "Infrastructure"],
        )
    except Exception as e:
        print(f"Error fetching Chesapeake WEA events: {e}")

    try:
        scrape_csawwa = importlib.import_module("baltimore.scrape_csawwa")
        new_events += apply_source_tags(
            scrape_csawwa.scrape_events(),
            "https://csawwa.org/events/",
            ["Water"],
        )
    except Exception as e:
        print(f"Error fetching CSAWWA events: {e}")

    try:
        scrape_marylandforwardparty = importlib.import_module("baltimore.scrape_marylandforwardparty")
        new_events += apply_source_tags(
            scrape_marylandforwardparty.scrape_events(),
            "https://www.marylandforwardparty.com/get-involved",
            ["Politics"],
            "Maryland Forward Party",
            "https://static.wixstatic.com/media/d08726_f0a40763c1b0494d9747efd59718dced%7Emv2.png/v1/fill/w_192%2Ch_192%2Clg_1%2Cusm_0.66_1.00_0.01/d08726_f0a40763c1b0494d9747efd59718dced%7Emv2.png",
        )
    except Exception as e:
        print(f"Error fetching Maryland Forward Party events: {e}")

    try:
        scrape_mddems = importlib.import_module("baltimore.scrape_mddems")
        new_events += apply_source_tags(
            scrape_mddems.scrape_events(),
            "https://mddems.org/events/",
            ["Politics"],
            "Maryland Democratic Party",
            "https://mddems.org/wp-content/uploads/2023/05/MD-DEMS-LOGO.png",
        )
    except Exception as e:
        print(f"Error fetching MD Dems events: {e}")

    return new_events
