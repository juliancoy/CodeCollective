import json
with open("curriculum.json", 'r') as f:
    curriculum = json.loads(f.read())

def toHTML(indict, depth = 1):
    retstring = ""
    if type(indict) is not dict:
        return indict
    for k, v in indict.items():
        if k == "meta":
            continue
        if type(v) is dict and "meta" in v.keys() and "reference" in v["meta"].keys():
            retstring += f'<li><a href = {v["meta"]["reference"]}>{k}</a>' + "</li>\n"
            continue
        retstring += f"<h{depth}>{k}"
        if type(v) is dict and "meta" in v.keys() and "required" in v["meta"].keys():
            retstring += f' ({v["meta"]["required"][0]} Required)\n'
        retstring += f"</h{depth}>\n"
        retstring += "<ol>\n"
        retstring += f"{toHTML(v, depth=depth+1)}\n"
        retstring += "</ol>\n"
    return retstring

content = toHTML(curriculum)

with open("templates/placeholder.html", "r") as f:
    html_template = f.read()

content = html_template.replace("CONTENT", content)
"""Saves the HTML content to a file."""
filename = "curriculum.html"
with open(filename, "w+", encoding="utf-8") as file:
    file.write(content)
print(f"HTML file saved as {filename}")
