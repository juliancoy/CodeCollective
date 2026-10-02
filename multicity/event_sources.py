from city_source_taxonomy import apply_city_source_taxonomy

# Add organizations here that host events across multiple city regions.
# Example:
# {
#     "url": "https://www.meetup.com/example-org/",
#     "group_name": "Example Org",
#     "tags": ["Tech Community", "Professional Networking"],
# }
sources = [
    {
        "url": "https://luma.com/bill",
        "group_name": "Bill's Journey Into AI",
        "orgImageUrl": "https://images.lumacdn.com/calendars/c1/49b78549-857b-462a-9e6f-1ab6ebde6d6c.jpg",
        "tags": ["Tech Skills", "AI", "Tech Community", "Web3"],
    },
    {
        "url": "https://www.eventbrite.com/o/11206981546",
        "tags": ["Tech Community", "Professional Networking", "Career Growth"],
    },
]

apply_city_source_taxonomy(sources)
