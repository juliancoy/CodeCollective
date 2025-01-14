import requests
import json
from bs4 import BeautifulSoup
import datetime
from html import escape
import markdown
import pytz

# Define the timezone for EST
utc_timezone = pytz.timezone("UTC")
est_timezone = pytz.timezone("America/New_York")

# URL of the Baltimore Code Collective Meetup group
MEETUP_URL = "https://www.meetup.com/code-collective/"


def fetch_meetup_page(url):
    """Fetches the HTML content of the Meetup page."""
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception(f"Failed to retrieve page: {response.status_code}")
    return response.text

def parse_meetup_html(page_content):
    """
    Parses the HTML content of the Meetup page and extracts event data in JSON format.
    Includes event details and associated images.
    
    Args:
        page_content (str): The HTML content of the Meetup page
        
    Returns:
        list: List of event dictionaries containing event details and image URLs
    """
    soup = BeautifulSoup(page_content, "html.parser")
    
    # Find the script tag containing the events JSON
    script_tags = soup.find_all("script", type="application/ld+json")
    
    events_json = None
    for script in script_tags:
        try:
            json_data = json.loads(script.string)
            if isinstance(json_data, list):
                # Look for events with @type == "Event"
                events = []
                for item in json_data:
                    if item.get("@type") == "Event":
                        event_data = item.copy()
                        
                        # Extract standard image URL if available
                        if "image" in event_data:
                            event_data["imageUrl"] = event_data.pop("image")
                            
                        # Look for additional high-res image if available
                        # This might be nested in featuredEventPhoto or other fields
                        if "featuredEventPhoto" in event_data:
                            if "highResUrl" in event_data["featuredEventPhoto"]:
                                event_data["highResImageUrl"] = event_data["featuredEventPhoto"]["highResUrl"]
                        
                        events.append(event_data)
                
                if events:
                    events_json = events
                    break
                
        except json.JSONDecodeError:
            continue
            
    return events_json

def create_html(events, seriesName):
    """Creates an HTML string for the events, including event images."""
    html_content = f"<h1>{seriesName}</h1>"

    if not events:
        html_content += "<p>No upcoming events at this time.</p>"
    else:
        for index, event in enumerate(events):
            print(json.dumps(event, indent=2))
            event_name = escape(event.get("name", "No title available"))
            event_date = event.get("startDate", "No date available")
            # Assuming event_date is in ISO format with 'Z' at the end, indicating UTC
            event_date = datetime.datetime.fromisoformat(event_date.replace("Z", ""))
            # Convert to UTC timezone first
            event_date = utc_timezone.localize(event_date)
            # Then convert to EST
            event_date_est = event_date.astimezone(est_timezone)

            # Format the date into a string as required
            event_date = event_date_est.strftime("%Y-%m-%d %H:%M:%S")

            event_description = escape(
                event.get("description", "No description available")
            )
            event_description = markdown.markdown(event_description).replace("strong>", "b>")

            event_location = event.get("location", {}).get(
                "name", "No location available"
            )
            event_link = event.get("url", "#")
            
            # Get the image URL, with fallback to None if not available
            event_image = event.get("imageUrl")
            image_html = ""
            if event_image:
                image_html = f"""
                    <div class="event-image">
                        <img src="{event_image}" alt="{event_name}" class="event-thumbnail">
                    </div>
                """
            
            # Alternate the layout for each event
            if index % 2 == 0:
                layout_class = "event-card-left"
            else:
                layout_class = "event-card-right"
                
            html_content += f"""
                <div class="event-card {layout_class}">
                    <div class="event-content">
                        <h2 class="event-title">
                            <a href="{event_link}" target="_blank">{event_name}</a>
                        </h2>
                        <div class="event-detail">
                            <h4 class="event-date">{event_date} EST</h4>
                            <p class="event-location">@{event_location}</p>
                            {image_html}
                        </div>
                    </div>
                </div>
                <hr class="divider">
            """
    return html_content

if __name__ == "__main__":
    # Fetch the Meetup page content
    page_content = fetch_meetup_page(MEETUP_URL)
    with open("meetup.html", "w+") as f:
        f.write(page_content)

    # Parse the Meetup page HTML for event data
    events = parse_meetup_html(page_content)

    # Create HTML content for the events
    html_content = create_html(events, "Code Collective Workshop Series at Dear Globe")

    with open("templates/events-template.html", "r") as f:
        html_template = f.read()

    # Save the HTML content to a file
    html_template = html_template.replace("EVENTS_HTML", html_content)

    """Saves the HTML content to a file."""
    with open("series.html", "w", encoding="utf-8") as file:
        file.write(html_template)
    print(f"HTML file saved as {"series.html"}")
