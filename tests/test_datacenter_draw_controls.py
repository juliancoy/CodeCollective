"""Exercise the actual browser data join and scaling functions without a map server."""

import re
import subprocess
from pathlib import Path


SCRIPT = (Path(__file__).parents[1] / "datacenters/js/datacenters.js").read_text()
DRAW_CODE = SCRIPT[SCRIPT.index("  const POINT_SCALE_LABELS"):SCRIPT.index("  let powerPlantBoltLayer")]


def run_js(code):
    result = subprocess.run(["node"], input="const assert = require('node:assert/strict');\n" + code,
                            text=True, capture_output=True)
    assert result.returncode == 0, result.stderr


def test_osm_power_join_keeps_identity_and_missing_values_separate():
    run_js(DRAW_CODE + """
      const feature = (id) => ({id, properties: {osm_type: 'way', osm_id: id, name: 'Original'}});
      const base = {features: [feature(1), feature(2), feature(3)]};
      const sources = [{title: 'Operator', retrieved_url: 'https://example.com/spec'}];
      const enriched = mergeDataCenterPowerProfiles(base, {records: [
        {id: 'osm-way-1', osm_type: 'way', osm_id: 1, sources,
         power_profile: {reported_power_capacity_mw: 36, estimated_power_draw_mw: -2,
                         reported_grid_demand_mw: '80', name: 'Wrong', osm_id: 99}},
        {id: 'osm-way-2', osm_type: 'node', osm_id: 2,
         power_profile: {reported_grid_demand_mw: 80}},
        {id: 'osm-way-3', osm_type: 'way', osm_id: 3,
         power_profile: {reported_grid_demand_mw: 0}},
      ]});
      assert.equal(base.features[0].properties.reported_power_capacity_mw, undefined);
      assert.equal(enriched.features[0].properties.name, 'Original');
      assert.equal(enriched.features[0].properties.osm_id, 1);
      assert.equal(enriched.features[0].properties.reported_power_capacity_mw, 36);
      assert.equal(enriched.features[0].properties.estimated_power_draw_mw, null);
      assert.equal(enriched.features[0].properties.reported_grid_demand_mw, null);
      assert.equal(enriched.features[1], base.features[1]);
      const coverage = dataCenterDrawCoverage(enriched.features.map(f => f.properties));
      assert.equal(coverage.known, 2);
      assert.equal(coverage.missing, 1);
      assert.equal(coverage.counts.reported_grid_demand_mw, 1);
      assert.deepEqual(dataCenterPowerSources({power_sources: JSON.stringify(sources)}),
                       [['Operator', 'https://example.com/spec']]);
      assert.deepEqual(dataCenterPowerSources({power_sources: 'malformed'}), []);
    """)


def test_draw_scaling_supports_projection_zero_missing_and_uniform_values():
    run_js(DRAW_CODE + """
      const records = [{reported_power_capacity_mw: 36}, {projected_power_demand_mw: 80}, {},
                       {reported_power_capacity_mw: 0}];
      const scaled = pointScaleFactors(records, 'reported_power_capacity_mw');
      assert.ok(scaled.get(records[1]) > scaled.get(records[0]));
      assert.ok(scaled.get(records[0]) > scaled.get(records[3]));
      assert.ok(scaled.get(records[3]) > scaled.get(records[2]));
      assert.equal(scaled.get(records[2]), .55);
      assert.deepEqual([...pointScaleFactors(records, 'none').values()], [1,1,1,1]);
      const options = dataCenterPointScaleOptions([{osm_id: 999, reported_power_capacity_mw: 36}]);
      assert.ok(!options.some(([field]) => field === 'osm_id'));
      assert.ok(options.some(([field, label]) => field === 'reported_grid_demand_mw' && label.includes('0 public values')));
    """)


def test_power_plant_uniform_size_survives_normalization():
    names = ['normalizeIconScale', 'normalizeBrightness', 'normalizeBoltOutlineWidth',
             'normalizePowerPlantLayerFilters', 'normalizePowerPlantRenderMaterial']
    functions = '\n'.join(re.search(r'  function ' + name + r'\([^\n]*\) \{.*?\n  \}', SCRIPT, re.S)[0]
                          for name in names)
    material_options = re.search(r'  const POWER_PLANT_RENDER_MATERIAL_OPTIONS = \[.*?\n  \];', SCRIPT, re.S)[0]
    run_js(material_options + functions + """
      const filters = normalizePowerPlantLayerFilters({fillBy: 'resource-adjusted-utilization',
                                                      sizeBy: 'none', iconScale: 2});
      assert.equal(filters.sizeBy, 'none');
      assert.equal(filters.iconScale, 2);
      assert.equal(normalizeIconScale(10), 4);
      assert.equal(normalizeIconScale(.01), .25);
    """)
