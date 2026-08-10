#!/usr/bin/env python3
"""Selenium smoke and performance probe for the datacenter parcel-hover flow."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import statistics
import sys
import time

from selenium import webdriver
from selenium.webdriver import ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait


PARCEL_FETCH_FRAGMENT = "PlanningCadastre/MD_ParcelBoundaries/MapServer/0/query"


def new_driver(selenium_url: str, width: int, height: int) -> webdriver.Remote:
    options = ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument(f"--window-size={width},{height}")
    options.add_argument("--no-sandbox")
    options.add_argument("--use-angle=swiftshader")
    options.add_argument("--use-gl=angle")
    options.add_argument("--enable-webgl")
    options.add_argument("--ignore-gpu-blocklist")
    options.add_argument("--ignore-certificate-errors")
    options.set_capability("acceptInsecureCerts", True)
    driver = webdriver.Remote(command_executor=selenium_url, options=options)
    if width <= 760:
        driver.execute_cdp_cmd(
            "Emulation.setDeviceMetricsOverride",
            {"width": width, "height": height, "deviceScaleFactor": 2, "mobile": True},
        )
    driver.set_page_load_timeout(60)
    return driver


def wait_for_map_ready(driver: webdriver.Remote) -> None:
    WebDriverWait(driver, 60).until(lambda d: d.execute_script("return document.readyState") == "complete")
    WebDriverWait(driver, 60).until(
        lambda d: d.find_element(By.ID, "datacenter-map")
    )
    WebDriverWait(driver, 60).until(
        lambda d: d.execute_script(
            "return !!document.querySelector('#datacenter-map canvas.maplibregl-canvas')"
        )
    )
    WebDriverWait(driver, 60).until(
        lambda d: d.find_element(By.ID, "show-parcels").is_enabled()
    )


def install_instrumentation(driver: webdriver.Remote) -> None:
    driver.execute_script(
        """
        if (window.__ccDatacenterProbeInstalled) {
          return;
        }
        window.__ccDatacenterProbeInstalled = true;
        window.__ccDatacenterProbe = {
          fetches: [],
          detailRenders: [],
          hovers: []
        };

        const originalFetch = window.fetch.bind(window);
        window.fetch = async (...args) => {
          const url = String(args[0] && args[0].url ? args[0].url : args[0] || '');
          const startedAt = performance.now();
          let index = -1;
          if (url.includes(arguments[0])) {
            index = window.__ccDatacenterProbe.fetches.push({
              url,
              startedAt,
              finishedAt: null,
              ok: null,
              status: null,
              kind: url.includes('resultRecordCount=1') ? 'lookup' : 'bounds'
            }) - 1;
          }
          try {
            const response = await originalFetch(...args);
            if (index >= 0) {
              const target = window.__ccDatacenterProbe.fetches[index];
              target.finishedAt = performance.now();
              target.ok = !!response.ok;
              target.status = response.status;
            }
            return response;
          } catch (error) {
            if (index >= 0) {
              const target = window.__ccDatacenterProbe.fetches[index];
              target.finishedAt = performance.now();
              target.ok = false;
              target.status = 0;
              target.error = String(error && error.message || error);
            }
            throw error;
          }
        };

        const detail = document.getElementById('record-detail');
        const snapshot = () => {
          const heading = detail.querySelector('h2')?.textContent?.trim() || '';
          const type = detail.querySelector('.dc-type')?.textContent?.trim() || '';
          const sourceLink = detail.querySelector('.dc-record-sources a')?.href || '';
          window.__ccDatacenterProbe.detailRenders.push({
            at: performance.now(),
            heading,
            type,
            sourceLink
          });
        };
        snapshot();
        new MutationObserver(snapshot).observe(detail, {
          childList: true,
          subtree: true,
          characterData: true
        });
        """,
        PARCEL_FETCH_FRAGMENT,
    )


def save_screenshot(driver: webdriver.Remote, directory: pathlib.Path, name: str) -> pathlib.Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    driver.save_screenshot(str(path))
    return path


def set_checkbox(driver: webdriver.Remote, checkbox_id: str, checked: bool) -> None:
    element = driver.find_element(By.ID, checkbox_id)
    if element.is_selected() != checked:
        element.click()


def verify_base_layers(driver: webdriver.Remote, screenshot_dir: pathlib.Path) -> dict:
    initial = driver.execute_script(
        "return document.querySelector('.dc-base-layer-toggle:checked')?.id || null;"
    )
    if initial != "show-md-six-inch-imagery":
        driver.execute_script("document.getElementById('show-md-six-inch-imagery').click();")
    WebDriverWait(driver, 30).until(
        lambda d: d.execute_script(
            "return !!window.__codeCollectiveDatacenterMap.getSource('base-md-six-inch-imagery');"
        )
    )
    WebDriverWait(driver, 60).until(
        lambda d: d.execute_script(
            "return window.__codeCollectiveDatacenterMap.isSourceLoaded('base-md-six-inch-imagery');"
        )
    )
    imagery = driver.execute_script(
        """
        const map = window.__codeCollectiveDatacenterMap;
        return {
          selected: [...document.querySelectorAll('.dc-base-layer-toggle:checked')].map((input) => input.id),
          source: !!map.getSource('base-md-six-inch-imagery'),
          layer: !!map.getLayer('base-md-six-inch-imagery'),
          backgroundVisibility: map.getLayoutProperty('background', 'visibility'),
          fallbackVisibility: map.getLayoutProperty('codecollective-map-background', 'visibility'),
          fallbackColor: map.getPaintProperty('codecollective-map-background', 'background-color'),
          queryBase: new URL(location.href).searchParams.get('base')
        };
        """
    )
    if imagery["selected"] != ["show-md-six-inch-imagery"] or not imagery["source"] or not imagery["layer"]:
        raise AssertionError(f"Maryland imagery base layer did not activate cleanly: {imagery}")
    if imagery["backgroundVisibility"] != "none" or imagery["queryBase"] != "md-six-inch-imagery":
        raise AssertionError(f"street base remained visible behind Maryland imagery: {imagery}")
    if imagery["fallbackVisibility"] != "visible" or imagery["fallbackColor"] != "#002a61":
        raise AssertionError(f"blue raster fallback was not visible beneath Maryland imagery: {imagery}")
    screenshot = save_screenshot(driver, screenshot_dir, "datacenters-maryland-six-inch-imagery.png")

    if initial != "show-md-six-inch-imagery":
        restore_id = initial or "show-md-six-inch-imagery"
        driver.execute_script("document.getElementById(arguments[0]).click();", restore_id)
        WebDriverWait(driver, 15).until(
            lambda d: not d.execute_script(
                "return !!window.__codeCollectiveDatacenterMap.getSource('base-md-six-inch-imagery');"
            )
        )
    return {"initial": initial, "maryland_imagery": imagery, "screenshot": str(screenshot)}


def verify_neon_streets(driver: webdriver.Remote, screenshot_dir: pathlib.Path) -> dict:
    set_checkbox(driver, "hover-neon-streets", True)
    driver.execute_script(
        """
        if (!document.getElementById('show-neon-streets').checked) {
          document.getElementById('show-neon-streets').click();
        }
        document.querySelector('[data-layer-config="neon-streets"]').click();
        document.querySelector('#layer-filter-form [name="scope"]').value = 'i95';
        document.querySelector('#layer-filter-form .dc-modal-primary').click();
        const map = window.__codeCollectiveDatacenterMap;
        map.jumpTo({center: [-76.61, 39.30], zoom: 10.5});
        """
    )
    i95 = WebDriverWait(driver, 30).until(
        lambda d: d.execute_script(
            """
            const map = window.__codeCollectiveDatacenterMap;
            if (!map.loaded() || !map.getLayer('neon-streets-core')) return null;
            const features = map.queryRenderedFeatures({layers: ['neon-streets-core']});
            if (!features.length) return null;
            const regularRoadLayers = map.getStyle().layers.filter((layer) =>
              layer.source === 'openmaptiles'
              && ['transportation', 'transportation_name'].includes(layer['source-layer'])
              && !layer.id.startsWith('neon-streets-')
              && map.getLayoutProperty(layer.id, 'visibility') !== 'none');
            return {
              featureCount: features.length,
              refs: [...new Set(features.map((feature) => feature.properties.ref || ''))],
              networks: [...new Set(features.map((feature) => feature.properties.network || ''))],
              regularRoadLayers: regularRoadLayers.map((layer) => layer.id),
              glowColor: map.getPaintProperty('neon-streets-glow', 'line-color'),
              glowBlur: map.getPaintProperty('neon-streets-glow', 'line-blur'),
              queryScope: JSON.parse(new URL(location.href).searchParams.get('filters')).neonStreets.scope,
              status: document.getElementById('neon-streets-status').textContent.trim()
            };
            """
        )
    )
    if i95["refs"] != ["95"] or i95["networks"] != ["us-interstate"]:
        raise AssertionError(f"non-I-95 roads leaked into the default neon view: {i95}")
    if i95["regularRoadLayers"] or i95["queryScope"] != "i95":
        raise AssertionError(f"ordinary streets remained visible beneath the default neon overlay: {i95}")
    if i95["glowColor"] != "#00eaff" or not isinstance(i95["glowBlur"], list):
        raise AssertionError(f"neon glow paint was not active: {i95}")
    screenshot = save_screenshot(driver, screenshot_dir, "datacenters-neon-i95.png")

    set_checkbox(driver, "show-enviroscreen", True)
    set_checkbox(driver, "hover-enviroscreen", True)
    overlap_point = WebDriverWait(driver, 30).until(
        lambda d: d.execute_script(
            """
            const map = window.__codeCollectiveDatacenterMap;
            if (!map.getLayer('mde-enviroscreen-fill')) return null;
            const canvas = map.getCanvas();
            for (let y = 2; y < canvas.clientHeight; y += 3) {
              for (let x = 2; x < canvas.clientWidth; x += 3) {
                const hits = map.queryRenderedFeatures([x, y], {layers: ['neon-streets-core', 'mde-enviroscreen-fill']});
                const hitLayers = new Set(hits.map((feature) => feature.layer.id));
                if (hitLayers.has('neon-streets-core') && hitLayers.has('mde-enviroscreen-fill')) {
                  return {x, y};
                }
              }
            }
            return null;
            """
        )
    )
    hover_arbitration = driver.execute_script(
        "return window.__resolveDatacenterHoverTargets(arguments[0]);",
        overlap_point,
    )
    if len(hover_arbitration["candidates"]) < 2:
        raise AssertionError(f"overlap did not produce multiple hover candidates: {hover_arbitration}")
    maximum_z = max(candidate["z"] for candidate in hover_arbitration["candidates"])
    if hover_arbitration["chosen"]["z"] != maximum_z:
        raise AssertionError(f"hover arbiter did not choose the highest rendered z-value: {hover_arbitration}")
    expected_type = {
        "enviroscreen": "Maryland Department of the Environment",
        "neon-street": "Neon streets",
        "power-plant": "Power plant",
    }.get(hover_arbitration["chosen"]["kind"])
    driver.execute_script(
        """
        const canvas = document.querySelector('#datacenter-map canvas.maplibregl-canvas');
        const rect = canvas.getBoundingClientRect();
        canvas.dispatchEvent(new MouseEvent('mousemove', {
          bubbles: true,
          cancelable: true,
          view: window,
          clientX: rect.left + arguments[0],
          clientY: rect.top + arguments[1]
        }));
        """,
        overlap_point["x"],
        overlap_point["y"],
    )
    inspector_type = WebDriverWait(driver, 10).until(lambda d: (
        value if expected_type and expected_type in value else False
    ) if (value := d.execute_script(
        "return document.querySelector('#record-detail .dc-type')?.textContent.trim() || '';"
    )) else False)
    hover_arbitration["inspectorType"] = inspector_type
    if expected_type and expected_type not in hover_arbitration["inspectorType"]:
        raise AssertionError(f"inspector did not show the one chosen hover target: {hover_arbitration}")
    set_checkbox(driver, "show-enviroscreen", False)

    driver.execute_script(
        """
        document.querySelector('[data-layer-config="neon-streets"]').click();
        const scope = document.querySelector('#layer-filter-form [name="scope"]');
        scope.value = 'all';
        document.querySelector('#layer-filter-form .dc-modal-primary').click();
        """
    )
    all_streets = WebDriverWait(driver, 15).until(
        lambda d: d.execute_script(
            """
            const map = window.__codeCollectiveDatacenterMap;
            const features = map.queryRenderedFeatures({layers: ['neon-streets-core']});
            const refs = [...new Set(features.map((feature) => feature.properties.ref || ''))];
            return refs.some((ref) => ref !== '95')
              ? {featureCount: features.length, refs, status: document.getElementById('neon-streets-status').textContent.trim()}
              : null;
            """
        )
    )
    driver.execute_script(
        """
        document.querySelector('[data-layer-config="neon-streets"]').click();
        document.querySelector('#layer-filter-form [name="scope"]').value = 'i95';
        document.querySelector('#layer-filter-form .dc-modal-primary').click();
        """
    )
    return {
        "i95": i95,
        "overlap_point": overlap_point,
        "hover_arbitration": hover_arbitration,
        "all_streets": all_streets,
        "screenshot": str(screenshot),
    }


def verify_layer_search(driver: webdriver.Remote) -> dict:
    search = driver.find_element(By.ID, "layer-search")
    before = driver.execute_script(
        """
        const powerLayer = window.__codeCollectiveDatacenterMap.getLayer('power-plant-bolt-webgl');
        return {
          cards: document.querySelectorAll('.dc-controls .dc-layer-option[data-layer-preview]').length,
          powerRecords: powerLayer?.implementation?.getDiagnostics?.().recordCount || 0
        };
        """
    )
    search.clear()
    search.send_keys("zoning")
    WebDriverWait(driver, 10).until(
        lambda d: d.execute_script(
            "return [...document.querySelectorAll('.dc-controls .dc-layer-option[data-layer-preview]')].some((card) => card.hidden);"
        )
    )
    filtered = driver.execute_script(
        r"""
        const cards = [...document.querySelectorAll('.dc-controls .dc-layer-option[data-layer-preview]')];
        const powerLayer = window.__codeCollectiveDatacenterMap.getLayer('power-plant-bolt-webgl');
        return {
          visible: cards.filter((card) => !card.hidden).map((card) => card.textContent.replace(/\s+/g, ' ').trim()),
          hidden: cards.filter((card) => card.hidden).length,
          dataCentersHidden: document.querySelector('[data-layer-preview="datacenters"]').hidden,
          powerRecords: powerLayer?.implementation?.getDiagnostics?.().recordCount || 0
        };
        """
    )
    if not filtered["visible"] or any("zoning" not in text.lower() for text in filtered["visible"]):
        raise AssertionError(f"layer search returned nonmatching cards: {filtered}")
    if not filtered["dataCentersHidden"] or filtered["powerRecords"] != before["powerRecords"]:
        raise AssertionError(f"layer search changed map records instead of card visibility: {before} {filtered}")
    driver.execute_script(
        "const input = document.getElementById('layer-search'); input.value = ''; input.dispatchEvent(new Event('input', {bubbles: true}));"
    )
    WebDriverWait(driver, 10).until(
        lambda d: d.execute_script(
            "return [...document.querySelectorAll('.dc-controls .dc-layer-option[data-layer-preview]')].every((card) => !card.hidden);"
        )
    )
    return {"before": before, "filtered": filtered}


def verify_mobile_layout(driver: webdriver.Remote, screenshot_dir: pathlib.Path) -> dict:
    layout = driver.execute_script(
        """
        const bounds = (selector) => {
          const rect = document.querySelector(selector).getBoundingClientRect();
          return {left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom,
                  width: rect.width, height: rect.height};
        };
        return {
          viewport: {width: innerWidth, height: innerHeight},
          documentWidth: document.documentElement.scrollWidth,
          panel: bounds('.dc-map-panel'),
          heading: bounds('.dc-map-panel > .dc-pane-heading'),
          tools: bounds('.dc-map-heading-tools'),
          download: bounds('#download-map-png'),
          theme: bounds('#map-theme'),
          map: bounds('#datacenter-map')
        };
        """
    )
    viewport = layout["viewport"]
    tolerance = 1.5
    if layout["documentWidth"] > viewport["width"] + tolerance:
        raise AssertionError(f"mobile page scrolls horizontally: {layout}")
    for name in ("heading", "tools", "download", "theme", "map"):
        rect = layout[name]
        if rect["left"] < -tolerance or rect["right"] > viewport["width"] + tolerance:
            raise AssertionError(f"mobile {name} escapes the viewport: {layout}")
    if min(layout["download"]["height"], layout["theme"]["height"]) < 42:
        raise AssertionError(f"mobile map controls are too small for touch: {layout}")
    if layout["map"]["height"] < min(430, viewport["height"] * .55):
        raise AssertionError(f"mobile map is too short: {layout}")
    overview = save_screenshot(driver, screenshot_dir, "datacenters-mobile-overview.png")

    marker = WebDriverWait(driver, 20).until(
        lambda d: d.find_element(By.CSS_SELECTOR, ".dc-map-marker--center")
    )
    driver.execute_script("arguments[0].click();", marker)
    WebDriverWait(driver, 10).until(
        lambda d: d.find_element(By.ID, "close-record-detail").is_displayed()
    )
    inspector = driver.execute_script(
        """
        const panel = document.querySelector('.dc-detail');
        const close = document.getElementById('close-record-detail');
        const rect = panel.getBoundingClientRect();
        const closeRect = close.getBoundingClientRect();
        return {position: getComputedStyle(panel).position, classPinned: panel.classList.contains('is-pinned'),
                left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom,
                closeWidth: closeRect.width, closeHeight: closeRect.height};
        """
    )
    if inspector["position"] != "fixed" or not inspector["classPinned"]:
        raise AssertionError(f"pinned mobile inspector is not a bottom sheet: {inspector}")
    if inspector["left"] < -tolerance or inspector["right"] > viewport["width"] + tolerance:
        raise AssertionError(f"mobile inspector escapes the viewport: {inspector}")
    if inspector["bottom"] > viewport["height"] + tolerance or min(inspector["closeWidth"], inspector["closeHeight"]) < 42:
        raise AssertionError(f"mobile inspector close control is not reachable: {inspector}")
    inspector_shot = save_screenshot(driver, screenshot_dir, "datacenters-mobile-inspector.png")
    driver.find_element(By.ID, "close-record-detail").click()
    WebDriverWait(driver, 10).until(
        lambda d: not d.execute_script("return document.querySelector('.dc-detail').classList.contains('is-pinned');")
    )

    driver.execute_script("document.querySelector('[data-layer-config=\"datacenters\"]').click();")
    WebDriverWait(driver, 10).until(
        lambda d: d.find_element(By.ID, "layer-filter-modal").get_attribute("open") is not None
    )
    modal = driver.execute_script(
        """
        const dialog = document.getElementById('layer-filter-modal');
        const rect = dialog.getBoundingClientRect();
        const apply = dialog.querySelector('.dc-modal-primary').getBoundingClientRect();
        return {left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom,
                applyHeight: apply.height};
        """
    )
    if modal["left"] < -tolerance or modal["right"] > viewport["width"] + tolerance:
        raise AssertionError(f"mobile filter dialog escapes the viewport: {modal}")
    if modal["top"] < -tolerance or modal["bottom"] > viewport["height"] + tolerance or modal["applyHeight"] < 42:
        raise AssertionError(f"mobile filter dialog actions are not reachable: {modal}")
    modal_shot = save_screenshot(driver, screenshot_dir, "datacenters-mobile-layer-dialog.png")
    driver.find_element(By.CSS_SELECTOR, '#layer-filter-form button[value="cancel"]').click()
    return {
        "layout": layout,
        "inspector": inspector,
        "modal": modal,
        "screenshots": [str(overview), str(inspector_shot), str(modal_shot)],
    }


def verify_no_base_and_png_export(driver: webdriver.Remote, screenshot_dir: pathlib.Path) -> dict:
    selected = driver.execute_script(
        "return document.querySelector('.dc-base-layer-toggle:checked')?.id || null;"
    )
    if selected:
        driver.execute_script("document.getElementById(arguments[0]).click();", selected)
    WebDriverWait(driver, 10).until(
        lambda d: d.find_element(By.ID, "datacenter-map").get_attribute("class").find("dc-map--no-base") >= 0
    )
    no_base = driver.execute_script(
        """
        const container = document.getElementById('datacenter-map');
        const canvas = window.__codeCollectiveDatacenterMap.getCanvas();
        const rect = canvas.getBoundingClientRect();
        return {
          classActive: container.classList.contains('dc-map--no-base'),
          background: getComputedStyle(container).backgroundImage,
          cssWidth: rect.width,
          cssHeight: rect.height,
          pixelWidth: canvas.width,
          pixelHeight: canvas.height,
          queryBase: new URL(location.href).searchParams.get('base')
        };
        """
    )
    if not no_base["classActive"] or "linear-gradient" not in no_base["background"]:
        raise AssertionError(f"no-base map did not use the blue fallback: {no_base}")
    if no_base["pixelWidth"] < no_base["cssWidth"] * 2 - 2:
        raise AssertionError(f"map canvas is not high resolution: {no_base}")

    driver.execute_script(
        """
        window.__ccMapDownload = {};
        const originalCreateObjectURL = URL.createObjectURL.bind(URL);
        URL.createObjectURL = (blob) => {
          window.__ccMapDownload.blob = blob;
          return originalCreateObjectURL(blob);
        };
        HTMLAnchorElement.prototype.click = function() {
          window.__ccMapDownload.name = this.download;
        };
        document.getElementById('download-map-png').click();
        """
    )
    WebDriverWait(driver, 15).until(
        lambda d: d.find_element(By.ID, "map-download-status").get_attribute("textContent").startswith("PNG downloaded")
    )
    exported = driver.execute_async_script(
        """
        const done = arguments[arguments.length - 1];
        const blob = window.__ccMapDownload.blob;
        blob.arrayBuffer().then((buffer) => {
          const view = new DataView(buffer);
          done({
            bytes: buffer.byteLength,
            type: blob.type,
            name: window.__ccMapDownload.name,
            width: view.getUint32(16),
            height: view.getUint32(20),
            status: document.getElementById('map-download-status').textContent
          });
        });
        """
    )
    if exported["type"] != "image/png" or exported["bytes"] < 10000:
        raise AssertionError(f"PNG export was empty or invalid: {exported}")
    if exported["width"] != no_base["pixelWidth"] or exported["height"] != no_base["pixelHeight"]:
        raise AssertionError(f"PNG dimensions do not match high-resolution map canvas: {exported} vs {no_base}")
    screenshot = save_screenshot(driver, screenshot_dir, "datacenters-no-base-blue.png")
    if selected:
        driver.execute_script("document.getElementById(arguments[0]).click();", selected)
    return {"no_base": no_base, "exported": exported, "screenshot": str(screenshot)}


def verify_power_plant_webgl(driver: webdriver.Remote, screenshot_dir: pathlib.Path) -> dict:
    set_checkbox(driver, "show-power-plants", True)
    diagnostics = WebDriverWait(driver, 30).until(
        lambda d: d.execute_script(
            """
            const layer = window.__codeCollectiveDatacenterMap.getLayer('power-plant-bolt-webgl');
            const diagnostics = layer?.implementation?.getDiagnostics?.();
            return diagnostics?.ready && diagnostics.renderCount > 1 ? diagnostics : null;
            """
        )
    )
    dom_markers = driver.execute_script("return document.querySelectorAll('.dc-map-marker--plant').length;")
    if diagnostics["recordCount"] < 1 or diagnostics["instanceCount"] != diagnostics["recordCount"]:
        raise AssertionError(f"WebGL power-plant instance mismatch: {diagnostics}")
    if diagnostics["vertexCount"] < 3 or diagnostics["indexCount"] < 3:
        raise AssertionError(f"WebGL lightning mesh is empty: {diagnostics}")
    if diagnostics["lastGlError"] != 0:
        raise AssertionError(f"WebGL lightning draw failed: {diagnostics}")
    if dom_markers:
        raise AssertionError(f"found {dom_markers} non-WebGL power-plant markers")

    driver.execute_script("document.querySelector('[data-layer-config=\"power-plants\"]').click();")
    WebDriverWait(driver, 10).until(lambda d: d.find_element(By.ID, "layer-filter-modal").get_attribute("open") is not None)
    scaling_options = driver.execute_script(
        """
        const select = document.querySelector('#layer-filter-form [name="sizeBy"]');
        const options = [...select.options].map((option) => ({value: option.value, label: option.textContent.trim()}));
        select.value = 'net_generation_mwh';
        document.querySelector('#layer-filter-form .dc-modal-primary').click();
        return options;
        """
    )
    scaled_diagnostics = WebDriverWait(driver, 10).until(
        lambda d: d.execute_script(
            """
            const layer = window.__codeCollectiveDatacenterMap.getLayer('power-plant-bolt-webgl');
            const diagnostics = layer?.implementation?.getDiagnostics?.();
            return diagnostics?.sizeBy === 'net_generation_mwh' ? diagnostics : null;
            """
        )
    )
    if scaled_diagnostics["maximumSize"] <= scaled_diagnostics["minimumSize"]:
        raise AssertionError(f"power output scaling did not vary WebGL bolt sizes: {scaled_diagnostics}")
    if not scaled_diagnostics["drawOrderAscending"] or scaled_diagnostics["topmostSize"] != scaled_diagnostics["maximumSize"]:
        raise AssertionError(f"larger WebGL bolts were not assigned the highest draw order: {scaled_diagnostics}")
    if not any(option["value"] == "net_generation_mwh" for option in scaling_options):
        raise AssertionError(f"power output was absent from point scaling options: {scaling_options}")
    driver.execute_script(
        """
        document.querySelector('[data-layer-config="power-plants"]').click();
        const select = document.querySelector('#layer-filter-form [name="sizeBy"]');
        select.value = 'none';
        document.querySelector('#layer-filter-form .dc-modal-primary').click();
        """
    )

    hover_point = driver.execute_script(
        """
        const map = window.__codeCollectiveDatacenterMap;
        map.jumpTo({center: [-76.548, 39.267], zoom: 15});
        const point = map.project([-76.548, 39.267]);
        return {x: point.x, y: point.y};
        """
    )
    WebDriverWait(driver, 30).until(
        lambda d: d.execute_script(
            """
            const layer = window.__codeCollectiveDatacenterMap.getLayer('power-plant-bolt-webgl');
            return !!layer?.implementation?.getDiagnostics?.().ready;
            """
        )
    )
    dispatch_hover(driver, hover_point["x"], hover_point["y"])
    hovered_record_id = WebDriverWait(driver, 10).until(
        lambda d: d.execute_script(
            """
            const layer = window.__codeCollectiveDatacenterMap.getLayer('power-plant-bolt-webgl');
            return layer?.implementation?.getDiagnostics?.().hoveredRecordId || null;
            """
        )
    )
    hovered_inspector = WebDriverWait(driver, 10).until(
        lambda d: d.execute_script(
            r"""
            const detail = document.getElementById('record-detail');
            const tags = [...detail.querySelectorAll('.dc-hover-tag')].map((element) => element.textContent.trim());
            const energy = [...detail.querySelectorAll('.dc-energy-summary > div')].map((item) => ({
              label: item.querySelector('span')?.textContent.trim() || '',
              value: item.querySelector('strong')?.textContent.trim() || ''
            }));
            return tags.includes('Power') && tags.includes('Solar')
              ? {title: detail.querySelector('h2').textContent.trim(), tags, energy}
              : null;
            """
        )
    )
    hovered_icon_title = hovered_inspector["title"]
    hovered_tags = hovered_inspector["tags"]
    if hovered_icon_title != "IGS Solar I - BWI2" or not {"Power", "Solar"} <= set(hovered_tags):
        raise AssertionError(f"unexpected hovered power icon: title={hovered_icon_title!r}, tags={hovered_tags!r}")
    if {"label": "2024 net generation", "value": "2,546 MWh"} not in hovered_inspector["energy"]:
        raise AssertionError(f"power generation was not prominent in the inspector: {hovered_inspector['energy']!r}")
    tag_filter_modes = driver.execute_script(
        """
        const buttons = [...document.querySelectorAll('#record-detail [data-filter-tag]')];
        for (const label of ['Solar', 'Built 2017']) {
          const button = buttons.find((candidate) => candidate.dataset.filterTag === label);
          if (!button) throw new Error(`Missing inspector tag ${label}`);
          button.click();
        }
        const layer = window.__codeCollectiveDatacenterMap.getLayer('power-plant-bolt-webgl');
        return {
          mode: new URL(location.href).searchParams.get('tagMode'),
          count: layer.implementation.getDiagnostics().recordCount,
          unwantedTextVisible: document.body.innerText.includes('Matching all')
        };
        """
    )
    driver.find_element(By.CSS_SELECTOR, '[data-tag-filter-mode="or"]').click()
    tag_filter_modes["or"] = WebDriverWait(driver, 10).until(
        lambda d: d.execute_script(
            """
            const layer = window.__codeCollectiveDatacenterMap.getLayer('power-plant-bolt-webgl');
            const count = layer?.implementation?.getDiagnostics?.().recordCount;
            const mode = new URL(location.href).searchParams.get('tagMode');
            return mode === 'or' && count > arguments[0] ? {mode, count} : null;
            """,
            tag_filter_modes["count"],
        )
    )
    tag_filter_modes["and"] = {"mode": tag_filter_modes.pop("mode"), "count": tag_filter_modes.pop("count")}
    if tag_filter_modes.pop("unwantedTextVisible"):
        raise AssertionError("removed tag match-count sentence is still visible")
    driver.find_element(By.ID, "clear-tag-filters").click()
    driver.find_element(By.CSS_SELECTOR, '[data-tag-filter-mode="and"]').click()
    dispatch_click(driver, hover_point["x"], hover_point["y"])
    WebDriverWait(driver, 10).until(
        lambda d: d.find_element(By.ID, "close-record-detail").is_displayed()
    )
    nuclear_point = driver.execute_script(
        """
        const map = window.__codeCollectiveDatacenterMap;
        map.jumpTo({center: [-76.4417, 38.4344], zoom: 15});
        const point = map.project([-76.4417, 38.4344]);
        return {x: point.x, y: point.y};
        """
    )
    dispatch_hover(driver, nuclear_point["x"], nuclear_point["y"])
    time.sleep(0.2)
    pinned_title = driver.find_element(By.CSS_SELECTOR, "#record-detail h2").text
    if pinned_title != hovered_icon_title:
        raise AssertionError(f"pinned inspector was replaced by hover: {pinned_title!r}")
    dispatch_click(driver, nuclear_point["x"], nuclear_point["y"])
    replacement_title = WebDriverWait(driver, 10).until(
        lambda d: d.find_element(By.CSS_SELECTOR, "#record-detail h2").text == "Calvert Cliffs Nuclear Power Plant"
        and d.find_element(By.ID, "close-record-detail").is_displayed()
        and "Calvert Cliffs Nuclear Power Plant"
    )
    driver.find_element(By.ID, "close-record-detail").click()
    WebDriverWait(driver, 10).until(
        lambda d: d.find_element(By.CSS_SELECTOR, "#record-detail h2").text == "Hover a map icon"
    )
    hover_point = driver.execute_script(
        """
        const map = window.__codeCollectiveDatacenterMap;
        map.jumpTo({center: [-76.548, 39.267], zoom: 15});
        const point = map.project([-76.548, 39.267]);
        return {x: point.x, y: point.y};
        """
    )
    dispatch_hover(driver, hover_point["x"], hover_point["y"])
    WebDriverWait(driver, 10).until(
        lambda d: d.find_element(By.CSS_SELECTOR, "#record-detail h2").text == hovered_icon_title
    )
    inspector_pin = {"title": pinned_title, "replacement_title": replacement_title, "released": True}
    driver.execute_script("window.__ccStableInspectorGallery = document.querySelector('#record-detail .dc-site-gallery');")
    for _ in range(5):
        dispatch_hover(driver, hover_point["x"], hover_point["y"])
    inspector_gallery_stable = driver.execute_script(
        "return window.__ccStableInspectorGallery === document.querySelector('#record-detail .dc-site-gallery');"
    )
    if not inspector_gallery_stable:
        raise AssertionError("same-feature hover refreshed the inspector gallery")
    aerial_animation = WebDriverWait(driver, 30).until(
        lambda d: d.execute_script(
            """
            const motion = document.querySelector('#record-detail .dc-aerial-motion.is-aerial-ready');
            if (!motion) return null;
            const style = getComputedStyle(motion);
            if (style.animationName !== 'dc-aerial-push-in') return null;
            return {name: style.animationName, duration: style.animationDuration};
            """
        )
    )
    aerial_control_limits = driver.execute_script(
        """
        const speed = document.querySelector('[data-aerial-speed]');
        const distance = document.querySelector('[data-aerial-distance]');
        speed.value = '10';
        speed.dispatchEvent(new Event('input', {bubbles: true}));
        distance.value = '2';
        distance.dispatchEvent(new Event('input', {bubbles: true}));
        const animation = document.querySelector('[data-site-animation]');
        return {
          speedMax: speed.max,
          distanceMax: distance.max,
          duration: animation.style.getPropertyValue('--dc-aerial-duration'),
          zoom: animation.style.getPropertyValue('--dc-aerial-zoom'),
          speedOutput: document.querySelector('[data-aerial-speed-output]').value,
          distanceOutput: document.querySelector('[data-aerial-distance-output]').value
        };
        """
    )
    expected_limits = {
        "speedMax": "10",
        "distanceMax": "2",
        "duration": "1.8s",
        "zoom": "3",
        "speedOutput": "10×",
        "distanceOutput": "2×",
    }
    if aerial_control_limits != expected_limits:
        raise AssertionError(f"aerial animation limits did not apply: {aerial_control_limits}")
    driver.execute_script(
        """
        const speed = document.querySelector('[data-aerial-speed]');
        const distance = document.querySelector('[data-aerial-distance]');
        speed.value = '1';
        speed.dispatchEvent(new Event('input', {bubbles: true}));
        distance.value = '1';
        distance.dispatchEvent(new Event('input', {bubbles: true}));
        """
    )
    first = save_screenshot(driver, screenshot_dir, "datacenters-power-webgl-hover-1.png")
    time.sleep(0.7)
    second = save_screenshot(driver, screenshot_dir, "datacenters-power-webgl-hover-2.png")
    frame_hashes = [hashlib.sha256(path.read_bytes()).hexdigest() for path in (first, second)]
    if frame_hashes[0] == frame_hashes[1]:
        raise AssertionError("WebGL lightning bolt frames did not animate")
    color_titles = {}
    entity_images = {}
    for label, coordinate, expected_title, expected_tag in (
        ("nuclear", [-76.4417, 38.4344], "Calvert Cliffs Nuclear Power Plant", "Nuclear"),
        ("wind", [-79.011111, 39.641111], "Fourmile Ridge", "Wind"),
    ):
        point = driver.execute_script(
            """
            const map = window.__codeCollectiveDatacenterMap;
            map.jumpTo({center: arguments[0], zoom: 15});
            const projected = map.project(arguments[0]);
            return {x: projected.x, y: projected.y};
            """,
            coordinate,
        )
        dispatch_hover(driver, point["x"], point["y"])
        WebDriverWait(driver, 10).until(
            lambda d: d.find_element(By.CSS_SELECTOR, "#record-detail h2").text == expected_title
        )
        tags = [element.text for element in driver.find_elements(By.CSS_SELECTOR, "#record-detail .dc-hover-tag")]
        if not {"Power", expected_tag} <= set(tags):
            raise AssertionError(f"missing semantic tags for {label}: {tags}")
        color_titles[label] = driver.find_element(By.CSS_SELECTOR, "#record-detail h2").text
        if label == "nuclear":
            entity_images[label] = WebDriverWait(driver, 10).until(
                lambda d: d.execute_script(
                    """
                    const detail = document.getElementById('record-detail');
                    const photo = detail.querySelector('.dc-entity-image');
                    const aerial = detail.querySelector('[data-site-animation]');
                    const image = photo?.querySelector('img');
                    if (!photo || !aerial || !image?.complete || !image.naturalWidth) return null;
                    return {
                      beforeAerial: !!(photo.compareDocumentPosition(aerial) & Node.DOCUMENT_POSITION_FOLLOWING),
                      width: image.naturalWidth,
                      source: photo.querySelector('a')?.href || ''
                    };
                    """
                )
            )
            if not entity_images[label]["beforeAerial"] or "commons.wikimedia.org" not in entity_images[label]["source"]:
                raise AssertionError(f"verified entity image was not attributed above the aerial: {entity_images[label]}")
    return {
        "diagnostics": diagnostics,
        "dom_plant_markers": dom_markers,
        "output_scaling": {"options": scaling_options, "diagnostics": scaled_diagnostics},
        "hovered_record_id": hovered_record_id,
        "hovered_icon_title": hovered_icon_title,
        "hovered_tags": hovered_tags,
        "tag_filter_modes": tag_filter_modes,
        "inspector_pin": inspector_pin,
        "inspector_gallery_stable": inspector_gallery_stable,
        "aerial_animation": aerial_animation,
        "aerial_control_limits": aerial_control_limits,
        "hover_point": hover_point,
        "frame_hashes": frame_hashes,
        "color_titles": color_titles,
        "entity_images": entity_images,
        "screenshots": [str(first), str(second)],
    }


def verify_baltimore_zoning(driver: webdriver.Remote, screenshot_dir: pathlib.Path) -> dict:
    layer_id = "remote-baltimore-city-zoning"
    set_checkbox(driver, "show-baltimore-city-zoning", True)
    driver.find_element(By.CSS_SELECTOR, '[data-layer-locate="baltimore-city-zoning"]').click()
    WebDriverWait(driver, 60).until(
        lambda d: "features" in d.find_element(By.ID, "status-baltimore-city-zoning").text.lower()
    )
    WebDriverWait(driver, 30).until(
        lambda d: d.execute_script(
            "return window.__codeCollectiveDatacenterMap.queryRenderedFeatures({layers:[arguments[0] + '-fill']}).length > 0;",
            layer_id,
        )
    )
    metrics = driver.execute_script(
        """
        const map = window.__codeCollectiveDatacenterMap;
        const layerId = arguments[0];
        return {
          center: map.getCenter().toArray(),
          zoom: map.getZoom(),
          rendered_features: map.queryRenderedFeatures({layers: [layerId + '-fill']}).length,
          source_features: map.querySourceFeatures(layerId).length,
          fill_opacity: map.getPaintProperty(layerId + '-fill', 'fill-opacity')
        };
        """,
        layer_id,
    )
    size = driver.execute_script(
        """
        const rect = document.querySelector('#datacenter-map canvas.maplibregl-canvas').getBoundingClientRect();
        return { width: rect.width, height: rect.height };
        """
    )
    hover_hit = None
    for y_fraction in (0.14, 0.3, 0.46, 0.62, 0.78, 0.9):
        for x_fraction in (0.1, 0.26, 0.42, 0.58, 0.74, 0.9):
            dispatch_hover(driver, size["width"] * x_fraction, size["height"] * y_fraction)
            time.sleep(0.08)
            detail = driver.execute_script(
                """
                return {
                  heading: document.querySelector('#record-detail h2')?.textContent?.trim() || '',
                  type: document.querySelector('#record-detail .dc-type')?.textContent?.trim() || ''
                };
                """
            )
            if "Baltimore City zoning" in detail["type"]:
                hover_hit = detail
                break
        if hover_hit:
            break
    if not hover_hit:
        raise AssertionError("Baltimore City zoning rendered, but no zoning feature responded to hover")
    screenshot = save_screenshot(driver, screenshot_dir, "datacenters-baltimore-zoning-visible.png")
    result = {
        "status": driver.find_element(By.ID, "status-baltimore-city-zoning").text,
        "metrics": metrics,
        "hover_hit": hover_hit,
        "screenshot": str(screenshot),
    }
    set_checkbox(driver, "show-baltimore-city-zoning", False)
    return result


def verify_layer_color_controls(driver: webdriver.Remote, screenshot_dir: pathlib.Path) -> dict:
    geometry = driver.execute_script(
        """
        const card = document.querySelector('[data-layer-preview="datacenters"]');
        const color = card.querySelector('[data-layer-color="datacenters"]');
        const render = card.querySelector('#show-datacenters').closest('label');
        const hover = card.querySelector('#hover-datacenters').closest('label');
        return {
          cardHeight: card.getBoundingClientRect().height,
          labels: [render.innerText.trim(), hover.innerText.trim()],
          controls: [color, render, hover].map((element) => {
            const bounds = element.getBoundingClientRect();
            return { x: bounds.x, y: bounds.y, width: bounds.width, height: bounds.height };
          })
        };
        """
    )
    if geometry["cardHeight"] > 68:
        raise AssertionError(f"layer card was not compact: {geometry['cardHeight']:.1f}px")
    if geometry["labels"] != ["Render", "Hover"]:
        raise AssertionError(f"render/hover controls were not explicit: {geometry['labels']}")
    control_y = [control["y"] for control in geometry["controls"]]
    if max(control_y) - min(control_y) > 2:
        raise AssertionError("color, render, and hover controls were not on the same row")

    driver.find_element(By.CSS_SELECTOR, '[data-layer-color="datacenters"]').click()
    WebDriverWait(driver, 10).until(
        lambda d: d.find_element(By.ID, "layer-color-modal").get_attribute("open") is not None
    )
    driver.execute_script(
        """
        const input = document.getElementById('layer-color-input');
        input.value = '#19c37d';
        input.dispatchEvent(new Event('input', { bubbles: true }));
        """
    )
    driver.find_element(By.CSS_SELECTOR, '#layer-color-form button[value="apply"]').click()
    WebDriverWait(driver, 10).until(
        lambda d: "#19c37d" in d.execute_script(
            "return document.querySelector('.dc-map-marker--center')?.style.getPropertyValue('--marker-icon-fill') || ''"
        )
    )
    applied = driver.execute_script(
        """
        return {
          swatch: document.querySelector('[data-layer-color="datacenters"]').classList.contains('has-custom-color'),
          query: JSON.parse(new URL(location.href).searchParams.get('colors') || '{}').datacenters,
          stored: JSON.parse(localStorage.getItem('codecollective.datacenters.ui-state.v1') || '{}').colors?.datacenters
        };
        """
    )
    if applied != {"swatch": True, "query": "#19c37d", "stored": "#19c37d"}:
        raise AssertionError(f"custom layer color did not persist: {applied}")
    screenshot = save_screenshot(driver, screenshot_dir, "datacenters-layer-color-controls.png")

    driver.find_element(By.CSS_SELECTOR, '[data-layer-color="datacenters"]').click()
    driver.find_element(By.ID, "reset-layer-color").click()
    WebDriverWait(driver, 10).until(
        lambda d: not d.execute_script(
            "return document.querySelector('[data-layer-color=\"datacenters\"]').classList.contains('has-custom-color')"
        )
    )
    return {"geometry": geometry, "applied": applied, "screenshot": str(screenshot)}


def verify_data_center_power_scale(driver: webdriver.Remote, screenshot_dir: pathlib.Path) -> dict:
    marker = driver.find_element(By.CSS_SELECTOR, '.dc-map-marker--center[aria-label="Cogent Elkridge"]')
    driver.execute_script(
        "arguments[0].dispatchEvent(new PointerEvent('pointerenter', { bubbles: true }))", marker
    )
    WebDriverWait(driver, 10).until(
        lambda d: any(
            tag.text.startswith("Power envelope:")
            for tag in d.find_elements(By.CSS_SELECTOR, ".dc-hover-tag")
        )
    )
    detail = driver.find_element(By.ID, "record-detail").text
    if "Power class\nMedium" not in detail or "not measured operating draw" not in detail:
        raise AssertionError("Cogent power class did not expose its capacity-proxy limitation")
    energy = driver.find_element(By.CSS_SELECTOR, "#record-detail .dc-energy-summary").text.replace("\n", " ")
    if "REQUIRED GRID POWER NOT PUBLICLY DISCLOSED 7.5 MW published capacity envelope" not in energy:
        raise AssertionError(f"Cogent required power was not presented honestly near the top: {energy!r}")
    if "NORMAL ON-SITE GENERATION NOT PUBLICLY DISCLOSED" not in energy:
        raise AssertionError(f"Cogent on-site generation disclosure was missing: {energy!r}")
    energy_screenshot = save_screenshot(driver, screenshot_dir, "datacenters-energy-requirement-summary.png")
    power_tag = next(
        tag for tag in driver.find_elements(By.CSS_SELECTOR, ".dc-hover-tag")
        if tag.text.startswith("Power envelope:")
    )
    tag_label = power_tag.text
    power_tag.click()
    WebDriverWait(driver, 10).until(
        lambda d: tag_label in [
            chip.text for chip in d.find_elements(By.CSS_SELECTOR, "#active-tag-filter-list [data-remove-tag]")
        ]
    )
    driver.find_element(By.CSS_SELECTOR, '[data-layer-config="datacenters"]').click()
    options = driver.execute_script(
        "return [...document.querySelector('select[name=powerScale]').options].map(option => option.value)"
    )
    expected = ["all", "sub-megawatt", "small", "medium", "large", "very-large", "unknown"]
    if options != expected:
        raise AssertionError(f"power-scale filter options were incomplete: {options}")
    screenshot = save_screenshot(driver, screenshot_dir, "datacenters-power-scale-filter.png")
    driver.find_element(By.CSS_SELECTOR, '#layer-filter-form button[value="cancel"]').click()
    driver.find_element(By.CSS_SELECTOR, f'#active-tag-filter-list [data-remove-tag="{tag_label}"]').click()
    return {
        "tag": tag_label,
        "options": options,
        "energy_screenshot": str(energy_screenshot),
        "screenshot": str(screenshot),
    }


def verify_data_center_draw_scaling(driver: webdriver.Remote, screenshot_dir: pathlib.Path) -> dict:
    driver.execute_script("document.querySelector('[data-layer-config=\"datacenters\"]').click();")
    WebDriverWait(driver, 10).until(
        lambda d: d.find_element(By.ID, "layer-filter-modal").get_attribute("open") is not None
    )
    options = driver.execute_script(
        "return [...document.querySelector('select[name=sizeBy]').options].map(option => ({value: option.value, label: option.textContent.trim()}));"
    )
    by_value = {option["value"]: option["label"] for option in options}
    if "Net draw · reported grid demand" not in by_value.get("reported_grid_demand_mw", ""):
        raise AssertionError(f"net-draw size mode was missing: {options}")
    if "Total draw · published power envelope" not in by_value.get("reported_power_capacity_mw", ""):
        raise AssertionError(f"total-draw size mode was missing: {options}")

    driver.execute_script(
        "const select = document.querySelector('select[name=sizeBy]'); select.value = 'reported_power_capacity_mw'; document.querySelector('#layer-filter-form .dc-modal-primary').click();"
    )
    total_draw = WebDriverWait(driver, 10).until(
        lambda d: d.execute_script(
            """
            const markers = [...document.querySelectorAll('.dc-map-marker--center')];
            const sizes = Object.fromEntries(markers.map((marker) => [marker.getAttribute('aria-label'), parseFloat(marker.style.getPropertyValue('--marker-size'))]));
            return sizes['AiNET CyberNAP'] > sizes['Aligned Data Centers IAD04'] ? sizes : null;
            """
        )
    )
    screenshot = save_screenshot(driver, screenshot_dir, "datacenters-total-draw-icon-scaling.png")

    driver.execute_script(
        "document.querySelector('[data-layer-config=\"datacenters\"]').click(); const select = document.querySelector('select[name=sizeBy]'); select.value = 'reported_grid_demand_mw'; document.querySelector('#layer-filter-form .dc-modal-primary').click();"
    )
    net_draw_sizes = driver.execute_script(
        "return [...new Set([...document.querySelectorAll('.dc-map-marker--center')].map(marker => parseFloat(marker.style.getPropertyValue('--marker-size'))))];"
    )
    if len(net_draw_sizes) != 1 or abs(net_draw_sizes[0] - 12.1) > .1:
        raise AssertionError(f"undisclosed net draw did not use the smallest marker size: {net_draw_sizes}")

    driver.execute_script(
        "document.querySelector('[data-layer-config=\"datacenters\"]').click(); const select = document.querySelector('select[name=sizeBy]'); select.value = 'none'; document.querySelector('#layer-filter-form .dc-modal-primary').click();"
    )
    return {"options": options, "total_draw_sizes": total_draw, "net_draw_sizes": net_draw_sizes, "screenshot": str(screenshot)}


def verify_data_center_glow(driver: webdriver.Remote, screenshot_dir: pathlib.Path) -> dict:
    driver.execute_script(
        """
        document.querySelector('[data-layer-config="datacenters"]').click();
        const select = document.querySelector('#layer-filter-form [name="glowBy"]');
        select.value = 'contestation';
        document.querySelector('#layer-filter-form .dc-modal-primary').click();
        """
    )
    appearance = driver.execute_script(
        """
        const inspect = (label) => {
          const marker = document.querySelector(`.dc-map-marker--center[aria-label="${label}"]`);
          const style = getComputedStyle(marker);
          const glow = getComputedStyle(marker, '::before');
          return {
            kind: marker.dataset.glow,
            color: style.getPropertyValue('--marker-glow-color').trim(),
            opacity: Number(style.getPropertyValue('--marker-glow-opacity')),
            scale: Number(style.getPropertyValue('--marker-glow-scale')),
            fieldWidth: parseFloat(glow.width),
            markerWidth: parseFloat(style.width),
            fieldOpacity: Number(glow.opacity),
          };
        };
        return {
          contested: inspect('Amazon Data Services BWI-150 through BWI-153'),
          quiet: inspect('Cogent Elkridge'),
          intermediate: inspect('AiNET Beltsville Data Center'),
          query: JSON.parse(new URL(location.href).searchParams.get('filters')).datacenters.glowBy,
        };
        """
    )
    if appearance["contested"]["kind"] != "contested" or appearance["contested"]["color"] != "#ff263f":
        raise AssertionError(f"contested facility did not receive a red glow: {appearance}")
    if appearance["quiet"]["kind"] != "quiet" or appearance["quiet"]["color"] != "#ffffff":
        raise AssertionError(f"quiet facility did not receive a white glow: {appearance}")
    if appearance["intermediate"]["kind"] != "none" or appearance["intermediate"]["opacity"] != 0:
        raise AssertionError(f"intermediate facility received a misleading glow: {appearance}")
    if appearance["contested"]["fieldWidth"] < appearance["contested"]["markerWidth"] * 4:
        raise AssertionError(f"contestation glow did not radiate beyond the marker: {appearance}")
    if appearance["query"] != "contestation":
        raise AssertionError(f"glow selection was not persisted in query state: {appearance}")

    driver.execute_script(
        """
        const map = window.__codeCollectiveDatacenterMap;
        map.jumpTo({ center: [-76.75, 39.05], zoom: 7.25, bearing: 0, pitch: 0 });
        """
    )
    time.sleep(.4)
    screenshot = save_screenshot(driver, screenshot_dir, "datacenters-contestation-glow.png")

    driver.execute_script(
        """
        document.querySelector('[data-layer-config="datacenters"]').click();
        document.querySelector('#layer-filter-form [name="glowBy"]').value = 'none';
        document.querySelector('#layer-filter-form .dc-modal-primary').click();
        """
    )
    disabled_opacity = driver.execute_script(
        "return Number(getComputedStyle(document.querySelector('.dc-map-marker--center')).getPropertyValue('--marker-glow-opacity'));"
    )
    if disabled_opacity != 0:
        raise AssertionError(f"No glow did not disable the dimension: {disabled_opacity}")

    driver.execute_script(
        """
        document.querySelector('[data-layer-config="datacenters"]').click();
        document.querySelector('#layer-filter-form [name="glowBy"]').value = 'contestation';
        document.querySelector('#layer-filter-form .dc-modal-primary').click();
        """
    )
    return {"appearance": appearance, "disabled_opacity": disabled_opacity, "screenshot": str(screenshot)}


def verify_power_interchanges(driver: webdriver.Remote, screenshot_dir: pathlib.Path) -> dict:
    layer_id = "remote-power-interchanges-point"
    set_checkbox(driver, "show-power-interchanges", True)
    driver.find_element(By.CSS_SELECTOR, '[data-layer-locate="power-interchanges"]').click()
    WebDriverWait(driver, 30).until(
        lambda d: "78 border corridors" in d.find_element(By.ID, "status-power-interchanges").text
    )
    hit = WebDriverWait(driver, 20).until(
        lambda d: d.execute_script(
            """
            const map = window.__codeCollectiveDatacenterMap;
            if (!map.getLayer(arguments[0])) return null;
            const features = map.queryRenderedFeatures({layers: [arguments[0]]});
            if (!features.length) return null;
            const feature = features.find((candidate) => candidate.properties.voltage_kv === '500') || features[0];
            const point = map.project(feature.geometry.coordinates);
            return {
              x: point.x,
              y: point.y,
              rendered: features.length,
              crossingId: feature.properties.crossing_id,
              symbol: map.getLayoutProperty(arguments[0], 'text-field')
            };
            """,
            layer_id,
        )
    )
    dispatch_hover(driver, hit["x"], hit["y"])
    inspector = WebDriverWait(driver, 15).until(
        lambda d: d.execute_script(
            r"""
            const detail = document.getElementById('record-detail');
            const text = detail.textContent.replace(/\s+/g, ' ').trim();
            if (!text.includes('transmission crossing') || !text.includes('27,111,098 MWh')) return null;
            return {
              title: detail.querySelector('h2')?.textContent.trim() || '',
              text,
              sources: detail.querySelectorAll('.dc-record-sources a').length
            };
            """
        )
    )
    if "Actual direction and MW are not published for this individual crossing" not in inspector["text"]:
        raise AssertionError(f"interchange hover implied a per-line flow measurement: {inspector}")
    if "Bidirectional interstate interchange corridor" not in inspector["text"]:
        raise AssertionError(f"interchange hover omitted its bidirectional physical role: {inspector}")
    dispatch_click(driver, hit["x"], hit["y"])
    WebDriverWait(driver, 10).until(
        lambda d: d.find_element(By.ID, "close-record-detail").is_displayed()
        and d.find_element(By.CSS_SELECTOR, "#record-detail h2").text == inspector["title"]
    )
    screenshot = save_screenshot(driver, screenshot_dir, "datacenters-power-import-export-layer.png")
    driver.find_element(By.ID, "close-record-detail").click()
    set_checkbox(driver, "show-power-interchanges", False)
    return {"hit": hit, "inspector": inspector, "screenshot": str(screenshot)}


def verify_transmission_color_key(driver: webdriver.Remote, screenshot_dir: pathlib.Path) -> dict:
    layer_id = "remote-electric-transmission-lines-line"
    set_checkbox(driver, "show-electric-transmission-lines", True)
    theme_options = driver.execute_script(
        """
        document.querySelector('[data-layer-config="electric-transmission-lines"]').click();
        const select = document.querySelector('#layer-filter-form [name="colorTheme"]');
        const options = [...select.options].map((option) => ({value: option.value, label: option.textContent.trim()}));
        select.value = 'black-body';
        document.querySelector('#layer-filter-form .dc-modal-primary').click();
        return options;
        """
    )
    driver.find_element(By.CSS_SELECTOR, '[data-layer-locate="electric-transmission-lines"]').click()
    hit = WebDriverWait(driver, 45).until(
        lambda d: d.execute_script(
            """
            const map = window.__codeCollectiveDatacenterMap;
            if (!map.getLayer(arguments[0])) return null;
            const features = map.queryRenderedFeatures({layers: [arguments[0]]});
            const feature = features.find((candidate) => Number(candidate.properties.VOLTAGE) > 0) || features[0];
            if (!feature) return null;
            const coordinates = feature.geometry.type === 'MultiLineString'
              ? feature.geometry.coordinates.flat()
              : feature.geometry.coordinates;
            const width = map.getCanvas().clientWidth;
            const height = map.getCanvas().clientHeight;
            const candidates = coordinates.map((coordinate) => ({coordinate, point: map.project(coordinate)}))
              .filter(({point}) => point.x >= 4 && point.x <= width - 4 && point.y >= 4 && point.y <= height - 4)
              .sort((a, b) => Math.hypot(a.point.x - width / 2, a.point.y - height / 2)
                - Math.hypot(b.point.x - width / 2, b.point.y - height / 2));
            if (!candidates.length) return null;
            return {
              x: candidates[0].point.x,
              y: candidates[0].point.y,
              voltageClass: feature.properties.VOLT_CLASS || '',
              voltage: Number(feature.properties.VOLTAGE) || null,
              paint: map.getPaintProperty(arguments[0], 'line-color')
            };
            """,
            layer_id,
        )
    )
    dispatch_hover(driver, hit["x"], hit["y"])
    key = WebDriverWait(driver, 15).until(
        lambda d: d.execute_script(
            """
            const key = document.querySelector('#record-detail .dc-feature-color-key');
            const swatch = key?.querySelector('.dc-color-key-swatch');
            const label = key?.querySelector('small');
            const theme = key?.querySelector('strong');
            if (!key || !swatch || !label) return null;
            return {
              color: swatch.style.getPropertyValue('--dc-key-color'),
              label: label.textContent.trim(),
              theme: theme?.textContent.trim() || '',
              itemCount: key.querySelectorAll('.dc-color-key-item').length
            };
            """
        )
    )
    if key["theme"] != "Black-body warmth" or "Voltage proxy" not in key["label"]:
        raise AssertionError(f"transmission heat theme was not reflected in hover: {hit} {key}")
    if key["itemCount"]:
        raise AssertionError(f"transmission hover included a full legend: {key}")
    if {option["value"] for option in theme_options} != {"default", "black-body", "forge", "stellar"}:
        raise AssertionError(f"transmission heat theme options were incomplete: {theme_options}")
    screenshot = save_screenshot(driver, screenshot_dir, "datacenters-transmission-color-key.png")
    driver.execute_script(
        """
        document.querySelector('[data-layer-config="electric-transmission-lines"]').click();
        document.querySelector('#layer-filter-form [name="colorTheme"]').value = 'default';
        document.querySelector('#layer-filter-form .dc-modal-primary').click();
        """
    )
    set_checkbox(driver, "show-electric-transmission-lines", False)
    return {"hit": hit, "key": key, "theme_options": theme_options, "screenshot": str(screenshot)}


def zoom_until_parcels_visible(driver: webdriver.Remote, max_clicks: int) -> str:
    zoom_in = driver.find_element(By.CSS_SELECTOR, ".maplibregl-ctrl-zoom-in")
    status = driver.find_element(By.ID, "parcel-status")
    text = status.text.strip()
    for _ in range(max_clicks + 1):
        text = status.text.strip()
        if "property boundaries visible" in text.lower() or text.lower().startswith("showing "):
            return text
        zoom_before = driver.execute_script("return window.__codeCollectiveDatacenterMap.getZoom();")
        zoom_in.click()
        try:
            WebDriverWait(driver, 5).until(
                lambda d: d.execute_script("return window.__codeCollectiveDatacenterMap.getZoom();") > zoom_before + 0.8
            )
            WebDriverWait(driver, 15).until(
                lambda d: "loading property boundaries" not in d.find_element(By.ID, "parcel-status").text.lower()
            )
        except Exception:
            pass
    raise AssertionError(f"parcel layer never became visible; last status={text!r}")


def read_probe(driver: webdriver.Remote) -> dict:
    return driver.execute_script("return window.__ccDatacenterProbe;")


def dispatch_hover(driver: webdriver.Remote, x: float, y: float) -> None:
    driver.execute_script(
        """
        const canvas = document.querySelector('#datacenter-map canvas.maplibregl-canvas');
        const rect = canvas.getBoundingClientRect();
        const clientX = rect.left + arguments[0];
        const clientY = rect.top + arguments[1];
        const target = document.elementFromPoint(clientX, clientY) || canvas;
        for (const type of ['pointermove', 'mousemove']) {
          target.dispatchEvent(new MouseEvent(type, {
            bubbles: true,
            cancelable: true,
            view: window,
            clientX,
            clientY
          }));
        }
        window.__ccDatacenterProbe.hovers.push({
          at: performance.now(),
          x: arguments[0],
          y: arguments[1]
        });
        """,
        x,
        y,
    )


def dispatch_click(driver: webdriver.Remote, x: float, y: float) -> None:
    driver.execute_script(
        """
        const canvas = document.querySelector('#datacenter-map canvas.maplibregl-canvas');
        const rect = canvas.getBoundingClientRect();
        canvas.dispatchEvent(new MouseEvent('click', {
          bubbles: true,
          cancelable: true,
          view: window,
          clientX: rect.left + arguments[0],
          clientY: rect.top + arguments[1]
        }));
        """,
        x,
        y,
    )


def wait_for_lookup_result(driver: webdriver.Remote, fetch_count_before: int, detail_count_before: int, timeout: int) -> dict | None:
    deadline = time.time() + timeout
    while time.time() < deadline:
      probe = read_probe(driver)
      fetches = probe.get("fetches", [])
      details = probe.get("detailRenders", [])
      for fetch in fetches[fetch_count_before:]:
        if fetch.get("kind") != "lookup" or fetch.get("finishedAt") is None:
          continue
        matching_detail = None
        for detail in details[detail_count_before:]:
          if detail.get("at", 0) >= fetch.get("startedAt", 0) and "MDP / SDAT public property record" in detail.get("type", ""):
            matching_detail = detail
            break
        if matching_detail:
          return {
            "fetch": fetch,
            "detail": matching_detail,
          }
      time.sleep(0.1)
    return None


def first_parcel_point(driver: webdriver.Remote, sample_limit: int) -> tuple[dict, list[dict]]:
    size = driver.execute_script(
        """
        const rect = document.querySelector('#datacenter-map canvas.maplibregl-canvas').getBoundingClientRect();
        return { width: rect.width, height: rect.height };
        """
    )
    width = float(size["width"])
    height = float(size["height"])
    points = []
    cols = 5
    rows = 4
    margin_x = max(80.0, width * 0.16)
    margin_y = max(70.0, height * 0.18)
    xs = [margin_x + ((width - (margin_x * 2)) * idx / (cols - 1)) for idx in range(cols)]
    ys = [margin_y + ((height - (margin_y * 2)) * idx / (rows - 1)) for idx in range(rows)]
    for y in ys:
        for x in xs:
            points.append({"x": round(x, 1), "y": round(y, 1)})

    attempted = []
    for point in points[:sample_limit]:
        probe_before = read_probe(driver)
        dispatch_hover(driver, point["x"], point["y"])
        result = wait_for_lookup_result(
            driver,
            fetch_count_before=len(probe_before.get("fetches", [])),
            detail_count_before=len(probe_before.get("detailRenders", [])),
            timeout=6,
        )
        attempted.append({"point": point, "hit": bool(result)})
        if result:
            return point, attempted
    raise AssertionError(f"no parcel hover point produced a lookup; attempted={attempted}")


def collect_hover_samples(driver: webdriver.Remote, point: dict, count: int) -> list[dict]:
    samples = []
    for index in range(count):
        # Re-arm the parcel lookup after point discovery and between samples.
        # Remaining inside the same highlighted polygon correctly uses the
        # cached inspector and does not issue another network request.
        set_checkbox(driver, "hover-parcels", False)
        set_checkbox(driver, "hover-parcels", True)
        driver.execute_script(
            "document.querySelector('#datacenter-map canvas.maplibregl-canvas')"
            ".dispatchEvent(new MouseEvent('mouseleave', {bubbles: true}));"
        )
        probe_before = read_probe(driver)
        start = time.perf_counter()
        dispatch_hover(driver, point["x"], point["y"])
        result = wait_for_lookup_result(
            driver,
            fetch_count_before=len(probe_before.get("fetches", [])),
            detail_count_before=len(probe_before.get("detailRenders", [])),
            timeout=6,
        )
        if not result:
            raise AssertionError(f"parcel hover sample {index + 1} did not resolve")
        end = time.perf_counter()
        fetch = result["fetch"]
        detail = result["detail"]
        samples.append(
            {
                "sample": index + 1,
                "hover_to_detail_ms": round((end - start) * 1000, 1),
                "fetch_ms": round(float(fetch["finishedAt"]) - float(fetch["startedAt"]), 1),
                "detail_after_fetch_ms": round(float(detail["at"]) - float(fetch["finishedAt"]), 1),
                "status": int(fetch.get("status") or 0),
                "heading": detail.get("heading") or "",
                "source_link": detail.get("sourceLink") or "",
            }
        )
        time.sleep(0.35)
    return samples


def build_summary(samples: list[dict]) -> dict:
    hover_ms = [sample["hover_to_detail_ms"] for sample in samples]
    fetch_ms = [sample["fetch_ms"] for sample in samples]
    detail_ms = [sample["detail_after_fetch_ms"] for sample in samples]
    return {
        "samples": len(samples),
        "hover_to_detail_ms": {
            "min": min(hover_ms),
            "median": round(statistics.median(hover_ms), 1),
            "max": max(hover_ms),
        },
        "fetch_ms": {
            "min": min(fetch_ms),
            "median": round(statistics.median(fetch_ms), 1),
            "max": max(fetch_ms),
        },
        "detail_after_fetch_ms": {
            "min": min(detail_ms),
            "median": round(statistics.median(detail_ms), 1),
            "max": max(detail_ms),
        },
    }


def run(args: argparse.Namespace) -> int:
    screenshot_dir = pathlib.Path(args.screenshot_dir).resolve()
    driver = new_driver(args.selenium_url, args.width, args.height)
    report_path = screenshot_dir / "datacenters-parcel-hover-report.json"
    try:
        driver.get(args.base_url)
        wait_for_map_ready(driver)
        install_instrumentation(driver)
        if args.mobile_only:
            report = {
                "base_url": args.base_url,
                "mobile_layout": verify_mobile_layout(driver, screenshot_dir),
            }
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(report, indent=2))
            print(json.dumps(report, indent=2))
            return 0
        if args.glow_only:
            report = {
                "base_url": args.base_url,
                "data_center_glow": verify_data_center_glow(driver, screenshot_dir),
            }
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(report, indent=2))
            print(json.dumps(report, indent=2))
            return 0
        layer_search = verify_layer_search(driver)
        layer_color_controls = verify_layer_color_controls(driver, screenshot_dir)
        data_center_draw_scaling = verify_data_center_draw_scaling(driver, screenshot_dir)
        data_center_glow = verify_data_center_glow(driver, screenshot_dir)
        data_center_power_scale = verify_data_center_power_scale(driver, screenshot_dir)
        power_interchanges = verify_power_interchanges(driver, screenshot_dir)
        base_layers = verify_base_layers(driver, screenshot_dir)
        neon_streets = verify_neon_streets(driver, screenshot_dir)
        map_export = verify_no_base_and_png_export(driver, screenshot_dir)
        power_plant_webgl = verify_power_plant_webgl(driver, screenshot_dir)
        transmission_color_key = verify_transmission_color_key(driver, screenshot_dir)
        zoning = verify_baltimore_zoning(driver, screenshot_dir)
        if args.zoning_only:
            report = {
                "base_url": args.base_url,
                "base_layers": base_layers,
                "neon_streets": neon_streets,
                "layer_search": layer_search,
                "layer_color_controls": layer_color_controls,
                "data_center_draw_scaling": data_center_draw_scaling,
                "data_center_glow": data_center_glow,
                "data_center_power_scale": data_center_power_scale,
                "power_interchanges": power_interchanges,
                "map_export": map_export,
                "power_plant_webgl": power_plant_webgl,
                "transmission_color_key": transmission_color_key,
                "baltimore_zoning": zoning,
            }
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(report, indent=2))
            print(json.dumps(report, indent=2))
            return 0
        set_checkbox(driver, "show-parcels", True)
        set_checkbox(driver, "hover-parcels", True)
        visible_status = zoom_until_parcels_visible(driver, args.max_zoom_clicks)
        ready_shot = save_screenshot(driver, screenshot_dir, "datacenters-parcels-ready.png")

        point, attempted = first_parcel_point(driver, args.point_search_limit)
        samples = collect_hover_samples(driver, point, args.hover_samples)
        final_shot = save_screenshot(driver, screenshot_dir, "datacenters-parcel-hover-hit.png")

        report = {
            "base_url": args.base_url,
            "base_layers": base_layers,
            "neon_streets": neon_streets,
            "layer_search": layer_search,
            "layer_color_controls": layer_color_controls,
            "data_center_draw_scaling": data_center_draw_scaling,
            "data_center_glow": data_center_glow,
            "data_center_power_scale": data_center_power_scale,
            "power_interchanges": power_interchanges,
            "map_export": map_export,
            "power_plant_webgl": power_plant_webgl,
            "transmission_color_key": transmission_color_key,
            "baltimore_zoning": zoning,
            "visible_status": visible_status,
            "hover_point": point,
            "attempted_points": attempted,
            "samples": samples,
            "summary": build_summary(samples),
            "screenshots": [str(ready_shot), str(final_shot)],
        }
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))
        return 0
    except Exception as error:
        failure_shot = save_screenshot(driver, screenshot_dir, "datacenters-parcel-hover-failure.png")
        failure = {
            "base_url": args.base_url,
            "error": str(error),
            "failure_screenshot": str(failure_shot),
        }
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(failure, indent=2))
        print(json.dumps(failure, indent=2), file=sys.stderr)
        return 1
    finally:
        driver.quit()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a datacenter parcel-hover Selenium smoke and performance check."
    )
    parser.add_argument(
        "--selenium-url",
        default=os.environ.get("SELENIUM_URL", "http://127.0.0.1:4444/wd/hub"),
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("DATACENTERS_BASE_URL", "https://host.docker.internal:8765/datacenters.html"),
    )
    parser.add_argument("--width", type=int, default=int(os.environ.get("DATACENTERS_SELENIUM_WIDTH", "1440")))
    parser.add_argument("--height", type=int, default=int(os.environ.get("DATACENTERS_SELENIUM_HEIGHT", "1000")))
    parser.add_argument(
        "--screenshot-dir",
        default=os.environ.get("DATACENTERS_SELENIUM_SHOT_DIR", "/tmp/codecollective-datacenters-selenium"),
    )
    parser.add_argument("--hover-samples", type=int, default=int(os.environ.get("DATACENTERS_HOVER_SAMPLES", "5")))
    parser.add_argument("--max-zoom-clicks", type=int, default=int(os.environ.get("DATACENTERS_MAX_ZOOM_CLICKS", "8")))
    parser.add_argument("--point-search-limit", type=int, default=int(os.environ.get("DATACENTERS_POINT_SEARCH_LIMIT", "20")))
    parser.add_argument("--zoning-only", action="store_true", help="Verify Baltimore zoning rendering and hover, then exit.")
    parser.add_argument("--mobile-only", action="store_true", help="Verify the touch layout and mobile inspector, then exit.")
    parser.add_argument("--glow-only", action="store_true", help="Verify the data-center contestation glow, then exit.")
    return parser.parse_args()


if __name__ == "__main__":
    sys.exit(run(parse_args()))
