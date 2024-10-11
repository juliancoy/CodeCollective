import os
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import datetime

# Base URL of your site
BASE_URL = "https://www.baltimorecodecollective.us"

# Directory where index.html is located
HTML_FILE = "index.html"

# Output sitemap file
SITEMAP_FILE = "sitemap.xml"


def extract_local_links(base_url, html_file):
    local_links = set()  # Use a set to avoid duplicates

    # Check if index.html exists
    if not os.path.isfile(html_file):
        print(f"{html_file} not found.")
        return local_links

    # Read and parse the HTML
    with open(html_file, "r", encoding="utf-8") as file:
        soup = BeautifulSoup(file, "html.parser")

    # Find all anchor tags with href attribute
    for link in soup.find_all("a", href=True):
        href = link["href"]

        # Only consider local links
        if href.startswith("/") or href.startswith("."):
            full_url = urljoin(base_url, href)
            local_links.add(full_url)

    return local_links


def generate_sitemap(links, output_file):
    # Get current date in W3C datetime format for <lastmod> tag
    current_date = datetime.datetime.now().strftime("%Y-%m-%d")

    # XML header for sitemap
    sitemap_header = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
"""

    # Generate URL entries
    url_entries = ""
    for link in links:
        url_entries += f"""  <url>
    <loc>{link}</loc>
    <lastmod>{current_date}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
  </url>
"""

    # XML footer
    sitemap_footer = """</urlset>
"""

    # Write the sitemap to file
    with open(output_file, "w", encoding="utf-8") as file:
        file.write(sitemap_header)
        file.write(url_entries)
        file.write(sitemap_footer)

    print(f"Sitemap generated: {output_file}")


# Main process
if __name__ == "__main__":
    # Step 1: Extract all local links from index.html
    local_links = extract_local_links(BASE_URL, HTML_FILE)

    # Step 2: Generate the sitemap.xml file
    if local_links:
        generate_sitemap(local_links, SITEMAP_FILE)
    else:
        print("No local links found.")
