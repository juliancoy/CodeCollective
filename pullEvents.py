import requests
import json
from bs4 import BeautifulSoup
import datetime
from html import escape
import pytz

# Define the timezone for EST
utc_timezone = pytz.timezone("UTC")
est_timezone = pytz.timezone("US/Eastern")

# URL of the Baltimore Code Collective Meetup group
MEETUP_URL = "https://www.meetup.com/code-collective/"


def fetch_meetup_page(url):
    """Fetches the HTML content of the Meetup page."""
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception(f"Failed to retrieve page: {response.status_code}")
    return response.text


def parse_meetup_html(page_content):
    """Parses the HTML content of the Meetup page and extracts event data in JSON format."""
    soup = BeautifulSoup(page_content, "html.parser")

    # Find the script tag containing the events JSON (based on the structure observed in your file)
    script_tags = soup.find_all("script", type="application/ld+json")

    events_json = None
    for script in script_tags:
        try:
            json_data = json.loads(script.string)
            if isinstance(json_data, list):
                # Look for the events data
                events_json = [
                    item for item in json_data if item.get("@type") == "Event"
                ]
                if events_json:
                    break
        except json.JSONDecodeError:
            continue

    if not events_json:
        raise Exception("No events data found in the HTML page.")

    return events_json


def create_html(events):
    """Creates an HTML string for the events."""
    html_content = "<h1>Upcoming Events for Baltimore Code Collective</h1>"

    if not events:
        html_content += "<p>No upcoming events at this time.</p>"
    else:
        for event in events:
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
            event_location = event.get("location", {}).get(
                "name", "No location available"
            )
            event_link = event.get("url", "#")

            html_content += f"""
                <div>
                    <h2><a href="{event_link}" target="_blank">{event_name}</a></h2>
                    <h3>Date and Time:</h3>
                    {event_date} EST
                    <h3>Location</h3>
                    {event_location}
                    <h3>Description</h3>
                    {event_description}
                </div>
                <hr>
            """
    return html_content


def save_html_file(content, filename="calendar.html"):
    """Saves the HTML content to a file."""
    with open(filename, "w", encoding="utf-8") as file:
        file.write(content)
    print(f"HTML file saved as {filename}")


if __name__ == "__main__":
    # Fetch the Meetup page content
    page_content = fetch_meetup_page(MEETUP_URL)

    # Parse the Meetup page HTML for event data
    events = parse_meetup_html(page_content)

    # Create HTML content for the events
    html_content = create_html(events)

    with open("templates/events-template.html", "r") as f:
        html_template = f.read()

    # Save the HTML content to a file
    save_html_file(html_template.replace("EVENTS_HTML", html_content))
