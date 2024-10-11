import requests
from bs4 import BeautifulSoup
import os


def download_google_doc_as_html(doc_id):
    url = f"https://docs.google.com/feeds/download/documents/export/Export?id={doc_id}&exportFormat=html"
    response = requests.get(url)
    if response.status_code != 200:
        print("Failed to download the document.")
    return response.text


def scrub_styles(html_content):
    soup = BeautifulSoup(html_content, "html.parser")

    # Remove the entire head tag
    if soup.head:
        soup.head.decompose()

    # Remove all style attributes from elements, except bold tags
    for tag in soup.find_all(True):  # True matches all tags
        if "style" in tag.attrs:
            # Preserve bold tags (strong and b) by skipping them
            if tag.name not in ["strong", "b"]:
                del tag.attrs["style"]

    # Extract the body content without the <html> and <head> tags
    if soup.body:
        return str(soup.body)[6:-7]  # Strip the <body> tags

    # fix an issue with the title
    # (not working. must be done manually for now)
    scrubbed = str(soup)
    scrubbed = scrubbed.encode("ascii", "ignore").decode("ascii")
    scrubbed = scrubbed.replace(
        'class="c5 doc-content"><div><p class="c0 c6"><span class="c2"></span></p></div><p class="c28 c27 c6 title" id="h.pinny9283ld5"><span class="c24"></span></p><p class="c27 c28 title" id="h.1iih1san2ov0"><span class="c24">Constitution and Bylaws</span></p><p class="c22"><span class="c24">',
        "<h1>Constitution and Bylaws of Baltimore Code Collective</h1>",
    )
    return scrubbed


def convert_to_html(doc_content):
    scrubbed_html = scrub_styles(doc_content)
    print(scrubbed_html)
    with open("templates/constitution-template.html", "r") as f:
        template = f.read()
    with open("constitution.html", "w+", encoding="utf-8") as file:
        file.write(template.replace("ORG_STRUCTURE", scrubbed_html))
    print("HTML document saved as constitution.html")


if __name__ == "__main__":
    google_doc_id = "165qyAEnNhpsRHSHNbQh6Q5TFea9YgmJftDFAeXLMcOY"
    html_content = download_google_doc_as_html(google_doc_id)
    if html_content:
        convert_to_html(html_content)
