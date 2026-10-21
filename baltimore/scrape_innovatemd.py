import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import json
import hashlib
from datetime import datetime
from zoneinfo import ZoneInfo
from http_client import build_session, polite_get

EVENTS_URL = "https://innovationmaryland.org/events/"
SESSION = build_session()

def generate_event_id(name, url):
    """Generate a unique ID for an event based on name and URL"""
    return hashlib.md5(f"{name}{url}".encode()).hexdigest()

def parse_event_date(date_str):
    """
    Parse event date string like 'October 30, 2025, 6 PM'
    Returns ISO format datetime string
    """
    for pattern in ("%B %d, %Y, %I %p", "%B %d, %Y, %I:%M %p"):
        try:
            dt = datetime.strptime(" ".join(date_str.split()), pattern)
            return dt.replace(tzinfo=ZoneInfo("America/New_York")).isoformat()
        except ValueError:
            continue
    return None


def get_event_urls(main_url):
    """
    Scrapes the main page to extract individual event URLs
    """
    print(f"Requesting main page: {main_url}")
    
    try:
        response = polite_get(SESSION, main_url, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        event_links = []
        fancy_boxes = soup.find_all('div', class_='nectar-fancy-box')
        
        for box in fancy_boxes:
            link = box.find('a', class_='box-link')
            if link and link.get('href'):
                full_url = urljoin(main_url, link['href'])
                
                # Extract event title
                heading = box.find('div', class_='heading-wrap')
                if heading:
                    # Remove the date icon/image
                    for img in heading.find_all('img'):
                        img.decompose()
                    title = heading.get_text(" ", strip=True)
                else:
                    title = "Unknown Event"
                
                event_links.append({
                    'url': full_url,
                    'title': title
                })
        
        return event_links
    
    except requests.RequestException as e:
        print(f"Error requesting main page: {e}")
        return []

def scrape_event_page(event_url, event_title):
    """
    Scrapes an individual event page and extracts structured data
    """
    print(f"\n{'='*60}")
    print(f"Scraping: {event_title}")
    print(f"URL: {event_url}")
    print('='*60)
    
    try:
        response = polite_get(SESSION, event_url, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Initialize event data
        event_data = {
            'id': generate_event_id(event_title, event_url),
            'name': event_title,
            'url': event_url,
            'status': 'ACTIVE',
            'recurring': False,
            'scrapeTime': datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        }
        
        # Extract description from the main content area
        # Look for the main descriptive text sections
        description_parts = []
        
        # Get all text column sections
        text_columns = soup.find_all('div', class_='wpb_text_column')
        for column in text_columns:
            # Skip the "Event Details" box and sponsor sections
            parent_col = column.find_parent('div', class_='wpb_column')
            if parent_col and parent_col.get('data-bg-color') == '#EAAA00':
                continue
            
            # Skip "Thank You to our Sponsors" section
            text = column.get_text()
            if 'Thank You to our Sponsors' in text or 'Speaker Request' in text:
                continue
            
            paragraphs = column.find_all('p')
            for p in paragraphs:
                text = p.get_text(" ", strip=True)
                # Skip empty paragraphs and single-word headers
                if text and len(text.split()) > 3:
                    description_parts.append(text)
        
        # Combine all description parts
        if description_parts:
            event_data['description'] = ' '.join(description_parts[:5])  # Limit to first 5 meaningful paragraphs
        
        # Extract event details (location, date, time)
        event_details_box = soup.find('div', {'data-bg-color': '#EAAA00'})
        if event_details_box:
            detail_text = event_details_box.get_text()
            
            # Extract location
            location_links = event_details_box.find_all('a', href=lambda x: x and 'maps.app.goo.gl' in x)
            if location_links:
                location_name = location_links[0].get_text(strip=True)
                location_address = location_links[1].get_text(strip=True) if len(location_links) > 1 else location_name
                event_data['location'] = {
                    'name': location_name,
                    'address': location_address
                }
            
            if 'location' not in event_data:
                location_match = re.search(
                    r"Location\s*:\s*(.*?)\s*Date & Time",
                    event_details_box.get_text(" ", strip=True),
                )
                if location_match:
                    location_text = location_match.group(1).strip()
                    event_data['location'] = {'name': location_text, 'address': location_text}

            # Extract date and time
            # Look for "Date & Time: " pattern
            if 'Date & Time' in detail_text:
                date_section = detail_text.split('Date & Time')[1].split('Tickets')[0]
                # Clean up the date string
                date_str = date_section.lstrip(' :\n\t').strip()
                parsed_date = parse_event_date(date_str)
                if parsed_date:
                    event_data['startDate'] = parsed_date
                    # The source does not publish an end time; do not invent one.
                    event_data['endTime'] = ''
        if not event_data.get('startDate'):
            return None
        event_data['source'] = EVENTS_URL

        # Extract image URL from the background image
        img_section = soup.find('div', class_='img-with-aniamtion-wrap')
        if img_section:
            img_tag = img_section.find('img')
            if img_tag and img_tag.get('src'):
                event_data['imageUrl'] = img_tag['src']
        
        print(f"✓ Successfully extracted event data")
        return event_data
    
    except requests.RequestException as e:
        print(f"✗ Error scraping event page: {e}")
        return None

def scrape_all():
    # Main page URL
    main_url = EVENTS_URL
    
    print("="*60)
    print("Innovation Maryland Event Scraper")
    print("="*60)
    
    # Get event URLs from main page
    events = get_event_urls(main_url)
    
    if not events:
        print("\nNo events found!")
        return []
    
    print(f"\nFound {len(events)} events:")
    for i, event in enumerate(events, 1):
        print(f"{i}. {event['title']}")
    
    # Scrape each event page
    all_event_data = []
    for event in events:
        event_data = scrape_event_page(event['url'], event['title'])
        if event_data and event_data['url'] not in {item['url'] for item in all_event_data}:
            all_event_data.append(event_data)
        
        # Shared HTTP client enforces per-host pacing and robots checks.
    
    # Summary
    print("\n" + "="*60)
    print(f"Successfully scraped {len(all_event_data)} out of {len(events)} events")
    print("="*60)

    return all_event_data
    
    

if __name__ == "__main__":
    all_event_data = scrape_all()

    # Output as JSON
    print("\n" + "="*60)
    print("JSON Output:")
    print("="*60)
    print(json.dumps(all_event_data, indent=2))
    
    # Save to file
    output_file = 'innovation_maryland_events.json'
    with open(output_file, 'w') as f:
        json.dump(all_event_data, f, indent=2)
    print(f"\n✓ Saved to {output_file}")
