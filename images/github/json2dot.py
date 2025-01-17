import json
import os
import subprocess
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
def json2dot(diagram):
    if not diagram or diagram.get('type') != 'graph':
        return ''

    # Start with graph definition
    direction = f"rankdir={diagram.get('direction', 'TD')};"
    dot_str = f"""digraph G {{\n{direction}\n
        // Graph styling
        bgcolor="transparent";

        // Node styling
        node [
            style="filled",
            color="white",
            fillcolor="black",
            fontcolor="white",
            shape="ellipse" // Default shape
        ];

        // Edge styling
        edge [
            color="yellow",
            style="dashed",
            fontcolor="yellow",
            penwidth=2,
            style="setlinewidth(2), dashed(5,3)" // Custom dash pattern
        ];

    """
    # Add nodes
    for node in diagram.get('nodes', []):
        label = node.get('label', '')
        shape = node.get('shape', '').lower()  # Get the shape, default to empty string
        # Set the shape based on the value of node["shape"]
        if shape == 'circle':
            node_shape = 'ellipse'  # DOT uses 'ellipse' for circles
        elif shape == 'square':
            node_shape = 'box'  # DOT uses 'box' for squares
        else:
            node_shape = 'ellipse'  # Default shape
        dot_str += f'    {node["id"]} [label="{label}", shape="{node_shape}"];\n'
    
    # Add edges
    for edge in diagram.get('edges', []):
        label = edge.get('label', '')
        dot_str += f'    {edge["from"]} -> {edge["to"]} [label="{label}"];\n'
    
    dot_str += "}\n"
    return dot_str

# Render DOT diagram to image
def render_dot(diagram_code, output_file):
    # Write styled DOT diagram to a temporary file
    temp_dot_file = output_file + '.dot'
    with open(temp_dot_file, 'w') as f:
        f.write(diagram_code)
     # Prepare the Graphviz command
    command = ['dot', '-Tpng', temp_dot_file, '-Gsize=20,20', '-Gdpi=300', '-o', output_file]
    print(" ".join(command))
    # Run the Graphviz command
    subprocess.run(command)
    return output_file

# Generate HTML for a single step
def step2html(step, index):
    diagram_content = (
        f"<img class='innerimage' src='{step.get('URL')}' />" if step.get('URL') else
        ""
    )
    
    swipe_text = "➡️"
    
    return f"""
    <div class="step">
        <h3>{index}. {step['Step']}</h3>
        <div class="diagram">{diagram_content}</div>
        <p>{step['Description']}</p>
        <div class="swipe">{swipe_text}</div>
    </div>
    """


# Generate HTML for a single step
titleHTML =f"""
    <div class="step">
        <h3>GitHub Basic Proficiency</h3>
        <div class="diagram"><img class='innerimage' src='http://localhost:8000/images/github/github.avif' /></div>
        <h3>A Guide</h3>
        <div class="swipe">➡️</div>
    </div>
    """


# Generate HTML for a single step
conclusionHTML =f"""
    <div class="step">
        <h3>GitHub Basic Proficiency</h3>
        <div class="diagram"><img class='innerimage' src='http://localhost:8000/images/github/github.avif' /></div>
        <p>Get Certified at Code Collective!</p>
        <div class="swipe">codecollective.us</div>
    </div>
    """

def setup_browser(aspect=1920.0/1080):
    chrome_options = Options()
    chrome_options.add_argument('--headless')  # Run in headless mode
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')

    # Set the path to the ChromeDriver
    service = Service('/usr/bin/chromedriver')  # Update this to the actual path
    browser = webdriver.Chrome(service=service, options=chrome_options)

    # Set the window size to 1:1.91 aspect ratio (LinkedIn recommended size)
    width = 1080  # Width in pixels
    height = int(width * aspect)  # Calculate height based on the aspect ratio
    browser.set_window_size(width, height)  # Set the browser window size

    return browser


from PIL import Image
from PIL import Image

def images_to_pdf(images, output_pdf, quality=95):
    """
    Combines images into a PDF with reduced compression.
    
    Parameters:
    - images: List of image file paths.
    - output_pdf: Path to save the output PDF.
    - quality: Integer (1-100), higher values mean better quality but larger file size.
    """
    # Ensure all images are opened and converted to RGB mode
    img_list = []
    for img_path in images:
        img = Image.open(img_path)
        if img.mode != 'RGB':  # Convert to RGB if not already
            img = img.convert('RGB')
        img_list.append(img)
    
    # Save all images into a single PDF with reduced compression
    if img_list:
        img_list[0].save(
            output_pdf, 
            save_all=True, 
            append_images=img_list[1:], 
            quality=quality  # Set quality for reduced compression
        )
    else:
        print("No images to process!")

def html2image(html_in, browser, output_dir="screenshots", index=0):

    temp_file = os.path.join(output_dir, f"step_{index}.html")

    # Save temporary HTML
    with open(temp_file, 'w') as f:
        f.write(html_in)
    
    # Load the temporary HTML file in the browser
    browser.get(f"file://{os.path.abspath(temp_file)}")

    try:
        WebDriverWait(browser, 1).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '.step'))
        )
        print("HTML rendered successfully.")
    except TimeoutException:
        print(f"Warning: Content not found for step {index}. Skipping screenshot.")
        return

    # Take a screenshot
    screenshot_path = os.path.join(output_dir, f"step_{index}.png")
    browser.save_screenshot(screenshot_path)
    print(f"Saved screenshot for step {index}: {screenshot_path}")
    return screenshot_path

# Generate screenshots for each step
def process_steps(steps, output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    browser = setup_browser()

    # Create a temporary HTML template
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
    <link rel="stylesheet" href="http://localhost:8000/images/github/index.css">
    </head>
    <body>
        <div id="steps-container"></div>
    </body>
    </html>
    """
    images = []
    title = html_template.replace('<div id="steps-container"></div>', titleHTML)
    screenshot_path = html2image(title, browser, index="intro")
    images += [screenshot_path]

    for index, step in enumerate(steps):
        if step.get('Diagram'):
            step["URL"] = "http://localhost:8000/images/github/" + render_dot(json2dot(step.get('Diagram')), f"screenshots/dot_{index}.png")
        else:
            step["URL"] = "http://localhost:8000" + step["URL"] 
        step_html = step2html(step, index)

        html_with_step = html_template.replace('<div id="steps-container"></div>', step_html)
        screenshot_path = html2image(html_with_step, browser, index=index)
        images += [screenshot_path]

    conclusion = html_template.replace('<div id="steps-container"></div>', conclusionHTML)
    screenshot_path = html2image(conclusion, browser, index="conclusion")
    images += [screenshot_path]

    # Example usage
    output_pdf = "output.pdf"
    print(images)
    images_to_pdf(images, output_pdf)
    print(f"PDF saved to {output_pdf}")
    #browser.quit()

# Main function
def main():
    steps_file = 'steps.json'
    output_dir = 'screenshots'

    if not os.path.exists(steps_file):
        print("Error: steps.json file not found")
        return

    with open(steps_file, 'r') as f:
        steps = json.load(f)

    if not isinstance(steps, list):
        print("Error: Invalid steps.json format")
        return

    for index, step in enumerate(steps):
        step['isLast'] = (index == len(steps) - 1)

    process_steps(steps, output_dir)

if __name__ == "__main__":
    main()
