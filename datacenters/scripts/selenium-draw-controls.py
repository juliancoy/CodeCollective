#!/usr/bin/env python3
"""Browser acceptance for shared plant scaling and nationwide power profiles."""

import argparse
import importlib.util
import json
from pathlib import Path

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait


SPEC = importlib.util.spec_from_file_location("smoke", Path(__file__).with_name("selenium-datacenters-smoke.py"))
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)


def run(args):
    driver = smoke.new_driver(args.selenium_url, args.width, args.height)
    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {'source': """
        window.__drawControlErrors = [];
        window.addEventListener('error', event => { if (event.error) window.__drawControlErrors.push(event.message); });
        window.addEventListener('unhandledrejection', event => window.__drawControlErrors.push(String(event.reason)));
    """})
    screenshots = Path(args.screenshot_dir)
    screenshots.mkdir(parents=True, exist_ok=True)
    wait = WebDriverWait(driver, 60)
    report = {}

    def plant_entries():
        return driver.execute_script("return window.__codeCollectiveDatacenterMap.getLayer('power-plant-bolt-webgl')?.implementation?.getExportEntries()")

    def open_settings(layer):
        driver.execute_script("document.querySelector('[data-layer-config=" + layer + "]').click()")

    def apply_settings(field, value):
        driver.execute_script("""
            const form = document.getElementById('layer-filter-form');
            form.elements[arguments[0]].value = arguments[1];
            form.requestSubmit();
        """, field, value)

    try:
        driver.get(args.base_url)
        smoke.wait_for_map_ready(driver)
        for layer in ('global-power-plants', 'nacei-power-plants'):
            smoke.set_checkbox(driver, 'show-' + layer, True)
            wait.until(lambda d: 'Loading' not in d.find_element(By.ID, layer.replace('power-plants', 'power-plant') + '-scope-status').text)
        before = wait.until(lambda _: plant_entries())
        report['plant_count'] = len(before)
        assert any(row['id'].startswith('eia-') for row in before)
        assert any(row['id'].startswith('wri-') for row in before)
        assert any(row['id'].startswith('nacei-') for row in before)
        control = driver.find_element(By.ID, 'power-plant-scale')
        driver.execute_script("""
            arguments[0].value = '2';
            arguments[0].dispatchEvent(new Event('input', {bubbles: true}));
            arguments[0].dispatchEvent(new Event('change', {bubbles: true}));
        """, control)
        before_sizes = {row['id']: row['size'] for row in before}
        after = wait.until(lambda _: (rows if (rows := plant_entries()) and abs(rows[0]['size'] - before_sizes[rows[0]['id']] * 2) < .0001 else None))
        assert len(after) == len(before)
        assert all(abs(row['size'] - before_sizes[row['id']] * 2) < .0001 for row in after)
        report['all_sources_scaled_by'] = 2
        open_settings('power-plants')
        assert driver.find_element(By.CSS_SELECTOR, '#layer-filter-form [name=iconScale]').get_attribute('value') == '2'
        apply_settings('sizeBy', 'none')
        wait.until(lambda _: all(abs(row['size'] - 72) < .0001 for row in plant_entries()))
        current_url = driver.current_url
        driver.execute_script("localStorage.clear()")
        driver.get(current_url)
        smoke.wait_for_map_ready(driver)
        wait.until(lambda _: len(plant_entries() or []) == len(before))
        assert driver.find_element(By.ID, 'power-plant-scale').get_attribute('value') == '2'
        assert all(abs(row['size'] - 72) < .0001 for row in plant_entries())
        report['uniform_size_and_url_restore'] = True
        open_settings('power-plants')
        driver.find_element(By.ID, 'reset-layer-filter').click()
        assert driver.find_element(By.ID, 'power-plant-scale').get_attribute('value') == '1'
        driver.execute_script("document.getElementById('layer-filter-modal').close()")
        for layer in ('power-plants', 'global-power-plants', 'nacei-power-plants', 'datacenters',
                      'data-center-moratoriums', 'neon-streets'):
            smoke.set_checkbox(driver, 'show-' + layer, False)

        layer = 'openstreetmap-us-data-centers'
        smoke.set_checkbox(driver, 'show-' + layer, True)
        report['coverage'] = wait.until(lambda d: (text if 'with power data' in (text := d.find_element(By.ID, 'status-' + layer).text) else None))
        open_settings(layer)
        options = driver.execute_script("return [...document.querySelector('#layer-filter-form [name=sizeBy]').options].map(o => [o.value, o.text])")
        required = {'reported_grid_demand_mw', 'reported_power_capacity_mw', 'projected_power_demand_mw', 'estimated_power_draw_mw'}
        assert required <= {option[0] for option in options}
        assert 'osm_id' not in {option[0] for option in options}
        assert 'power data coverage' in driver.find_element(By.ID, 'layer-filter-modal').text.lower()
        report['draw_options'] = [option for option in options if option[0] in required]
        report['settings_screenshot'] = str(smoke.save_screenshot(driver, screenshots, 'us-draw-settings.png'))
        apply_settings('sizeBy', 'reported_power_capacity_mw')

        data = driver.execute_async_script("""
            const done = arguments[arguments.length - 1];
            Promise.all([fetch('/datacenters/data/data-centers-openstreetmap-us.json').then(r=>r.json()),
              fetch('/datacenters/data/data-centers-openstreetmap-world-enrichment.json').then(r=>r.json())])
              .then(([base, overlay]) => done({base, overlay}));
        """)
        profiles = [row for row in data['overlay']['records'] if row['power_profile'].get('reported_power_capacity_mw') is not None]
        assert profiles, 'No audited numeric power profiles were available for browser acceptance'
        profile = profiles[0]
        feature = next(row for row in data['base']['features'] if row['properties']['osm_type'] == profile['osm_type'] and row['properties']['osm_id'] == profile['osm_id'])
        coordinate = feature['geometry']['coordinates']
        driver.execute_script("window.__codeCollectiveDatacenterMap.jumpTo({center: arguments[0], zoom: 15})", coordinate)
        rendered = wait.until(lambda d: d.execute_script("""
            const map = window.__codeCollectiveDatacenterMap;
            return map.queryRenderedFeatures({layers:['remote-openstreetmap-us-data-centers-point']})
              .find(f => f.properties.osm_id === arguments[0])?.properties;
        """, profile['osm_id']))
        assert rendered['reported_power_capacity_mw'] == profile['power_profile']['reported_power_capacity_mw']
        assert rendered['_dcPointScale'] > .55
        point = driver.execute_script("const p = window.__codeCollectiveDatacenterMap.project(arguments[0]); return {x:p.x,y:p.y}", coordinate)
        smoke.install_instrumentation(driver)
        if args.width > 760:
            smoke.dispatch_hover(driver, point['x'], point['y'])
        else:
            driver.execute_script("document.getElementById('datacenter-map').scrollIntoView({block:'center', behavior:'instant'})")
        smoke.dispatch_click(driver, point['x'], point['y'])
        wait.until(lambda d: feature['properties']['name'] in d.find_element(By.ID, 'record-detail').text)
        detail = driver.find_element(By.ID, 'record-detail')
        assert 'power draw' in detail.text.lower() and 'MW' in detail.text
        assert profile['sources'][0]['retrieved_url'] in [link.get_attribute('href') for link in detail.find_elements(By.CSS_SELECTOR, 'a')]
        report['rendered_power_capacity_mw'] = rendered['reported_power_capacity_mw']
        report['inspector_screenshot'] = str(smoke.save_screenshot(driver, screenshots, 'us-draw-inspector.png'))
        assert driver.execute_script('return document.documentElement.scrollWidth <= innerWidth + 1')
        assert driver.execute_script('const pane = document.querySelector(".dc-controls"); return pane.scrollWidth <= pane.clientWidth + 1')
        report['no_horizontal_overflow'] = True
        errors = driver.execute_script('return window.__drawControlErrors')
        assert not errors, errors
        (screenshots / 'draw-controls-report.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))
    except Exception:
        smoke.save_screenshot(driver, screenshots, 'draw-controls-failure.png')
        raise
    finally:
        driver.quit()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://host.docker.internal:8878/datacenters.html')
    parser.add_argument('--selenium-url', default='http://127.0.0.1:4444/wd/hub')
    parser.add_argument('--screenshot-dir', default='/tmp/codecollective-draw-controls')
    parser.add_argument('--width', type=int, default=1440)
    parser.add_argument('--height', type=int, default=1000)
    run(parser.parse_args())
