from urllib.parse import urljoin
from bs4 import BeautifulSoup
import json
from datetime import datetime
from typing import List, Dict, Optional
import time
from http_client import build_session, polite_get

class LumaCalendarScraper:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        self.session = build_session()
    
    def scrape_calendar(self, calendar_url: str) -> List[Dict]:
        """
        Scrape events from a Luma calendar page.
        
        Args:
            calendar_url: URL of the Luma calendar (e.g., https://lu.ma/calendar/cal-XXX)
        
        Returns:
            List of event dictionaries in the specified format
        """
        try:
            response = polite_get(self.session, calendar_url, headers=self.headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find the __NEXT_DATA__ script tag
            next_data_script = soup.find('script', {'id': '__NEXT_DATA__'})
            if not next_data_script:
                raise ValueError("Could not find __NEXT_DATA__ script tag")
            
            # Parse the JSON data
            data = json.loads(next_data_script.string)
            
            # Extract events from the initial data
            events = []
            initial_data = data.get('props', {}).get('pageProps', {}).get('initialData', {})
            
            # Handle both direct featured_items and nested under 'data' key
            featured_items = initial_data.get('featured_items', [])
            if not featured_items and 'data' in initial_data:
                featured_items = initial_data.get('data', {}).get('featured_items', [])
            
            for item in featured_items:
                event_data = item.get('event')
                if not event_data:
                    continue
                try:
                    event = self._parse_event(event_data, item)
                    if event:
                        events.append(event)
                except Exception as parse_error:
                    print(f"Error parsing event: {parse_error}")
                    continue
            
            return events
            
        except Exception as e:
            print(f"Error scraping calendar: {e}")
            return []
    
    def scrape_event_details(self, event_url: str) -> Optional[Dict]:
        """
        Scrape detailed information from an individual event page.
        
        Args:
            event_url: Full URL or slug of the event
        
        Returns:
            Event dictionary with detailed information including description
        """
        if not event_url.startswith('http'):
            event_url = f"https://lu.ma/{event_url}"
        
        try:
            print(f"Scraping {event_url}")
            response = polite_get(self.session, event_url, headers=self.headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            next_data_script = soup.find('script', {'id': '__NEXT_DATA__'})
            
            if not next_data_script:
                return None
            
            data = json.loads(next_data_script.string)
            event_data = data.get('props', {}).get('pageProps', {}).get('initialData', {}).get('event', {})
            
            if event_data:
                return self._parse_event_detailed(event_data)
            
            return None
            
        except Exception as e:
            print(f"Error scraping event details: {e}")
            return None
    
    def _parse_event(self, event_data: Dict, item_data: Dict = None) -> Optional[Dict]:
        """Parse event data from the calendar view (without description)."""
        event_id = event_data.get('api_id', '')
        name = event_data.get('name', '')
        start_at = event_data.get('start_at', '')
        end_at = event_data.get('end_at', '')
        url_slug = event_data.get('url', '')
        
        # Get location info with all available fields
        geo_info = event_data.get('geo_address_info', {})
        location = {
            'name': geo_info.get('address', ''),
            'address': geo_info.get('full_address', ''),
            'city': geo_info.get('city', ''),
            'state': geo_info.get('region', ''),
            'country': geo_info.get('country', ''),
        }
        
        # Get coordinates if available
        coord = event_data.get('coordinate', {})
        if coord:
            location['latitude'] = coord.get('latitude', '')
            location['longitude'] = coord.get('longitude', '')
        
        # Get cover image
        cover_url = event_data.get('cover_url', '')
        
        # Build full URL
        full_url = urljoin("https://lu.ma/", url_slug) if url_slug else ''
        
        return {
            'id': event_id,
            'name': name,
            'startDate': start_at,
            'endTime': end_at,
            'description': '',
            'url': full_url,
            'status': 'ACTIVE',
            'location': location,
            'imageUrl': cover_url,
            'recurring': False,
            'scrapeTime': datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
        }
        
        # Get cover image
        cover_url = event_data.get('cover_url', '')
        
        # Build full URL
        full_url = urljoin("https://lu.ma/", url_slug) if url_slug else ''
        
        return {
            'id': event_id,
            'name': name,
            'startDate': start_at,
            'endTime': end_at,
            'description': '',  # Empty from calendar view
            'url': full_url,
            'status': 'ACTIVE',
            'location': location,
            'imageUrl': cover_url,
            'recurring': False,
            'scrapeTime': datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
        }
    
    def _parse_event_detailed(self, event_data: Dict) -> Dict:
        """Parse detailed event data from an individual event page."""
        event_id = event_data.get('api_id', '')
        name = event_data.get('name', '')
        start_at = event_data.get('start_at', '')
        end_at = event_data.get('end_at', '')
        url_slug = event_data.get('url', '')
        
        # Get description - this is available on individual event pages
        description = event_data.get('description', '')
        
        # Get location info
        geo_info = event_data.get('geo_address_info', {})
        location = {
            'name': geo_info.get('address', ''),
            'address': geo_info.get('full_address', '')
        }
        
        # Get cover image
        cover_url = event_data.get('cover_url', '')
        
        # Build full URL
        full_url = urljoin("https://lu.ma/", url_slug) if url_slug else ''
        
        # Check if it's a recurring event
        recurring = event_data.get('recurrence_id') is not None
        
        return {
            'id': event_id,
            'name': name,
            'startDate': start_at,
            'endTime': end_at,
            'description': description,
            'url': full_url,
            'status': 'ACTIVE',
            'location': location,
            'imageUrl': cover_url,
            'recurring': recurring,
            'scrapeTime': datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
        }
    
    def scrape_with_details(self, calendar_url: str, delay: float = 1.0) -> List[Dict]:
        """
        Scrape calendar and then fetch details (including descriptions) for each event.
        
        Args:
            calendar_url: URL of the Luma calendar
            delay: Delay in seconds between requests to avoid rate limiting
        
        Returns:
            List of event dictionaries with detailed information including descriptions
        """
        events = self.scrape_calendar(calendar_url)
        detailed_events = []
        
        for event in events:
            if event.get('url'):
                print(f"Fetching details for: {event['name']}")
                detailed = self.scrape_event_details(event['url'])
                if detailed:
                    detailed_events.append(detailed)
                else:
                    # Fall back to basic event data if detailed fetch fails
                    detailed_events.append(event)
                time.sleep(delay)
            else:
                detailed_events.append(event)
        
        return detailed_events

def scrape(calendar_url = "https://lu.ma/calendar/cal-NjFsB6d9nrGCLdW"):
    scraper = LumaCalendarScraper()
    
    # Option 1: Just scrape calendar (no descriptions)
    events = scraper.scrape_calendar(calendar_url)
    print(f"Scraped {len(events)} events from calendar (no descriptions)")
    return events
    
import sys
# Example usage
if __name__ == "__main__":
    scrape(sys.argv[1])
