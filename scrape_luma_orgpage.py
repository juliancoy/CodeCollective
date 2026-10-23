from urllib.parse import urljoin
import json
import re
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
from http_client import build_session, polite_get


def _normalize_image_url(url: str) -> str:
    if not url:
        return ""
    value = str(url).strip()
    if not value or value.startswith("data:"):
        return ""
    if value.startswith("//"):
        return f"https:{value}"
    if value.startswith("http://"):
        return "https://" + value[len("http://"):]
    return value

def fetch_and_parse_luma_events(url: str) -> List[Dict[str, Any]]:
    """
    Fetch a Luma URL and parse events from it.
    
    Args:
        url (str): The Luma URL to fetch and parse
        
    Returns:
        List[Dict[str, Any]]: List of parsed events in the specified format
    """
    # Add headers to mimic a real browser request
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
    }
    
    # Fetch the URL
    session = build_session()
    response = polite_get(session, url, headers=headers, timeout=30)
    response.raise_for_status()  # Raise an exception for bad status codes
    
    # Parse the HTML content
    return parse_luma_events(response.text, url)
        

def parse_luma_events(html_content: str, source_url: str = '') -> List[Dict[str, Any]]:
    """
    Parse events from Luma HTML content and return them in the specified format.
    
    Args:
        html_content (str): The HTML content containing JSON-LD structured data
        source_url (str): The source URL where the events were scraped from
        
    Returns:
        List[Dict[str, Any]]: List of parsed events in the specified format
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    json_ld_events = parse_json_ld_events(soup, source_url)
    next_data_events = parse_next_data_events(soup, source_url)

    if len(next_data_events) > len(json_ld_events):
        return next_data_events

    return json_ld_events


def parse_json_ld_events(soup: BeautifulSoup, source_url: str = '') -> List[Dict[str, Any]]:
    json_ld_script = soup.find('script', {'type': 'application/ld+json'})
    if not json_ld_script or not json_ld_script.string:
        return []

    try:
        json_data = json.loads(json_ld_script.string)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON-LD: {e}")
        return []

    events = json_data.get('events', [])
    parsed_events = []

    org_image_url = ""
    organizer = json_data.get("organizer")
    if isinstance(organizer, dict):
        raw_img = organizer.get("image")
        if isinstance(raw_img, list) and raw_img:
            org_image_url = _normalize_image_url(raw_img[0])
        elif isinstance(raw_img, str):
            org_image_url = _normalize_image_url(raw_img)

    for event in events:
        parsed_event = parse_single_event(event, source_url, org_image_url=org_image_url)
        if parsed_event:
            parsed_events.append(parsed_event)

    return parsed_events


def parse_next_data_events(soup: BeautifulSoup, source_url: str = '') -> List[Dict[str, Any]]:
    next_data_script = soup.find('script', {'id': '__NEXT_DATA__'})
    if not next_data_script or not next_data_script.string:
        return []

    try:
        next_data = json.loads(next_data_script.string)
    except json.JSONDecodeError as e:
        print(f"Error parsing __NEXT_DATA__: {e}")
        return []

    initial_data = next_data.get('props', {}).get('pageProps', {}).get('initialData', {})
    calendar_data = initial_data.get('data', {}) if initial_data.get('kind') == 'calendar' else {}
    featured_items = calendar_data.get('featured_items', [])
    org_image_url = _normalize_image_url(calendar_data.get("avatar_url", ""))

    parsed_events = []
    for item in featured_items:
        event_data = item.get('event', {})
        parsed_event = parse_next_data_event(event_data, source_url, org_image_url=org_image_url)
        if parsed_event:
            parsed_events.append(parsed_event)

    return parsed_events

def parse_single_event(event: Dict[str, Any], source_url: str = '', org_image_url: str = '') -> Optional[Dict[str, Any]]:
    """
    Parse a single event from JSON-LD format to the target format.
    
    Args:
        event (Dict[str, Any]): Single event data from JSON-LD
        source_url (str): The source URL where the event was scraped from
        
    Returns:
        Optional[Dict[str, Any]]: Parsed event in target format, or None if parsing fails
    """
    # Extract basic event information
    name = event.get('name', '')
    description = event.get('description', '')
    start_date = event.get('startDate', '')
    end_date = event.get('endDate', '')
    event_url = event.get('@id', '')
    
    # Determine status based on eventStatus
    event_status = event.get('eventStatus', '')
    status = 'ACTIVE' if 'EventScheduled' in event_status else 'INACTIVE'
    
    # Extract location information
    location_data = event.get('location', {})
    location = parse_location(location_data)
    
    # Extract image URL
    images = event.get('image', [])
    image_url = images[0] if images and isinstance(images, list) else images if isinstance(images, str) else ''
    image_url = _normalize_image_url(image_url) or org_image_url
    
    # Build the parsed event
    parsed_event = {
        'name': name,
        'description': description,
        'startDate': start_date,
        'endTime': end_date,  # Note: using endTime as per the target format
        'url': event_url,
        'status': status,
        'location': location,
        'imageUrl': image_url,
        'orgImageUrl': org_image_url or image_url,
        'source': source_url
    }
    
    return parsed_event


def parse_next_data_event(event: Dict[str, Any], source_url: str = '', org_image_url: str = '') -> Optional[Dict[str, Any]]:
    if not event:
        return None

    geo_info = event.get('geo_address_info', {}) or {}
    location = {
        'name': geo_info.get('address', ''),
        'address': geo_info.get('full_address', '')
    }

    url_slug = event.get('url', '')
    event_url = urljoin("https://luma.com/", url_slug) if url_slug else source_url

    event_image_url = _normalize_image_url(event.get('cover_url', '')) or org_image_url
    return {
        'name': event.get('name', ''),
        'description': event.get('description', ''),
        'startDate': event.get('start_at', ''),
        'endTime': event.get('end_at', ''),
        'url': event_url,
        'status': 'ACTIVE',
        'location': location,
        'imageUrl': event_image_url,
        'orgImageUrl': org_image_url or event_image_url,
        'source': source_url
    }
    

def parse_location(location_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Parse location information from JSON-LD format.
    
    Args:
        location_data (Dict[str, Any]): Location data from event
        
    Returns:
        Dict[str, str]: Parsed location with name and address
    """
    location = {
        'name': '',
        'address': ''
    }
    
    if not location_data:
        return location
    
    # Extract location name
    location['name'] = location_data.get('name', '')
    
    # Extract address information
    address_data = location_data.get('address', {})
    if isinstance(address_data, dict):
        address_parts = []
        
        # Build address from components
        street_address = address_data.get('streetAddress', '')
        locality = address_data.get('addressLocality', '')
        region = address_data.get('addressRegion', '')
        country_data = address_data.get('addressCountry', {})
        
        if street_address:
            address_parts.append(street_address)
        if locality:
            address_parts.append(locality)
        if region:
            address_parts.append(region)
        
        # Handle country (could be string or object)
        if isinstance(country_data, dict):
            country_name = country_data.get('name', '')
            if country_name and country_name != 'United States':
                address_parts.append(country_name)
        elif isinstance(country_data, str) and country_data != 'United States':
            address_parts.append(country_data)
        
        location['address'] = ', '.join(address_parts)
    
    elif isinstance(address_data, str):
        # If the address is a plain string, just use it directly
        location['address'] = address_data

    return location


def parse_multiple_urls(urls: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Parse events from multiple Luma URLs.
    
    Args:
        urls (List[str]): List of Luma URLs to parse
        
    Returns:
        Dict[str, List[Dict[str, Any]]]: Dictionary mapping URLs to their parsed events
    """
    results = {}
    
    for url in urls:
        print(f"Processing: {url}")
        events = fetch_and_parse_luma_events(url)
        results[url] = events
        print(f"Found {len(events)} events")
        
    return results

import sys
if __name__ == "__main__":

    """
    Example usage of the parser with a Luma URL.
    """
    # Example URL
    url = sys.argv[1]
    
    print(f"Fetching and parsing events from: {url}")
    print("=" * 60)
    
    # Fetch and parse events from the URL
    events = fetch_and_parse_luma_events(url)
    
    if not events:
        print("No events found or error occurred.")
        sys.exit(1)
    
    print(f"Found {len(events)} event(s):")
    print("=" * 60)
    
    # Print the results
    for i, event in enumerate(events, 1):
        print(f"Event {i}:")
        print(json.dumps(event, indent=2))
        print("-" * 50)
