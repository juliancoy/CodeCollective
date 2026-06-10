from city_source_taxonomy import apply_city_source_taxonomy
from urllib.parse import urlparse

sources = [
    {
        "name": "Baltimore Tech Meetup",
        "url": "https://www.meetup.com/baltimore-tech/events/",
        "tags": ["Economic Development", "Tech Community"],
    },
    {
        "name": "DevOps Columbia",
        "url": "https://www.meetup.com/devops-columbia/events/",
        "tags": ["Tech Skills", "DevOps", "Cloud & Platform"],
    },
    {
        "name": "Baltimore Code and Coffee",
        "url": "https://www.meetup.com/baltimore-code-and-coffee/events/",
        "tags": ["Tech Skills", "Software Development", "Tech Community"],
    },
    {
        "name": "Baltimore CryptoMondays",
        "url": "https://www.meetup.com/baltimore-cryptomondays/events/",
        "tags": ["Finance", "Crypto & Web3"],
    },
    {
        "name": "Ellicott City Cryptocurrency Meetup",
        "url": "https://www.meetup.com/ellicott-city-cryptocurrency-meetup-group/events/",
        "tags": ["Finance", "Crypto & Web3"],
    },
    {
        "name": "IT Social East US Data Technology Cybersecurity",
        "url": "https://www.meetup.com/it-social-east-us-ca-data-technology-cybersecurity/events/",
        "tags": ["Tech Skills", "Cybersecurity", "Data Science", "Tech Community"],
    },
    {
        "name": "Baltimore WordPress Group",
        "url": "https://www.meetup.com/the-baltimore-wordpress-group/events/",
        "tags": ["Tech Skills", "Web Development"],
    },
    {
        "name": "Baltimore Bayesians",
        "url": "https://www.meetup.com/baltimore-bayesians/events/",
        "tags": ["Tech Skills", "AI", "Data Science"],
    },
    {
        "name": "DataWorks",
        "url": "https://www.meetup.com/dataworks/events/",
        "tags": ["Tech Skills", "Data Science"],
    },
    {
        "name": "Baltimore Veg Vegan Meetup",
        "url": "https://www.meetup.com/baltimoreveg-vegan/",
        "tags": ["Food", "Health", "Culture"],
    },
    {
        "name": "Charm City Eats",
        "url": "https://www.meetup.com/charmcityeats/",
        "tags": ["Food", "Culture", "Community"],
    },
    {
        "name": "Farmers Market Supper Club",
        "url": "https://www.meetup.com/the-farmers-market-supper-club/",
        "tags": ["Food", "Community", "Culture"],
    },
    {
        "name": "Whole Food for Optimal Health Baltimore",
        "url": "https://www.meetup.com/whole-food-for-optimal-health-potluck/",
        "tags": ["Community", "Food"],
    },
    {
        "name": "Baltimore Foodies on a Budget",
        "url": "https://www.meetup.com/meetup-group-SNifIHBM/",
        "tags": ["Community", "Food"],
    },
    {
        "name": "Plant-Based Baltimore",
        "url": "https://www.meetup.com/plant-based-recipes-exchange/",
        "tags": ["Community", "Food"],
    },
    {
        "name": "DMV Affordable Housing Meetup",
        "url": "https://www.meetup.com/dmv-affordable-housing-meetup/",
        "tags": ["Shelter", "Politics", "Community"],
    },
    {
        "name": "Cohousing of Greater Baltimore",
        "url": "https://www.meetup.com/cohousing-of-greater-baltimore/",
        "tags": ["Shelter", "Community", "Culture"],
    },
    {
        "name": "Baltimore Bitcoin",
        "url": "https://www.meetup.com/baltimorebitcoin/events/",
        "tags": ["Finance", "Crypto & Web3"],
    },
    {
        "name": "Maryland Blockchain Association Meetup",
        "url": "https://www.meetup.com/www-marylandblockchainassociation-org/",
        "tags": ["Finance", "Crypto & Web3", "Tech Community"],
    },
    {
        "name": "LFDT Maryland",
        "url": "https://www.meetup.com/lfdt-maryland/",
        "tags": ["Crypto & Web3", "Tech Community"],
    },
    {
        "name": "Distributed Computing Maryland",
        "url": "https://www.meetup.com/distributedcomputingmd/",
        "tags": ["Crypto & Web3", "Tech Community"],
    },
    {
        "name": "Fintech Maryland",
        "url": "https://www.meetup.com/fintech-maryland/",
        "tags": ["Finance", "Tech Community"],
    },
    {
        "name": "Essex Bitcoin for Beginners",
        "url": "https://www.meetup.com/essex-bitcoin-for-beginners-meetup-group/",
        "tags": ["Finance", "Crypto & Web3"],
    },
    {
        "name": "Python Frederick",
        "url": "https://www.meetup.com/python-frederick/events/",
        "tags": ["Tech Skills", "Python", "Software Development"],
    },
    {
        "name": "Business Connection Network",
        "url": "https://www.meetup.com/the-business-connection-network/",
        "tags": ["Business", "Tech Community"],
    },
    {
        "name": "Baltimore UX Meetup",
        "url": "https://www.meetup.com/baltimore-ux-meetup/",
        "tags": ["Tech Skills", "UX", "Product"],
    },
    {
        "name": "Baltimore SDN",
        "url": "https://www.meetup.com/baltomsdn/",
        "tags": ["Tech Skills", "Cloud & Platform"],
    },
    {
        "name": "Pitch Labs",
        "url": "https://www.meetup.com/pitch-labs/",
        "tags": ["Business"],
    },
    {
        "name": "Baltimore Hackerspace",
        "url": "https://www.meetup.com/Baltimore-Hackerspace/",
        "orgImageUrl": "https://baltimorehackerspace.com/wp-content/uploads/2013/06/bahalogotop.png",
        "tags": ["Makerspace", "Tech Community"],
    },
    {
        "name": "Maryland Red Hat User Group",
        "url": "https://www.meetup.com/maryland-red-hat-user-group/",
        "tags": ["Tech Skills", "DevOps", "Cloud & Platform"],
    },
    {
        "name": "Columbia Politics Meetup",
        "url": "https://www.meetup.com/columbia-politics-meetup-group/",
        "tags": ["Politics"],
    },
    {
        "name": "AI Performance Engineering Washington DC",
        "url": "https://www.meetup.com/ai-performance-engineering-washington-dc/",
        "tags": ["Tech Skills", "AI", "Cloud & Platform"],
    },
    {
        "name": "Philanthropicode",
        "url": "https://www.meetup.com/philanthropicode/",
        "tags": [
            "Code Collective & Partners",
            "Community Organizing",
            "Tech Community",
        ],
    },
    {
        "name": "Profs and Pints Baltimore",
        "url": "https://www.meetup.com/profs-and-pints-baltimore/",
        "tags": ["Education", "Science", "Lifelong Learning"],
    },
    {
        "name": "AI Enthusiasts",
        "url": "https://www.meetup.com/ai-enthusiasts/",
        "tags": ["Tech Skills", "AI"],
    },
    {
        "name": "KMC Maryland",
        "url": "https://www.meetup.com/KMC-Maryland/",
        "tags": ["Religion"],
    },
    {
        "name": "Bmore Ethical",
        "url": "https://www.meetup.com/bmorethical/",
        "tags": ["Religion", "Economic Development"],
    },
    {
        "name": "Meditation Modern Buddhism Canton",
        "url": "https://www.meetup.com/meditation-modern-buddhism-in-canton/",
        "tags": ["Religion"],
    },
    {
        "name": "Baltimore Tech Innovation",
        "url": "https://www.meetup.com/baltimore-tech-innovation/",
        "tags": ["Economic Development"],
    },
    {
        "name": "CMAP Online",
        "url": "https://www.meetup.com/cmap-online/",
        "tags": ["Business"],
    },
    {
        "name": "Cyber STEAM Global Innovation Alliance",
        "url": "https://www.meetup.com/cyber-steam-global-innovation-alliance/",
        "tags": ["Tech Skills", "Cybersecurity"],
    },
    {
        "name": "Maryland Forward Party",
        "url": "https://www.meetup.com/marylandforwardparty/",
        "tags": ["Politics"],
    },
    {
        "name": "Charm City Angels Capital Coffee",
        "url": "https://www.meetup.com/charm-city-angels-capital-coffee/",
        "tags": ["Finance"],
    },
    {
        "name": "GRID Baltimore",
        "url": "https://www.meetup.com/grid-baltimore/",
        "tags": ["Finance", "Professional Networking"],
    },
    {
        "name": "Baltimore Real Estate Investing Meetup Group",
        "url": "https://www.meetup.com/baltimore-real-estate-investing-meetup-group/",
        "tags": ["Finance", "Professional Networking"],
    },
    {
        "name": "Baltimore Investors Meetup",
        "url": "https://www.meetup.com/baltimoreinvestors/",
        "tags": ["Finance", "Professional Networking"],
    },
    {
        "name": "BetterInvesting Maryland",
        "url": "https://www.meetup.com/betterinvesting-maryland-stock-investing-education/",
        "tags": ["Finance", "Education"],
    },
    {
        "name": "Cash-Flow Breakfast Club Baltimore",
        "url": "https://www.meetup.com/the-cash-flow-breakfast-club-baltimore-md-rei/",
        "tags": ["Finance", "Professional Networking"],
    },
    {
        "name": "Baltimore Black Techies",
        "url": "https://www.meetup.com/baltimore-black-techies-meetup/",
        "tags": ["Economic Development", "Tech Community", "Community Organizing"],
    },
    # Eventbrite
    {
        "name": "Tential Tech Tuesday",
        "url": "https://www.eventbrite.com/e/tential-tech-tuesday-tickets-1366415157519",
        "tags": ["Business"],
    },
    {
        "name": "TECHSPO Baltimore 2025",
        "url": "https://www.eventbrite.com/e/techspo-baltimore-2025-technology-expo-internet-adtech-martech-tickets-1114708064829",
        "tags": ["Business", "Tech Community", "Startup"],
    },
    {
        "name": "Maryland Makerspace Meetup 2025",
        "url": "https://www.eventbrite.com/e/2025-md-makerspace-meetup-tickets-1345760890049",
        "tags": ["Makerspace"],
    },
    {
        "name": "Baltimore Data Day 2025",
        "url": "https://www.eventbrite.com/e/baltimore-data-day-state-of-our-neighborhoods-2025-tickets-1424508315719",
        "tags": ["Economic Development"],
    },
    {
        "name": "EnergyConnect Baltimore",
        "url": "https://www.eventbrite.com/e/energyconnect-virtual-job-networking-hub-for-energy-professionals-baltimore-tickets-1434086875449",
        "tags": ["Infrastructure"],
    },
    {
        "name": "BLK Tech Connect",
        "url": "https://www.eventbrite.com/o/blk-tech-connect-107618183651",
        "tags": ["Economic Development", "Tech Community"],
    },
    {
        "name": "Open Works Baltimore",
        "url": "https://www.eventbrite.com/o/open-works-86343210063",
        "orgImageUrl": "https://www.openworksbmore.org/wp-content/uploads/2021/04/openworks-logo.svg",
        "tags": ["Makerspace"],
    },
    {
        "name": "Baltimore Underground Science Space",
        "url": "https://www.eventbrite.com/o/baltimore-under-ground-science-space-bugss-4318633291",
        "orgImageUrl": "https://bugssonline.org/wp-content/themes/BUGS3/assets/images/bugsslogo-square300.png",
        "tags": ["Makerspace"],
    },
    {
        "name": "IT Social Baltimore Eventbrite",
        "url": "https://www.eventbrite.com.au/o/it-social-baltimore-110781946041",
        "tags": ["Tech Skills", "Cybersecurity", "Data Science", "Tech Community"],
    },
    {
        "name": "Eventbrite Baltimore Collection",
        "url": "https://www.eventbrite.com/cc/baltimore-4326703",
        "tags": ["Business"],
    },
    {
        "name": "Maryland Blockchain Association Monthly Virtual Meetups",
        "url": "https://www.eventbrite.com/e/maryland-blockchain-association-monthly-virtual-meet-ups-tickets-1134555268349",
        "tags": ["Finance", "Crypto & Web3", "Tech Community"],
    },
    {
        "name": "Impact Hub Baltimore",
        "url": "https://www.eventbrite.com/o/impact-hub-baltimore-8423440202",
        "tags": ["Business"],
    },
    {
        "name": "A Prosperous Tomorrow",
        "url": "https://www.eventbrite.com/o/a-prosperous-tomorrow-11875462384",
        "tags": ["Business"],
    },
    {
        "name": "Lets Go Organization",
        "url": "https://www.eventbrite.com/o/lets-go-113135073431",
        "tags": ["Economic Development", "Youth Education"],
    },
    {
        "name": "Howard County Workforce Development",
        "url": "https://www.eventbrite.com/o/howard-county-office-of-workforce-development-88843319173",
        "tags": ["Economic Development"],
    },
    {
        "name": "Howard County Economic Development Authority",
        "url": "https://www.eventbrite.com/o/howard-county-economic-development-authority-2805856464",
        "tags": ["Economic Development"],
    },
    {
        "name": "RMI Events",
        "url": "https://www.eventbrite.com/o/rmi-107139765",
        "tags": ["Water"],
    },
    {
        "name": "Nachman Executive Consulting",
        "url": "https://www.eventbrite.com/o/nachman-executive-consulting-77249254883",
        "tags": ["Business"],
    },
    {
        "name": "Vashtiblue Jewelry Studio",
        "url": "https://www.eventbrite.com/o/vashtiblue-jewelry-studio-120729155482",
        "tags": ["Business"],
    },
    {
        "name": "Baltimore Robotics Center",
        "url": "https://www.eventbrite.com/o/baltimore-robotics-center-14997527925",
        "orgImageUrl": "https://www.baltimoreroboticscenter.com/wp-content/uploads/2021/02/cropped-Balto-Robotics-CTR-logo-new.png",
        "tags": ["Makerspace", "Robotics"],
    },
    {
        "name": "Fight Blight Baltimore",
        "url": "https://www.eventbrite.com/o/fight-blight-bmore-18309938620",
        "tags": ["Water"],
    },
    {
        "name": "IMET Events",
        "url": "https://www.eventbrite.com/o/79181486483",
        "tags": ["Business"],
    },
    {
        "name": "Center for Entrepreneurship and Innovation",
        "url": "https://www.eventbrite.com/o/34179073381",
        "tags": ["Business"],
    },
    {
        "name": "NSBE Baltimore",
        "url": "https://www.eventbrite.com/o/11070919734",
        "tags": ["Business"],
    },
    {
        "name": "Baltimore Roundtable for Economic Development",
        "url": "https://www.eventbrite.com/o/30286628672",
        "tags": ["Business", "Politics", "Economic Development"],
    },
    # Luma / others
    {
        "name": "Luma Event 2d1a4uwv",
        "url": "https://luma.com/2d1a4uwv",
        "tags": ["Business"],
    },
    {
        "name": "Luma Water Calendar",
        "url": "https://lu.ma/calendar/cal-vzms1nGZmYUUCrj",
        "tags": ["Water"],
    },
    {
        "name": "Bmore Climate",
        "url": "https://lu.ma/Bmore_Climate",
        "tags": ["Water", "Tech Community"],
    },
    {
        "name": "BLK Tech Connect Luma",
        "url": "https://luma.com/blk-tech-connect-baltimore",
        "tags": ["Economic Development", "Tech Community", "Community Organizing"],
    },
    {
        "name": "Charm City JS",
        "url": "https://lu.ma/user/charmcityjs",
        "tags": ["Tech Skills", "JavaScript", "Software Development"],
    },
    {
        "name": "MTech UMD",
        "url": "https://lu.ma/mtechumd",
        "tags": ["Economic Development"],
    },
    {
        "name": "Luma Economic Development Calendar",
        "url": "https://luma.com/calendar/cal-MVw6HVCN4MEFaNV",
        "tags": ["Economic Development"],
    },
    {
        "name": "Techstars AI Health Baltimore",
        "url": "https://luma.com/calendar/cal-vtTwduv5AoHTdyg",
        "tags": ["Health", "Tech Community", "AI", "Startup"],
    },
    {
        "name": "Code Collective",
        "url": "https://luma.com/codecollective",
        "group_name": "Code Collective",
        "orgImageUrl": "/images/general_encircled.png",
        "tags": [
            "Code Collective & Partners",
            "Tech Community",
            "Community Organizing",
        ],
    },
    {
        "name": "Bmore on Rails",
        "url": "https://luma.com/bmore-on-rails",
        "tags": ["Tech Skills", "Ruby", "Software Development"],
    },
    {
        "name": "Lets BMore",
        "url": "https://lu.ma/LetsBMore",
        "tags": ["Economic Development", "Tech Community"],
    },
    {"name": "MEIA", "url": "https://luma.com/MEIA", "tags": ["Economic Development"]},
    {"name": "UMBC CHE", "url": "https://luma.com/umbcche", "tags": ["Business"]},
    {
        "name": "SGLang Meetups",
        "url": "https://luma.com/SGLang-meetups",
        "tags": ["Tech Skills", "AI"],
    },
    {
        "name": "Luma User d4s75dZyC9VOXAd",
        "url": "https://api.lu.ma/user/profile/events-hosting?user_api_id=usr-d4s75dZyC9VOXAd",
        "tags": ["Business"],
    },
    {
        "name": "Luma User iZFykYNctUzTFLd",
        "url": "https://api.lu.ma/user/profile/events-hosting?user_api_id=usr-iZFykYNctUzTFLd",
        "tags": ["Economic Development"],
    },
    {
        "name": "BMNT Ventures",
        "url": "https://api.lu.ma/user/profile/events-hosting?user_api_id=usr-WdW6dzEEpKMRMGq",
        "group_name": "BMNT Ventures",
        "tags": ["Business", "Startup"],
    },
    {
        "name": "Baltimore Sister Cities Events",
        "url": "https://baltimoresistercities.org/events/",
        "tags": ["Community", "Tech Community"],
    },
    {
        "name": "Backwater Books Events",
        "url": "https://backwaterbooks.com/events",
        "tags": ["Culture", "Community", "Lifelong Learning"],
    },
    {
        "name": "Baltimore Orioles Schedule",
        "url": "https://www.mlb.com/orioles/schedule",
        "tags": ["Culture", "Community", "Economic Development"],
    },
    {
        "name": "Baltimore Ravens Schedule",
        "url": "https://www.baltimoreravens.com/schedule/",
        "tags": ["Culture", "Community", "Economic Development"],
    },
    {
        "name": "CFG Bank Arena Events",
        "url": "https://cfgbankarena.com/events/",
        "tags": ["Culture", "Community", "Economic Development"],
    },
    {
        "name": "Baltimore Convention Center Events",
        "url": "https://www.bccenter.org/events/",
        "tags": ["Culture", "Community", "Economic Development"],
    },
    {
        "name": "Web3 Maryland",
        "url": "https://api.lu.ma/user/profile/events-hosting?user_api_id=usr-A83YmR5Onz1uMdp",
        "group_name": "Web3 Maryland",
        "orgImageUrl": "https://images.lumacdn.com/avatars/4g/431276ef-4081-4db7-a077-9a45da105826.png",
        "tags": [
            "Finance",
            "Crypto & Web3",
            "Tech Skills",
            "AI",
            "Economic Development",
            "Tech Community",
        ],
    },
    {
        "name": "Luma User k0oO7FswDxbAWh0",
        "url": "https://api.lu.ma/user/profile/events-hosting?user_api_id=usr-k0oO7FswDxbAWh0",
        "tags": ["Business"],
    },
    {
        "name": "Luma User cTlmPNsi6jHYweP",
        "url": "https://api.lu.ma/user/profile/events-hosting?user_api_id=usr-cTlmPNsi6jHYweP",
        "tags": ["Health & Wellness", "Culture", "Community"],
    },
    {
        "name": "Luma User 2eWBPcn6lj9Dzqz",
        "url": "https://api.lu.ma/user/profile/events-hosting?user_api_id=usr-2eWBPcn6lj9Dzqz",
        "tags": ["Tech Community"],
    },
    # Medical / Wellness sources
    {
        "name": "NAMI Metro Baltimore Events",
        "url": "https://namibaltimore.org/get-involved/events/",
        "tags": ["Health", "Wellness", "Community", "Community Organizing"],
    },
    {
        "name": "Baltimore City Health Department Events",
        "url": "https://health.baltimorecity.gov/events",
        "tags": ["Health", "Community", "Community Organizing"],
    },
    {
        "name": "UMMC Community Health Outreach",
        "url": "https://www.umms.org/ummc/community/events",
        "tags": ["Health", "Wellness", "Community"],
    },
    {
        "name": "Baltimore Eventbrite Medical Events",
        "url": "https://www.eventbrite.com/b/md--baltimore/health/medical/",
        "tags": ["Health", "Wellness", "Community"],
    },
    {
        "name": "Central Maryland Fibromyalgia Support Group",
        "url": "https://www.vitality101.com/node/2919",
        "tags": ["Health", "Wellness", "Community"],
    },
    {
        "name": "The Chronically ChILL Meetup Group",
        "url": "https://www.meetup.com/the-chronically-chill-meetup-group/",
        "tags": ["Health", "Belonging"],
    },
    {
        "name": "Chronic Illness Outdoors Club",
        "url": "https://www.meetup.com/chronic-illness-outdoors-club/",
        "tags": ["Health", "Belonging"],
    },
    {
        "name": "Baltimore Cancer Support Group Calendar",
        "url": "https://baltimorecancersupportgroup.org/?page_id=53",
        "tags": ["Health", "Belonging"],
    },
    {
        "name": "HopeWell Cancer Support Program Events",
        "url": "https://www.hopewellcancersupport.org/programs/programevents",
        "tags": ["Health", "Belonging"],
    },
    {
        "name": "American Lung Association Better Breathers Baltimore",
        "url": "https://www.lung.org/get-involved/events/find-an-event/26578-bbc-baltimore-md",
        "tags": ["Health", "Belonging"],
    },
    {
        "name": "LifeBridge Grace Medical Community Calendar",
        "url": "https://www.lifebridgehealth.org/events/community-calendar",
        "tags": ["Health", "Growth"],
    },
    {
        "name": "Baltimore County Diabetes Support Group",
        "url": "https://www.baltimorecountymd.gov/departments/aging/events/diabetes-support-group",
        "tags": ["Health", "Belonging"],
    },
    {
        "name": "Fibromyalgia Association Support and Education Group",
        "url": "https://www.managefibromyalgia.org/supportgroup",
        "tags": ["Health", "Belonging"],
    },
    {
        "name": "Meetup Fibromyalgia Support Groups",
        "url": "https://www.meetup.com/topics/fibromyalgia-support-groups/",
        "tags": ["Health", "Wellness", "Community"],
    },
    # Phase 2 direct source expansion (non-platform)
    {
        "name": "Maryland Food Bank Events",
        "url": "https://mdfoodbank.org/events/category/foodworks/",
        "tags": ["Culture", "Food", "Safety", "Belonging"],
    },
    {
        "name": "Moveable Feast Events",
        "url": "https://www.mfeast.org/events/",
        "tags": ["Health", "Food", "Safety", "Belonging"],
    },
    {
        "name": "Baltimore Free Farm Events",
        "url": "https://www.baltimorefreefarm.org/events/",
        "tags": ["Culture", "Food", "Growth", "Belonging"],
    },
    {
        "name": "Farm Alliance Field Day Workshops",
        "url": "https://www.eventbrite.com/o/farm-alliance-of-baltimore-33824037405",
        "tags": ["Environment", "Food", "Growth", "Belonging"],
    },
    {
        "name": "St Ambrose Housing Aid Center Events",
        "url": "https://www.stambros.org/support-our-mission/events-calendar/",
        "tags": ["Culture", "Shelter", "Safety", "Belonging"],
    },
    {
        "name": "Baltimore DHCD Events",
        "url": "https://dhcd.baltimorecity.gov/events/list",
        "tags": ["Politics", "Shelter", "Safety", "Purpose"],
    },
    {
        "name": "Blue Water Baltimore Events",
        "url": "https://bluewaterbaltimore.org/events/photo/",
        "tags": ["Environment", "Water", "Safety", "Purpose"],
    },
    {
        "name": "Waterfront Partnership Waterfront Week",
        "url": "https://www.waterfrontpartnership.org/waterfrontweek",
        "tags": ["Environment", "Water", "Belonging", "Purpose"],
    },
    {
        "name": "Parks and People Events",
        "url": "https://www.parksandpeople.org/events",
        "tags": ["Environment", "Safety", "Belonging", "Growth"],
    },
    {
        "name": "Sheppard Pratt Events",
        "url": "https://www.sheppardpratt.org/events/",
        "tags": ["Health", "Safety", "Belonging", "Growth"],
    },
    {
        "name": "UMMC Community Events",
        "url": "https://www.umms.org/ummc/community/events",
        "tags": ["Health", "Safety", "Belonging", "Growth"],
    },
    # Phase 3 sector gap expansion
    {
        "name": "CFA Society Baltimore Upcoming Events",
        "url": "https://community.cfainstitute.org/baltimore/society-events/upcoming-events",
        "tags": ["Finance", "Education", "Esteem", "Growth"],
    },
    {
        "name": "Maryland Bankers Association Events",
        "url": "https://www.mdbankers.com/education-events/calendar/conferences-seminars-schools/",
        "tags": ["Finance", "Education", "Esteem", "Growth"],
    },
    {
        "name": "Makerspace at Johns Hopkins Events",
        "url": "https://makerspace.jhu.edu/events/",
        "tags": ["Makerspace", "Technology", "Growth", "Belonging"],
    },
    {
        "name": "Open Works Class and Workshop Schedule",
        "url": "https://www.openworksbmore.org/schedule/",
        "tags": ["Makerspace", "Education", "Growth", "Belonging"],
    },
    {
        "name": "League of Women Voters Baltimore City Events",
        "url": "https://www.lwv-baltimorecity.org/events",
        "tags": ["Politics", "Culture", "Purpose", "Belonging"],
    },
    {
        "name": "League of Women Voters Baltimore County Events",
        "url": "https://www.lwvbaltimorecounty.org/",
        "tags": ["Politics", "Culture", "Purpose", "Belonging"],
    },
    {
        "name": "Baltimore Unity Hall Civic Calendar",
        "url": "https://www.baltimoreunityhall.org/calendar",
        "tags": ["Politics", "Culture", "Purpose", "Belonging"],
    },
    {
        "name": "Baltimore Neighborhood Indicators Community Change Events",
        "url": "https://bniajfi.org/currentprojects/baltimore-community-change-events/",
        "tags": ["Politics", "Community Organizing", "Purpose", "Belonging"],
    },
    {
        "name": "Beth El Congregation Calendar",
        "url": "https://bethelbalto.com/calendar/",
        "tags": ["Faith", "Culture", "Belonging", "Purpose"],
    },
    {
        "name": "Chizuk Amuno Congregation Programs and Events",
        "url": "https://www.chizukamuno.org/",
        "tags": ["Faith", "Culture", "Belonging", "Growth"],
    },
    {
        "name": "Zion Church Baltimore Calendar",
        "url": "https://www.zionbaltimore.org/",
        "tags": ["Faith", "Culture", "Belonging", "Purpose"],
    },
    # Phase 4 remaining Maslow gaps
    {
        "name": "BUILD Baltimore",
        "url": "https://www.buildiaf.org/calendar/events/",
        "tags": ["Culture", "Politics", "Shelter", "Purpose", "Safety"],
    },
    {
        "name": "House of Ruth Maryland Fundraising Events",
        "url": "https://hruth.org/get-involved/fundraising-events/",
        "tags": ["Health", "Culture", "Shelter", "Safety", "Purpose"],
    },
    {
        "name": "My Sisters Place Womens Center",
        "url": "https://cc-md.org/get-involved/events/",
        "tags": ["Health", "Culture", "Shelter", "Safety", "Belonging"],
    },
    {
        "name": "Changing Lives Baltimore Coat Drive",
        "url": "https://changinglivesinitiativ.org/events/",
        "tags": ["Culture", "Clothing", "Safety", "Belonging", "Purpose"],
    },
    {
        "name": "Pratt Compassion Clothing Closet",
        "url": "https://calendar.prattlibrary.org/event/compassion-clothing-closet",
        "tags": ["Culture", "Clothing", "Safety", "Belonging"],
    },
    {
        "name": "Maryland Food Bank Baltimore Office",
        "url": "https://mdfoodbank.org/events/",
        "tags": ["Culture", "Food", "Safety", "Belonging"],
    },
    {
        "name": "Maryland Food Bank Volunteer and Access Programs",
        "url": "https://mdfoodbank.org/events/",
        "tags": ["Culture", "Food", "Safety", "Belonging"],
    },
    {
        "name": "Maryland Food Bank Pantry on the Go",
        "url": "https://mdfoodbank.org/events/",
        "tags": ["Culture", "Food", "Safety", "Belonging"],
    },
    {
        "name": "Moveable Feast Volunteer and Meal Access",
        "url": "https://www.mfeast.org/events-calendar/",
        "tags": ["Health", "Food", "Safety", "Belonging"],
    },
    {
        "name": "Baltimore Hunger Project",
        "url": "https://www.baltimorehungerproject.org/events/today/",
        "tags": ["Culture", "Food", "Safety", "Belonging"],
    },
    {
        "name": "Hunger Free Zone Baltimore",
        "url": "https://hungerfreezone.org/schedule/",
        "tags": ["Culture", "Food", "Safety", "Belonging"],
    },
    {
        "name": "Blue Water Baltimore Volunteer Opportunities",
        "url": "https://bluewaterbaltimore.org/volunteer-opportunities-baltimore/",
        "tags": ["Environment", "Water", "Safety", "Purpose", "Belonging"],
    },
    {
        "name": "Collide Capital @ JHU (Partiful)",
        "url": "https://partiful.com/e/IjvnMmmJOBBvkAIsYjTN",
        "tags": ["Business", "Startup", "Tech Community"],
    },
    {
        "name": "Google Form Submission",
        "url": "http://docs.google.com/forms/d/e/1FAIpQLSfAHwexta7vxLto1xmvBxFNawicAUtRrjTKqN0jHs25RjLCQg/viewform",
        "tags": ["Business"],
    },
    {
        "name": "Google Developer Group Chapter 3047",
        "url": "https://gdg.community.dev/chapter/3047",
        "tags": ["Tech Community", "Software Development"],
        "chapter_id": 3047,
    },
    {
        "name": "WordPress Frederick",
        "url": "https://www.meetup.com/wordpress-frederick/",
        "tags": ["Tech Community", "Software Development"],
    },
    # Phase 5 Maryland and local government source expansion
    {
        "name": "Maryland Department of the Environment Events",
        "url": "https://mde.maryland.gov/Pages/default.aspx",
        "tags": ["MarylandGov", "Politics", "Environment", "Water", "Purpose"],
    },
    {
        "name": "Maryland Department of Natural Resources Events",
        "url": "https://dnr.maryland.gov/Pages/default.aspx",
        "tags": ["MarylandGov", "Politics", "Environment", "Water", "Community"],
    },
    {
        "name": "Maryland Department of Planning Events",
        "url": "https://planning.maryland.gov/Pages/default.aspx",
        "tags": ["MarylandGov", "Politics", "Economic Development", "Infrastructure", "Purpose"],
    },
    {
        "name": "Maryland Department of Housing and Community Development Events",
        "url": "https://dhcd.maryland.gov/Pages/default.aspx",
        "tags": ["MarylandGov", "Politics", "Shelter", "Community", "Safety"],
    },
    {
        "name": "Maryland Commission on Civil Rights Events",
        "url": "https://mccr.maryland.gov/Pages/Events.aspx",
        "tags": ["MarylandGov", "Politics", "Community Organizing", "Belonging", "Purpose"],
    },
    {
        "name": "Baltimore City Council Legislative Calendar",
        "url": "https://baltimore.legistar.com/Calendar.aspx",
        "tags": ["MarylandGov", "Politics", "Community", "Purpose"],
    },
    {
        "name": "Harford County Government Calendar",
        "url": "https://www.harfordcountymd.gov/calendar.aspx",
        "tags": ["MarylandGov", "Politics", "Community", "Education", "Purpose"],
    },
    {
        "name": "Howard County Government Workforce Events Calendar",
        "url": "https://www.howardcountymd.gov/workforce-development/events-calendar",
        "tags": ["MarylandGov", "Community", "Education", "Belonging", "Growth"],
    },
    {
        "name": "Inner Arbor Trust Events",
        "url": "https://innerarbortrust.org/events",
        "tags": ["Culture", "Community", "Belonging", "Growth"],
    },
    {
        "name": "Prince George's Parks Events",
        "url": "https://www.pgparks.com/events",
        "tags": ["MarylandGov", "Politics", "Community", "Economic Development", "Purpose"],
    },
    {
        "name": "Enoch Pratt Free Library Events",
        "url": "https://www.prattlibrary.org/events",
        "tags": ["MarylandGov", "Politics", "Community", "Infrastructure", "Purpose"],
    },
    {
        "name": "Thread Baltimore Upcoming Events",
        "url": "https://my.thread.org/api/v2/help_center/en-us/categories/360005554572/articles.json",
        "orgImageUrl": "https://www.thread.org/wp-content/uploads/2021/01/thread-official-trademarked-logo.png",
        "tags": ["Education", "Community", "Belonging", "Purpose"],
    },
    {
        "name": "St John Baptist Church",
        "url": "https://sjbc.org/events/",
        "orgImageUrl": "https://sjbc.org/wp-content/uploads/2023/01/sjbc_logo.png",
        "tags": ["Religion", "Education", "Community"],
    },
    {
        "name": "Montgomery County Council Legislative Calendar",
        "url": "https://montgomerycountymd.legistar.com/Calendar.aspx",
        "tags": ["MarylandGov", "Politics", "Infrastructure", "Economic Development", "Purpose"],
    },
    {
        "name": "Greater Baltimore Urban League",
        "url": "https://www.eventbrite.com/o/2103730749",
        "tags": ["Business", "Economic Development"],
    }
]


def _derive_group_name(source: dict) -> str:
    name = str(source.get("group_name") or source.get("name") or "").strip()
    if name:
        return name
    url = str(source.get("url") or "").strip()
    if "://" in url:
        host = url.split("://", 1)[1].split("/", 1)[0].replace("www.", "").strip()
        if host:
            return host
    return "Organization"


def _ensure_org_image_urls(source_list: list[dict]) -> None:
    for source in source_list:
        if source.get("orgImageUrl"):
            continue
        url = str(source.get("url") or "").strip()
        if not url:
            continue
        host = urlparse(url).netloc.replace("www.", "").strip()
        if not host:
            continue
        source["orgImageUrl"] = f"https://www.google.com/s2/favicons?domain={host}&sz=256"


_ensure_org_image_urls(sources)
apply_city_source_taxonomy(sources)
