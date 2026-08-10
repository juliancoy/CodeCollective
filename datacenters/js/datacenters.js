(() => {
  const DATA_URLS = {
    infrastructure: '/datacenters/data/infrastructure.json',
    entityImages: '/datacenters/data/power-plant-images.json',
    sources: '/datacenters/data/sources.json',
  };
  const POWER_PLANT_WEBGL_LAYER_ID = 'power-plant-bolt-webgl';
  const NEON_STREET_GLOW_LAYER_ID = 'neon-streets-glow';
  const NEON_STREET_CORE_LAYER_ID = 'neon-streets-core';
  const NEON_STREET_LABEL_LAYER_ID = 'neon-streets-label';
  const MAP_FALLBACK_BACKGROUND_LAYER_ID = 'codecollective-map-background';
  const PLANT_IMAGE_FALLBACK = '/datacenters/images/power-plants/fallback/energy-infrastructure-illustration.webp';
  const USGS_IMAGERY_SOURCE = 'https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer';
  const AERIAL_IMAGE_CACHE = 'codecollective-aerial-imagery-v1';
  const AERIAL_IMAGE_WIDTH = 1200;
  const AERIAL_IMAGE_HEIGHT = 675;
  const TRANSPARENT_IMAGE = 'data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=';
  const ENVIROSCREEN_SERVICE = 'https://mdgeodata.md.gov/imap/rest/services/Environment/MD_EnviroScreen/FeatureServer/0';
  const ENVIROSCREEN_QUERY = `${ENVIROSCREEN_SERVICE}/query?${new URLSearchParams({
    where: '1=1',
    outFields: 'GEOID20,P_EJ,OVERBURDENED_COMMUNITY,UNDERSERVED_COMMUNITY',
    returnGeometry: 'true',
    outSR: '4326',
    geometryPrecision: '5',
    maxAllowableOffset: '0.0001',
    f: 'geojson',
  })}`;
  const ENVIROSCREEN_SOURCE_ID = 'mde-enviroscreen';
  const ENVIROSCREEN_FILL_ID = 'mde-enviroscreen-fill';
  const ENVIROSCREEN_LINE_ID = 'mde-enviroscreen-line';
  const PARCEL_SERVICE = 'https://mdgeodata.md.gov/imap/rest/services/PlanningCadastre/MD_ParcelBoundaries/MapServer';
  const PARCEL_SOURCE_ID = 'mdp-sdat-parcels';
  const PARCEL_LAYER_ID = 'mdp-sdat-parcels-line';
  const PARCEL_HOVER_SOURCE_ID = 'mdp-sdat-parcel-hover';
  const PARCEL_HOVER_FILL_ID = 'mdp-sdat-parcel-hover-fill';
  const PARCEL_HOVER_LINE_ID = 'mdp-sdat-parcel-hover-line';
  const PARCEL_MIN_ZOOM = 13;
  const MAP_MIN_ZOOM = 0;
  const MAP_MAX_ZOOM = 18;
  const PARCEL_MAX_FEATURES = 1000;
  const TRANSMISSION_VOLTAGE_COLORS = [
    { value: 'Under 100', label: 'Under 100 kV', color: '#69c7ff' },
    { value: '100-161', label: '100–161 kV', color: '#20b8d8' },
    { value: '220-287', label: '220–287 kV', color: '#a58bff' },
    { value: '345', label: '345 kV', color: '#f3a712' },
    { value: '500', label: '500 kV', color: '#ff665e' },
    { value: '735 And Above', label: '735 kV and above', color: '#ff4fc3' },
    { value: 'DC', aliases: ['Dc'], label: 'DC', color: '#f8f9fa' },
  ];
  const MD_IMAP_TRANSMISSION_COLORS = ['step', ['coalesce', ['get', 'Voltage_kV'], 0], '#69c7ff', 115, '#20b8d8', 230, '#a58bff', 345, '#f3a712', 500, '#ff665e'];
  const HIFLD_TRANSMISSION_COLORS = [
    'match', ['get', 'VOLT_CLASS'],
    ...TRANSMISSION_VOLTAGE_COLORS.flatMap((entry) => [
      entry.value, entry.color,
      ...(entry.aliases || []).flatMap((alias) => [alias, entry.color]),
    ]),
    '#aab9c5',
  ];
  const TRANSMISSION_HEAT_PALETTES = [
    { id: 'black-body', label: 'Black-body warmth', colors: ['#50110a', '#9d1d0d', '#e94713', '#ff8426', '#ffc34d', '#fff0ba', '#fffdf2'] },
    { id: 'forge', label: 'Forge heat', colors: ['#2b0b08', '#68110b', '#b5260c', '#ef5815', '#ff9829', '#ffd56a', '#fff4c7'] },
    { id: 'stellar', label: 'Stellar temperature', colors: ['#8f1d14', '#dc3c1d', '#ff7b31', '#ffc35a', '#fff0bf', '#f7fbff', '#b9dcff'] },
  ];
  const LINE_WIDTH_OPTIONS = [
    ['0.5', 'Hairline'],
    ['1', 'Standard'],
    ['2', 'Bold'],
    ['3', 'Heavy'],
    ['5', 'Maximum'],
  ];
  const LINE_WIDTH_BY_DEFAULT = [['zoom', 'Zoom curve only']];

  function transmissionHeatExpression(field, colors) {
    const value = ['to-number', ['get', field], 0];
    const stops = [69, 115, 230, 345, 500, 735, 1000];
    return ['case', ['<=', value, 0], '#aab9c5', ['interpolate', ['linear'], value, ...stops.flatMap((stop, index) => [stop, colors[index]])]];
  }

  function transmissionLineThemes(field, defaultExpression) {
    return [
      { id: 'uniform', label: 'Uniform layer color', field, expression: null },
      { id: 'default', label: 'Voltage classes', field, expression: defaultExpression },
      ...TRANSMISSION_HEAT_PALETTES.map((palette) => ({
        ...palette,
        field,
        expression: transmissionHeatExpression(field, palette.colors),
      })),
    ];
  }
  const ESRI_BUILDINGS = {
    id: 'esri-3d-buildings',
    name: 'Esri 3D Buildings',
    description: 'Streaming 3D building meshes',
    service: 'https://basemaps3d.arcgis.com/arcgis/rest/services/Esri3D_Buildings_v1/SceneServer/layers/0',
    sourceUrl: 'https://www.arcgis.com/home/item.html?id=b8fec5af7dfe4866b1b8ac2d2800f282',
    sourceLabel: 'Esri 3D Buildings',
    color: '#72b7d2',
    minZoom: 13,
    focus: { center: [-76.6122, 39.2904], zoom: 15.2, pitch: 52 },
  };
  const BASE_LAYER_CONFIGS = [
    {
      id: 'street-map',
      name: 'Street map',
      description: 'The selected OpenFreeMap street style, including roads, labels, land, and water.',
      category: 'Base map',
      sourceUrl: 'https://openfreemap.org/',
      sourceLabel: 'OpenFreeMap',
    },
    {
      id: 'md-six-inch-imagery',
      name: 'Maryland six-inch imagery',
      description: 'Statewide six-inch aerial imagery flown from 2023 through 2025.',
      category: 'High-resolution state imagery',
      sourceUrl: 'https://mdgeodata.md.gov/imagery/rest/services/SixInch/SixInchImagery/MapServer',
      sourceLabel: 'Maryland iMAP / DoIT',
      source: {
        type: 'raster',
        tiles: ['https://mdgeodata.md.gov/imagery/rest/services/SixInch/SixInchImagery/MapServer/export?bbox={bbox-epsg-3857}&bboxSR=3857&imageSR=3857&size=512,512&format=jpg&transparent=false&f=image'],
        tileSize: 512,
        minzoom: 5,
        maxzoom: 19,
        bounds: [-79.5254, 37.8632, -75.0091, 39.7577],
        attribution: '<a href="https://mdgeodata.md.gov/imagery/rest/services/SixInch/SixInchImagery/MapServer" target="_blank">Maryland iMAP / DoIT</a>',
      },
    },
    {
      id: 'esri-world-imagery',
      name: 'Esri World Imagery',
      description: 'Global satellite and aerial imagery, including sub-meter coverage in much of the United States.',
      category: 'Global satellite imagery',
      sourceUrl: 'https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer',
      sourceLabel: 'Esri World Imagery',
      source: {
        type: 'raster',
        tiles: ['https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'],
        tileSize: 256,
        maxzoom: 23,
        attribution: '<a href="https://www.esri.com/" target="_blank">Esri and imagery contributors</a>',
      },
    },
    {
      id: 'usgs-imagery',
      name: 'USGS Imagery Only',
      description: 'The National Map orthoimagery, primarily public-domain NAIP aerial coverage in the continental United States.',
      category: 'National aerial imagery',
      sourceUrl: USGS_IMAGERY_SOURCE,
      sourceLabel: 'U.S. Geological Survey / The National Map',
      source: {
        type: 'raster',
        tiles: [`${USGS_IMAGERY_SOURCE}/tile/{z}/{y}/{x}`],
        tileSize: 256,
        maxzoom: 16,
        attribution: '<a href="https://www.usgs.gov/programs/national-geospatial-program/national-map" target="_blank">USGS The National Map</a>',
      },
    },
  ];
  const BASE_LAYER_IDS = new Set(BASE_LAYER_CONFIGS.map((config) => config.id));
  const CORE_LAYER_PREVIEWS = {
    ...Object.fromEntries(BASE_LAYER_CONFIGS.map((config) => [config.id, config])),
    datacenters: {
      id: 'datacenters',
      name: 'Data centers',
      description: 'Documented Maryland campuses, facilities, and proposals in the project inventory.',
      category: 'Facility inventory',
      sourceUrl: '/datacenters/data/infrastructure.json',
      sourceLabel: 'Published data-center inventory',
      statusId: 'datacenter-layer-count',
      statusSuffix: ' documented records',
    },
    'power-plants': {
      id: 'power-plants',
      name: 'Power plants',
      description: 'EIA generation facilities with published capacity and production fields.',
      category: 'Generation inventory',
      sourceUrl: '/datacenters/data/infrastructure.json',
      sourceLabel: 'Published EIA-derived power-plant inventory',
      statusId: 'power-plant-layer-count',
      statusSuffix: ' documented facilities',
    },
    'neon-streets': {
      id: 'neon-streets',
      name: 'Neon streets',
      description: 'GPU-rendered OpenFreeMap road overlay, filtered to I-95 by default.',
      category: 'Road network',
      sourceUrl: 'https://openfreemap.org/',
      sourceLabel: 'OpenFreeMap / OpenStreetMap',
      minZoom: 0,
      maxZoom: MAP_MAX_ZOOM,
      statusId: 'neon-streets-status',
    },
    enviroscreen: {
      id: 'enviroscreen',
      name: 'MDE EnviroScreen',
      description: 'Maryland environmental-justice screening scores and community designations by census tract.',
      category: 'Environmental screening',
      sourceUrl: 'https://mde.maryland.gov/Environmental_Justice/Pages/MDEnviroScreen.aspx',
      sourceLabel: 'Maryland Department of the Environment',
      minZoom: 0,
      maxZoom: MAP_MAX_ZOOM,
      statusId: 'enviroscreen-status',
    },
    parcels: {
      id: 'parcels',
      name: 'MDP / SDAT parcels',
      description: 'Public property boundaries and coordinate-based assessment record lookup.',
      category: 'Property records',
      sourceUrl: PARCEL_SERVICE,
      sourceLabel: 'Maryland Department of Planning / SDAT',
      minZoom: PARCEL_MIN_ZOOM,
      maxZoom: MAP_MAX_ZOOM,
      statusId: 'parcel-status',
    },
  };
  const REMOTE_LAYERS = [
    {
      id: 'maryland-state-boundary',
      name: 'Maryland state boundary',
      description: 'Official political outline of the State of Maryland',
      category: 'Political boundaries',
      service: 'https://mdgeodata.md.gov/imap/rest/services/Boundaries/MD_PoliticalBoundaries/FeatureServer/0',
      sourceUrl: 'https://mdgeodata.md.gov/imap/rest/services/Boundaries/MD_PoliticalBoundaries/FeatureServer/0',
      sourceLabel: 'Maryland iMAP State Boundary',
      attribution: 'MD iMAP, SHA, DoIT',
      geometry: 'polygon',
      color: '#f3c969',
      fillColor: '#f3c969',
      fillOpacity: .025,
      lineWidth: ['interpolate', ['linear'], ['zoom'], 6, 2.4, 12, 4.5],
      lineOpacity: .96,
      focus: { center: [-76.7, 39.05], zoom: 7.2 },
      minZoom: 0,
      maxFeatures: 10,
      outFields: ['OBJECTID', 'State', 'Shape__Area', 'Shape__Length'],
      titleFields: ['State'],
      facts: [['State', 'State'], ['Object ID', 'OBJECTID'], ['Boundary area', 'Shape__Area'], ['Boundary length', 'Shape__Length']],
    },
    {
      id: 'maryland-county-boundaries',
      name: 'Maryland county boundaries',
      description: 'Political borders for Maryland counties and Baltimore City',
      category: 'Political boundaries',
      service: 'https://mdgeodata.md.gov/imap/rest/services/Boundaries/MD_PoliticalBoundaries/FeatureServer/1',
      sourceUrl: 'https://mdgeodata.md.gov/imap/rest/services/Boundaries/MD_PoliticalBoundaries/FeatureServer/1',
      sourceLabel: 'Maryland iMAP County Boundaries',
      attribution: 'MD iMAP, MDP, MDOT SHA',
      geometry: 'polygon',
      color: '#8fd2ed',
      fillColor: '#8fd2ed',
      fillOpacity: .035,
      lineWidth: ['interpolate', ['linear'], ['zoom'], 6, .7, 12, 2.1],
      lineOpacity: .88,
      focus: { center: [-76.7, 39.05], zoom: 7.2 },
      minZoom: 0,
      maxFeatures: 50,
      outFields: ['COUNTY', 'DISTRICT', 'TSD_ID', 'OBJECTID_1', 'COUNTY_FIP', 'COUNTYNUM', 'Shape__Area', 'Shape__Length'],
      titleFields: ['COUNTY'],
      facts: [['County', 'COUNTY'], ['County FIPS', 'COUNTY_FIP'], ['County number', 'COUNTYNUM'], ['MDOT SHA district', 'DISTRICT'], ['Object ID', 'OBJECTID_1']],
    },
    {
      id: 'dhcd-multifamily',
      name: 'DHCD multifamily sites',
      description: 'State-supported multifamily properties',
      service: 'https://mdgeodata.md.gov/imap/rest/services/BusinessEconomy/MD_MultifamilySites/FeatureServer/0',
      sourceUrl: 'https://mdgeodata.md.gov/imap/rest/services/BusinessEconomy/MD_MultifamilySites/FeatureServer/0',
      sourceLabel: 'Maryland DHCD Multifamily Sites',
      geometry: 'point',
      color: '#f29e4c',
      scaleFields: [['ResUnits', 'Residential units'], ['DisUnits', 'Disabled-accessible units']],
      minZoom: 7,
      outFields: ['ProjID', 'ProjName', 'MFPrograms', 'ProjType', 'ResUnits', 'DisUnits', 'Address', 'City', 'Zip'],
      titleFields: ['ProjName', 'Address'],
      facts: [['Project ID', 'ProjID'], ['Programs', 'MFPrograms'], ['Project type', 'ProjType'], ['Residential units', 'ResUnits'], ['Disabled units', 'DisUnits'], ['Address', 'Address'], ['City', 'City']],
    },
    {
      id: 'dhcd-qct',
      name: 'DHCD qualified census tracts',
      description: 'Federal housing-credit target geography',
      service: 'https://mdgeodata.md.gov/imap/rest/services/BusinessEconomy/MD_HousingDesignatedAreas/FeatureServer/1',
      sourceUrl: 'https://mdgeodata.md.gov/imap/rest/services/BusinessEconomy/MD_HousingDesignatedAreas/FeatureServer/1',
      sourceLabel: 'Maryland DHCD Qualified Census Tracts',
      geometry: 'polygon',
      color: '#b38bd4',
      minZoom: 0,
      outFields: ['QCT', 'COUNTY_N', 'GEOID20'],
      titleFields: ['GEOID20', 'QCT'],
      facts: [['Tract GEOID', 'GEOID20'], ['Qualified tract', 'QCT'], ['County', 'COUNTY_N']],
    },
    {
      id: 'dhcd-just-communities',
      name: 'DHCD Just Communities',
      description: 'Housing and environmental indicators',
      service: 'https://mdgeodata.md.gov/imap/rest/services/BusinessEconomy/MD_HousingDesignatedAreas/FeatureServer/9',
      sourceUrl: 'https://mdgeodata.md.gov/imap/rest/services/BusinessEconomy/MD_HousingDesignatedAreas/FeatureServer/9',
      sourceLabel: 'Maryland DHCD Just Communities',
      geometry: 'polygon',
      color: '#e76f51',
      minZoom: 0,
      outFields: ['GEOID', 'NAMELSAD', 'County', 'VacantHousingUnitsPer', 'SuperfundProximityPerc', 'LeadPaintExposurePer', 'RECAP'],
      titleFields: ['NAMELSAD', 'GEOID'],
      facts: [['GEOID', 'GEOID'], ['County', 'County'], ['Vacant housing percentile', 'VacantHousingUnitsPer'], ['Superfund proximity percentile', 'SuperfundProximityPerc'], ['Lead exposure percentile', 'LeadPaintExposurePer'], ['RECAP', 'RECAP']],
    },
    {
      id: 'mdp-generalized-zoning',
      name: 'MDP generalized zoning (2021)',
      description: 'WorldSim statewide canonical zoning fallback',
      service: 'https://services.arcgis.com/njFNhDsUCentVYJW/arcgis/rest/services/GeneralizedZoning2021_StoryMap/FeatureServer/3',
      sourceUrl: 'https://storymaps.arcgis.com/stories/4a3bd4e562c44d41b2f0f413d44aff13',
      sourceLabel: 'Maryland Department of Planning Generalized Zoning',
      geometry: 'polygon',
      color: '#55a868',
      fillColor: [
        'match', ['get', 'GENZONE'],
        'COMMERCIAL', '#3a86ff',
        'INDUSTRIAL', '#f2c94c',
        'MIXED USE', '#8d74c7',
        'OTHER', '#8c9aa6',
        'HIGH DENSITY RESIDENTIAL', '#167944',
        'MEDIUM DENSITY RESIDENTIAL', '#35a85f',
        'LOW DENSITY RESIDENTIAL', '#70c77c',
        'VERY LOW DENSITY RESIDENTIAL', '#a8d99c',
        'RURAL HIGH DENSITY RESIDENTIAL', '#5d9e66',
        'RURAL MEDIUM DENSITY RES', '#82b879',
        'RURAL LOW DENSITY RESIDENTIAL', '#aacb91',
        '#8c9aa6',
      ],
      focus: { center: [-76.7, 39.05], zoom: 8.8 },
      minZoom: 0,
      outFields: ['GENZONE', 'OVERLAY', 'JURSCODE', 'MUNICIPALITY_NAME', 'ABBREVIATION', 'UPDATEYR', 'ACRES', 'Source'],
      titleFields: ['GENZONE', 'ABBREVIATION'],
      facts: [['Generalized zone', 'GENZONE'], ['Overlay', 'OVERLAY'], ['Jurisdiction code', 'JURSCODE'], ['Municipality', 'MUNICIPALITY_NAME'], ['Local abbreviation', 'ABBREVIATION'], ['Source update year', 'UPDATEYR'], ['Acres', 'ACRES']],
    },
    {
      id: 'baltimore-city-zoning',
      name: 'Baltimore City zoning (MDP 2021)',
      description: 'WorldSim statewide fallback, filtered to Baltimore City',
      service: 'https://services.arcgis.com/njFNhDsUCentVYJW/arcgis/rest/services/GeneralizedZoning2021_StoryMap/FeatureServer/3',
      sourceUrl: 'https://storymaps.arcgis.com/stories/4a3bd4e562c44d41b2f0f413d44aff13',
      sourceLabel: 'Maryland Department of Planning Generalized Zoning — Baltimore City',
      where: "JURSCODE = 'BACI'",
      geometry: 'polygon',
      color: '#55a868',
      fillColor: [
        'match', ['get', 'GENZONE'],
        'COMMERCIAL', '#3a86ff',
        'INDUSTRIAL', '#f2c94c',
        'MIXED USE', '#8d74c7',
        'OTHER', '#8c9aa6',
        'HIGH DENSITY RESIDENTIAL', '#167944',
        'MEDIUM DENSITY RESIDENTIAL', '#35a85f',
        'LOW DENSITY RESIDENTIAL', '#70c77c',
        'VERY LOW DENSITY RESIDENTIAL', '#a8d99c',
        'RURAL HIGH DENSITY RESIDENTIAL', '#5d9e66',
        'RURAL MEDIUM DENSITY RES', '#82b879',
        'RURAL LOW DENSITY RESIDENTIAL', '#aacb91',
        '#8c9aa6',
      ],
      fillOpacity: .46,
      focus: { center: [-76.6122, 39.2904], zoom: 11.7 },
      minZoom: 0,
      outFields: ['GENZONE', 'OVERLAY', 'JURSCODE', 'MUNICIPALITY_NAME', 'ABBREVIATION', 'UPDATEYR', 'ACRES', 'Source'],
      titleFields: ['GENZONE', 'ABBREVIATION'],
      facts: [['Generalized zone', 'GENZONE'], ['Overlay', 'OVERLAY'], ['Jurisdiction code', 'JURSCODE'], ['Municipality', 'MUNICIPALITY_NAME'], ['Local abbreviation', 'ABBREVIATION'], ['Source update year', 'UPDATEYR'], ['Acres', 'ACRES']],
    },
    {
      id: 'baltimore-nibrs-crime',
      name: 'Baltimore NIBRS crime',
      description: 'Group A incidents, 2022 to present',
      service: 'https://services1.arcgis.com/UWYHeuuJISiGmgXx/arcgis/rest/services/NIBRS_GroupA_Crime_Data/FeatureServer/0',
      sourceUrl: 'https://www.arcgis.com/home/item.html?id=204beefe92a645d79fdf0969957bbdf8',
      sourceLabel: 'Baltimore Police Department NIBRS Group A Crime Data',
      geometry: 'point',
      color: '#e15759',
      scaleFields: [['Total_Incidents', 'Incident count']],
      focus: { center: [-76.6122, 39.2904], zoom: 12.2 },
      minZoom: 12,
      outFields: ['CCNumber', 'CrimeDateTime', 'CrimeCode', 'Description', 'Inside_Outside', 'Weapon', 'Shooting', 'New_District', 'Neighborhood', 'PremiseType', 'Total_Incidents'],
      titleFields: ['Description', 'CrimeCode'],
      facts: [['Incident number', 'CCNumber'], ['Date and time', 'CrimeDateTime'], ['NIBRS code', 'CrimeCode'], ['Description', 'Description'], ['Inside / outside', 'Inside_Outside'], ['Weapon', 'Weapon'], ['Shooting', 'Shooting'], ['Police district', 'New_District'], ['Neighborhood', 'Neighborhood'], ['Premise type', 'PremiseType'], ['Incident count', 'Total_Incidents']],
    },
    {
      id: 'historic-properties',
      name: 'Historic properties',
      description: 'Maryland historic-property inventory',
      service: 'https://mdgeodata.md.gov/imap/rest/services/Historic/MD_InventoryHistoricProperties/MapServer/0',
      sourceUrl: 'https://apps.mht.maryland.gov/mihp/MIHP.aspx',
      sourceLabel: 'Maryland Inventory of Historic Properties',
      geometry: 'polygon',
      color: '#ffd166',
      minZoom: 0,
      outFields: ['MIHPNO', 'FULLADDR', 'TOWN', 'COUNTY', 'PDFLINK', 'CLASS', 'MIHPID'],
      titleFields: ['FULLADDR', 'MIHPNO'],
      facts: [['MIHP number', 'MIHPNO'], ['Address', 'FULLADDR'], ['Town', 'TOWN'], ['County', 'COUNTY'], ['Class', 'CLASS'], ['Inventory ID', 'MIHPID']],
    },
    {
      id: 'dpw-storm-ms4',
      name: 'DPW storm MS4 projects',
      description: 'Baltimore storm-system capital work',
      category: 'Water architecture',
      tags: ['water', 'stormwater', 'ms4', 'drainage', 'baltimore city'],
      service: 'https://dpwdata.baltimorecity.gov/pubgis/rest/services/Hosted/Capital_Improvement_Projects/FeatureServer/0',
      sourceUrl: 'https://dpwdata.baltimorecity.gov/pubgis/rest/services/Hosted/Capital_Improvement_Projects/FeatureServer/0',
      sourceLabel: 'Baltimore DPW Capital Improvement Projects',
      geometry: 'polygon',
      color: '#66c2a5',
      minZoom: 0,
      outFields: ['name', 'projectid', 'projectdes', 'agency', 'structure_', 'contract_number'],
      titleFields: ['name', 'projectid'],
      facts: [['Project ID', 'projectid'], ['Description', 'projectdes'], ['Agency', 'agency'], ['Structure', 'structure_'], ['Contract', 'contract_number']],
    },
    {
      id: 'dpw-stormwater',
      name: 'DPW stormwater projects',
      description: 'Baltimore stormwater capital work',
      category: 'Water architecture',
      tags: ['water', 'stormwater', 'drainage', 'runoff', 'baltimore city'],
      service: 'https://dpwdata.baltimorecity.gov/pubgis/rest/services/Hosted/Capital_Improvement_Projects/FeatureServer/1',
      sourceUrl: 'https://dpwdata.baltimorecity.gov/pubgis/rest/services/Hosted/Capital_Improvement_Projects/FeatureServer/1',
      sourceLabel: 'Baltimore DPW Stormwater Projects',
      geometry: 'polygon',
      color: '#3288bd',
      minZoom: 0,
      outFields: ['projectid', 'name', 'title', 'status', 'phase', 'scope', 'contract_number', 'start', 'finish'],
      titleFields: ['title', 'name', 'projectid'],
      facts: [['Project ID', 'projectid'], ['Status', 'status'], ['Phase', 'phase'], ['Scope', 'scope'], ['Contract', 'contract_number'], ['Start', 'start'], ['Finish', 'finish']],
    },
    {
      id: 'dpw-water',
      name: 'DPW water projects',
      description: 'Baltimore water-system capital work',
      category: 'Water architecture',
      tags: ['water', 'drinking water', 'distribution', 'utility', 'baltimore city'],
      service: 'https://dpwdata.baltimorecity.gov/pubgis/rest/services/Hosted/Capital_Improvement_Projects/FeatureServer/2',
      sourceUrl: 'https://dpwdata.baltimorecity.gov/pubgis/rest/services/Hosted/Capital_Improvement_Projects/FeatureServer/2',
      sourceLabel: 'Baltimore DPW Water Projects',
      geometry: 'polygon',
      color: '#1f78b4',
      minZoom: 0,
      outFields: ['title', 'status', 'phase', 'scope', 'contract_number', 'start', 'finish'],
      titleFields: ['title', 'contract_number'],
      facts: [['Status', 'status'], ['Phase', 'phase'], ['Scope', 'scope'], ['Contract', 'contract_number'], ['Start', 'start'], ['Finish', 'finish']],
    },
    {
      id: 'dpw-wastewater',
      name: 'DPW wastewater projects',
      description: 'Baltimore wastewater capital work',
      category: 'Water architecture',
      tags: ['water', 'wastewater', 'sewer', 'utility', 'baltimore city'],
      service: 'https://dpwdata.baltimorecity.gov/pubgis/rest/services/Hosted/Capital_Improvement_Projects/FeatureServer/3',
      sourceUrl: 'https://dpwdata.baltimorecity.gov/pubgis/rest/services/Hosted/Capital_Improvement_Projects/FeatureServer/3',
      sourceLabel: 'Baltimore DPW Wastewater Projects',
      geometry: 'polygon',
      color: '#5e4fa2',
      minZoom: 0,
      outFields: ['title', 'status', 'phase', 'scope', 'contract_number', 'start', 'finish'],
      titleFields: ['title', 'contract_number'],
      facts: [['Status', 'status'], ['Phase', 'phase'], ['Scope', 'scope'], ['Contract', 'contract_number'], ['Start', 'start'], ['Finish', 'finish']],
    },
    {
      id: 'md-waterbodies-streams',
      name: 'MD rivers and streams',
      description: 'Detailed statewide surface-water flowlines',
      category: 'Water architecture',
      tags: ['water', 'hydrology', 'rivers', 'streams', 'surface water'],
      service: 'https://mdgeodata.md.gov/imap/rest/services/Hydrology/MD_Waterbodies/FeatureServer/2',
      sourceUrl: 'https://mdgeodata.md.gov/imap/rest/services/Hydrology/MD_Waterbodies/FeatureServer',
      sourceLabel: 'Maryland iMAP Rivers and Streams',
      attribution: 'Maryland iMAP',
      geometry: 'line',
      color: '#4cc9f0',
      lineColor: '#4cc9f0',
      focus: { center: [-76.7, 39.05], zoom: 8.2 },
      minZoom: 8,
      outFields: ['OBJECTID', 'LAYER', 'Shape__Length'],
      titleFields: ['LAYER', 'OBJECTID'],
      facts: [['Layer', 'LAYER'], ['Segment length', 'Shape__Length'], ['Object ID', 'OBJECTID']],
    },
    {
      id: 'md-waterbodies-lakes',
      name: 'MD lakes and reservoirs',
      description: 'Detailed statewide lakes, reservoirs, and treated-water bodies',
      category: 'Water architecture',
      tags: ['water', 'hydrology', 'lakes', 'reservoirs', 'surface water'],
      service: 'https://mdgeodata.md.gov/imap/rest/services/Hydrology/MD_Waterbodies/FeatureServer/3',
      sourceUrl: 'https://mdgeodata.md.gov/imap/rest/services/Hydrology/MD_Waterbodies/FeatureServer',
      sourceLabel: 'Maryland iMAP Lakes and Reservoirs',
      attribution: 'Maryland iMAP',
      geometry: 'polygon',
      color: '#80d8ff',
      fillColor: '#80d8ff',
      fillOpacity: .3,
      focus: { center: [-76.7, 39.05], zoom: 8.2 },
      minZoom: 7,
      outFields: ['OBJECTID', 'LAKENAME', 'COUNTY', 'ACRES', 'WATERTREAT', 'SAND_GRAVE'],
      titleFields: ['LAKENAME', 'ALIAS_NAME', 'OBJECTID'],
      facts: [['Lake name', 'LAKENAME'], ['County', 'COUNTY'], ['Acres', 'ACRES'], ['Water treatment', 'WATERTREAT'], ['Sand or gravel', 'SAND_GRAVE']],
    },
    {
      id: 'md-watersheds-12digit',
      name: 'MD 12-digit watersheds',
      description: 'State watershed catchments with tributary and biotic context',
      category: 'Water architecture',
      tags: ['water', 'hydrology', 'watersheds', 'catchments', 'runoff'],
      service: 'https://mdgeodata.md.gov/imap/rest/services/Hydrology/MD_Watersheds/FeatureServer/2',
      sourceUrl: 'https://mdgeodata.md.gov/imap/rest/services/Hydrology/MD_Watersheds/FeatureServer',
      sourceLabel: 'Maryland iMAP Watersheds',
      attribution: 'Maryland iMAP',
      geometry: 'polygon',
      color: '#90be6d',
      fillColor: '#90be6d',
      fillOpacity: .08,
      lineWidth: ['interpolate', ['linear'], ['zoom'], 6, .7, 11, 1.8],
      lineOpacity: .75,
      focus: { center: [-76.7, 39.05], zoom: 8.0 },
      minZoom: 6,
      outFields: ['OBJECTID', 'dnr12dig', 'mde8name', 'straname', 'hua14', 'cbi'],
      titleFields: ['straname', 'mde8name', 'dnr12dig'],
      facts: [['12-digit watershed', 'dnr12dig'], ['8-digit watershed', 'mde8name'], ['Tributary strategy', 'straname'], ['HUA 14', 'hua14'], ['Biotic integrity', 'cbi']],
    },
    {
      id: 'md-fema-floodplain',
      name: 'MD FEMA floodplain',
      description: 'Effective FEMA flood-hazard polygons for Maryland',
      category: 'Water architecture',
      tags: ['water', 'floodplain', 'flood risk', 'fema', 'resilience'],
      service: 'https://mdgeodata.md.gov/imap/rest/services/Hydrology/MD_Floodplain/FeatureServer/1',
      sourceUrl: 'https://mdgeodata.md.gov/imap/rest/services/Hydrology/MD_Floodplain/FeatureServer',
      sourceLabel: 'Maryland iMAP Effective FEMA Floodplain',
      attribution: 'Maryland iMAP / FEMA',
      geometry: 'polygon',
      color: '#0077b6',
      fillColor: ['match', ['coalesce', ['get', 'FLD_ZONE'], ''], 'AE', '#1d4ed8', 'VE', '#7c3aed', 'X', '#8ecae6', 'A', '#2563eb', '#5dade2'],
      fillOpacity: .22,
      focus: { center: [-76.7, 39.05], zoom: 8.1 },
      minZoom: 7,
      outFields: ['OBJECTID', 'DFIRM_ID', 'FLD_ZONE', 'ZONE_SUBTY', 'SFHA_TF', 'STATIC_BFE', 'V_DATUM', 'EFFECTIVE_DATE'],
      titleFields: ['FLD_ZONE', 'DFIRM_ID'],
      facts: [['Flood zone', 'FLD_ZONE'], ['Zone subtype', 'ZONE_SUBTY'], ['Special flood hazard area', 'SFHA_TF'], ['Base flood elevation', 'STATIC_BFE'], ['Vertical datum', 'V_DATUM'], ['Effective date', 'EFFECTIVE_DATE']],
    },
    {
      id: 'md-stream-gauges',
      name: 'MD stream gauges',
      description: 'NOAA stream-gauge points for observed water conditions',
      category: 'Water architecture',
      tags: ['water', 'stream gauge', 'monitoring', 'hydrology', 'noaa'],
      service: 'https://mdgeodata.md.gov/imap/rest/services/Hydrology/MD_Gauges/FeatureServer/1',
      sourceUrl: 'https://mdgeodata.md.gov/imap/rest/services/Hydrology/MD_Gauges/FeatureServer',
      sourceLabel: 'Maryland iMAP Stream Gauges',
      attribution: 'Maryland iMAP / NOAA',
      geometry: 'point',
      color: '#219ebc',
      focus: { center: [-76.7, 39.05], zoom: 8.4 },
      minZoom: 7,
      outFields: ['OBJECTID', 'GaugeLID', 'Location', 'Waterbody', 'State', 'URL'],
      titleFields: ['Waterbody', 'Location', 'GaugeLID'],
      facts: [['Gauge ID', 'GaugeLID'], ['Location', 'Location'], ['Waterbody', 'Waterbody'], ['State', 'State'], ['Official link', 'URL']],
    },
    {
      id: 'md-blue-infrastructure',
      name: 'MD blue infrastructure ranks',
      description: 'Aquatic and near-shore habitat ranking for water-sensitive siting context',
      category: 'Water architecture',
      tags: ['water', 'blue infrastructure', 'habitat', 'ecology', 'shoreline'],
      service: 'https://mdgeodata.md.gov/imap/rest/services/Hydrology/MD_BlueInfrastructure/FeatureServer/0',
      sourceUrl: 'https://mdgeodata.md.gov/imap/rest/services/Hydrology/MD_BlueInfrastructure/FeatureServer',
      sourceLabel: 'Maryland iMAP Blue Infrastructure',
      attribution: 'Maryland iMAP / DNR',
      geometry: 'polygon',
      color: '#2a9d8f',
      fillColor: ['interpolate', ['linear'], ['coalesce', ['get', 'TOTAL_RANK'], 0], 0, '#d9f0f0', 4, '#8fd3d1', 8, '#4db6ac', 12, '#1f8f82'],
      fillOpacity: .26,
      focus: { center: [-76.4, 38.9], zoom: 8.0 },
      minZoom: 7,
      outFields: ['OBJECTID', 'BI_Numbers', 'TOTAL_RANK', 'T_aquatic', 'T_land', 'FISH_BLKG', 'POLLTN_Rnk', 'PRCNT_STRD'],
      titleFields: ['BI_Numbers', 'OBJECTID'],
      facts: [['Blue infrastructure cells', 'BI_Numbers'], ['Total rank', 'TOTAL_RANK'], ['Aquatic rank', 'T_aquatic'], ['Land rank', 'T_land'], ['Fish blockage', 'FISH_BLKG'], ['Pollution point', 'POLLTN_Rnk'], ['Percent structured shore', 'PRCNT_STRD']],
    },
    {
      id: 'power-interchanges',
      name: 'Power imports / exports',
      description: 'Transmission corridors crossing the Maryland border and statewide net interchange',
      category: 'Electricity interchange',
      tags: ['Electric grid', 'Imports', 'Exports', 'Transmission'],
      staticDataUrl: '/datacenters/data/power-interchanges.json',
      sourceUrl: '/datacenters/data/power-interchanges.json',
      sourceLabel: 'Derived official Maryland transmission-crossing inventory',
      attribution: 'HIFLD, Maryland iMAP, EIA, PJM',
      geometry: 'point',
      pointSymbol: 'interchange-arrow',
      color: '#69d2ff',
      focus: { center: [-76.75, 39.05], zoom: 7.2 },
      minZoom: 0,
      statusOffText: 'Off · 78 border corridors / 107 line crossings',
      scaleFields: [['estimated_average_interchange_mw', 'Estimated crossing average MW'], ['line_count', 'Co-located line count'], ['statewide_average_net_import_mw', 'Statewide average net import (MW)']],
      defaultSizeBy: 'estimated_average_interchange_mw',
      titleFields: ['name', 'crossing_id'],
      facts: [
        ['Crossing ID', 'crossing_id'],
        ['Neighboring jurisdiction', 'neighboring_jurisdiction'],
        ['Co-located transmission lines', 'line_count'],
        ['Line IDs', 'line_ids'],
        ['Voltage', 'voltage_kv', ' kV'],
        ['Voltage classes', 'voltage_classes'],
        ['Owners', 'owners'],
        ['Named substations', 'named_substations'],
        ['Physical capability', 'flow_capability'],
        ['Per-line public measurement', 'line_flow_measurement'],
        ['Maryland statewide direction', 'statewide_flow_direction'],
        ['Estimated crossing average', 'estimated_average_interchange_mw', ' MW'],
        ['Estimated share of statewide flow', 'estimated_interchange_share_percent', '%'],
        ['Estimate basis', 'estimated_interchange_basis'],
        ['2024 statewide net import', 'statewide_net_import_mwh', ' MWh'],
        ['2024 statewide average net import', 'statewide_average_net_import_mw', ' MW'],
      ],
      additionalSources: [
        ['HIFLD transmission geometry', 'https://www.arcgis.com/home/item.html?id=d4090758322c4d32a4cd002ffaa0aa12'],
        ['Maryland iMAP state boundary', 'https://mdgeodata.md.gov/imap/rest/services/Boundaries/MD_PoliticalBoundaries/FeatureServer/0'],
        ['U.S. Census Bureau TIGERweb state boundaries', 'https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/0'],
        ['EIA Maryland State Electricity Profile table 10', 'https://www.eia.gov/electricity/state/maryland/state_tables.php'],
        ['PJM 2025 Maryland and D.C. infrastructure report', 'https://www.pjm.com/-/media/DotCom/library/reports-notices/state-specific-reports/2025/maryland-dc.pdf'],
      ],
    },
    {
      id: 'county-power-estimates',
      name: 'County power estimates',
      description: 'Derived residential electricity demand estimates by Maryland county equivalent',
      category: 'Power demand estimates',
      tags: ['Residential', 'Electric demand', 'Power estimates', 'County', 'ACS', 'EIA'],
      staticDataUrl: '/datacenters/data/power-estimates.json',
      sourceUrl: '/datacenters/data/power-estimates.json',
      sourceLabel: 'Derived Maryland county residential electricity estimates',
      attribution: 'EIA, U.S. Census Bureau, Census Reporter',
      geometry: 'polygon',
      color: '#facc15',
      fillColor: [
        'interpolate', ['linear'], ['coalesce', ['get', 'estimated_residential_average_mw'], 0],
        0, '#0f2f5f',
        40, '#1d4ed8',
        120, '#06b6d4',
        250, '#facc15',
        450, '#f97316',
      ],
      fillOpacity: .42,
      lineColor: '#fff2a8',
      lineWidth: ['interpolate', ['linear'], ['zoom'], 6, .55, 11, 1.6],
      lineOpacity: .82,
      focus: { center: [-76.75, 39.05], zoom: 7.2 },
      minZoom: 0,
      statusOffText: 'Off · 24 county residential-demand estimates',
      titleFields: ['county', 'geoid'],
      facts: [
        ['County', 'county'],
        ['Source year', 'source_year'],
        ['Estimated residential average', 'estimated_residential_average_mw', ' MW'],
        ['Estimated residential annual use', 'estimated_residential_annual_mwh', ' MWh'],
        ['Estimated residential monthly use', 'estimated_residential_monthly_mwh', ' MWh'],
        ['Occupied housing units', 'occupied_housing_units'],
        ['Estimated residential customers', 'estimated_residential_customers'],
        ['Share of statewide estimate', 'estimated_share_percent', '%'],
        ['Statewide residential price', 'statewide_residential_price_cents_kwh', '¢/kWh'],
        ['Estimate basis', 'estimate_basis'],
      ],
      additionalSources: [
        ['EIA Maryland residential retail electricity record', 'https://api.eia.gov/v2/electricity/retail-sales/data/?api_key=DEMO_KEY&frequency=annual&data[0]=price&data[1]=revenue&data[2]=sales&data[3]=customers&facets[stateid][]=MD&facets[sectorid][]=RES&start=2024&end=2024'],
        ['Census Reporter ACS table B25003', 'https://api.censusreporter.org/1.0/data/show/latest?table_ids=B25003&geo_ids=050%7C04000US24'],
        ['U.S. Census Bureau TIGERweb county boundaries', 'https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/1'],
      ],
    },
    {
      id: 'md-imap-substations',
      name: 'MD iMAP substations',
      description: 'Delmarva Peninsula substations',
      service: 'https://mdgeodata.md.gov/appdata/rest/services/CoastalAtlas/MD_PowerTransmission/MapServer/0',
      sourceUrl: 'https://mdgeodata.md.gov/appdata/rest/services/CoastalAtlas/MD_PowerTransmission/MapServer',
      sourceLabel: 'Maryland iMAP / DNR Power Transmission',
      attribution: 'Maryland iMAP / DNR',
      geometry: 'point',
      color: '#f4d35e',
      scaleFields: [['TRNFM_VOLT', 'Transformer voltage']],
      focus: { center: [-75.1, 38.4], zoom: 11 },
      minZoom: 8,
      outFields: ['OBJECTID_1', 'TRNFM_VOLT', 'A_NAME', 'A_NAME2'],
      titleFields: ['A_NAME', 'A_NAME2', 'OBJECTID_1'],
      facts: [['Substation', 'A_NAME'], ['Alternate name', 'A_NAME2'], ['Transformer voltage', 'TRNFM_VOLT'], ['Object ID', 'OBJECTID_1']],
    },
    {
      id: 'md-imap-transmission-lines',
      name: 'MD iMAP transmission',
      description: 'Delmarva lines, voltage, and proposed MAPP route',
      service: 'https://mdgeodata.md.gov/appdata/rest/services/CoastalAtlas/MD_PowerTransmission/MapServer/1',
      sourceUrl: 'https://mdgeodata.md.gov/appdata/rest/services/CoastalAtlas/MD_PowerTransmission/MapServer',
      sourceLabel: 'Maryland iMAP / DNR Power Transmission',
      attribution: 'Maryland iMAP / DNR',
      geometry: 'line',
      color: '#f4d35e',
      lineColor: MD_IMAP_TRANSMISSION_COLORS,
      lineColorThemes: transmissionLineThemes('Voltage_kV', MD_IMAP_TRANSMISSION_COLORS),
      lineWidthFields: [['Voltage_kV', 'Voltage class / kV proxy']],
      focus: { center: [-75.65, 38.95], zoom: 8.2 },
      minZoom: 7,
      outFields: ['OBJECTID_1', 'Id', 'Voltage_kV', 'Status', 'Name', 'Undergrnd'],
      titleFields: ['Name', 'Id', 'OBJECTID_1'],
      facts: [['Line name', 'Name'], ['Voltage (kV)', 'Voltage_kV'], ['Status', 'Status'], ['Underground', 'Undergrnd'], ['Line ID', 'Id']],
    },
    {
      id: 'bge-generation-hosting',
      name: 'BGE generation hosting',
      description: 'Estimated remaining DER capacity',
      services: [
        [14, 'https://services3.arcgis.com/agWTKEK7X5K1Bx7o/arcgis/rest/services/BGE_HOSTING_CAPACITY_AGOL/FeatureServer/37'],
        [10, 'https://services3.arcgis.com/agWTKEK7X5K1Bx7o/arcgis/rest/services/BGE_HOSTING_CAPACITY_AGOL/FeatureServer/38'],
        [0, 'https://services3.arcgis.com/agWTKEK7X5K1Bx7o/arcgis/rest/services/BGE_HOSTING_CAPACITY_AGOL/FeatureServer/39'],
      ],
      sourceUrl: 'https://www.arcgis.com/home/item.html?id=5ed8bfaa2e85430b8364d2d615151cfd',
      sourceLabel: 'Baltimore Gas and Electric Hosting Capacity',
      attribution: 'BGE',
      geometry: 'polygon',
      color: '#65c466',
      fillColor: ['step', ['coalesce', ['get', 'Sum_Hosting_Capacity_Remaining_kW'], 0], '#d73027', 250, '#f46d43', 3000, '#fee08b', 6000, '#a6d96a', 9000, '#1a9850'],
      fillOpacity: .56,
      lineColor: '#343434',
      lineWidth: ['interpolate', ['linear'], ['zoom'], 7, 0.4, 14, 0.8],
      lineOpacity: .72,
      focus: { center: [-76.65, 39.25], zoom: 8.6 },
      minZoom: 7,
      maxFeatures: 1000,
      outFields: ['OBJECTID', 'MAP_NAME', 'Count_', 'Sum_DER_Installed_and_approved_kW', 'Sum_Hosting_Capacity_Remaining_kW'],
      titleFields: ['MAP_NAME', 'OBJECTID'],
      facts: [['Map area', 'MAP_NAME'], ['Remaining generation hosting (kW)', 'Sum_Hosting_Capacity_Remaining_kW'], ['Installed and approved DER (kW)', 'Sum_DER_Installed_and_approved_kW'], ['Facilities represented', 'Count_']],
    },
    {
      id: 'bge-load-capacity',
      name: 'BGE load capacity',
      description: 'Estimated capacity for new electric load',
      services: [
        [14, 'https://services3.arcgis.com/agWTKEK7X5K1Bx7o/arcgis/rest/services/BGE_EV_Load_Capacity/FeatureServer/1'],
        [10, 'https://services3.arcgis.com/agWTKEK7X5K1Bx7o/arcgis/rest/services/BGE_EV_Load_Capacity/FeatureServer/2'],
        [0, 'https://services3.arcgis.com/agWTKEK7X5K1Bx7o/arcgis/rest/services/BGE_EV_Load_Capacity/FeatureServer/3'],
      ],
      sourceUrl: 'https://www.arcgis.com/home/item.html?id=3388d9b757a64147b84bd5ee8c3a7e1a',
      sourceLabel: 'Baltimore Gas and Electric EV Load Capacity',
      attribution: 'BGE',
      geometry: 'polygon',
      color: '#00b4d8',
      fillColor: ['step', ['coalesce', ['get', 'Max_FEEDER_AVAIL_CAP_MW_MIN'], 0], '#d73027', .77, '#f46d43', 1.83, '#f5f500', 2.93, '#94f700', 4.21, '#00f500'],
      fillOpacity: .56,
      lineColor: '#6e6e6e',
      lineWidth: ['interpolate', ['linear'], ['zoom'], 7, 0.4, 14, 0.8],
      lineOpacity: .72,
      focus: { center: [-76.65, 39.25], zoom: 8.6 },
      minZoom: 7,
      maxFeatures: 1000,
      outFields: ['OBJECTID_1', 'MAP_NAME', 'Count_', 'Sum_FEEDER_AVAIL_CAP_MW_MIN', 'Min_FEEDER_AVAIL_CAP_MW_MIN', 'Max_FEEDER_AVAIL_CAP_MW_MIN', 'Sum_SUBSTATION_AVAIL_CAP_MW_MIN'],
      titleFields: ['MAP_NAME', 'OBJECTID_1'],
      facts: [['Map area', 'MAP_NAME'], ['Feeder capacity sum (MW)', 'Sum_FEEDER_AVAIL_CAP_MW_MIN'], ['Minimum feeder capacity (MW)', 'Min_FEEDER_AVAIL_CAP_MW_MIN'], ['Maximum feeder capacity (MW)', 'Max_FEEDER_AVAIL_CAP_MW_MIN'], ['Substation capacity sum (MW)', 'Sum_SUBSTATION_AVAIL_CAP_MW_MIN']],
    },
    {
      id: 'pepco-generation-hosting',
      name: 'Pepco generation hosting',
      description: 'Maryland feeder DER capacity',
      service: 'https://services3.arcgis.com/agWTKEK7X5K1Bx7o/arcgis/rest/services/PHI_Hosting_Capacity_Public/FeatureServer/0',
      sourceUrl: 'https://www.pepco.com/smart-energy/my-green-power-connection/developers-contractors/technical-consideration/hosting-capacity-map',
      sourceLabel: 'Pepco Hosting Capacity',
      attribution: 'Pepco',
      where: "Region = 'Pepco' AND State = 'MD'",
      geometry: 'line',
      color: '#74c69d',
      lineColor: ['step', ['coalesce', ['get', 'Allowable_PV_kW'], 0], '#d73027', 250, '#f46d43', 1000, '#fee08b', 3000, '#a6d96a', 6000, '#1a9850'],
      lineWidthFields: [['Allowable_PV_kW', 'Allowable PV (kW)'], ['Total_Active_Gen_kW', 'Active generation (kW)'], ['Total_Pending_Gen_kW', 'Pending generation (kW)']],
      focus: { center: [-76.98, 39.02], zoom: 9.5 },
      minZoom: 9,
      outFields: ['Region', 'State', 'Substation', 'FeederID', 'Allowable_PV_kW', 'Voltage', 'Total_Active_Gen_kW', 'Total_Pending_Gen_kW', 'UpdateDate'],
      titleFields: ['FeederID', 'Substation'],
      facts: [['Feeder', 'FeederID'], ['Substation', 'Substation'], ['Allowable PV (kW)', 'Allowable_PV_kW'], ['Voltage (kV)', 'Voltage'], ['Active generation (kW)', 'Total_Active_Gen_kW'], ['Pending generation (kW)', 'Total_Pending_Gen_kW'], ['Updated', 'UpdateDate']],
    },
    {
      id: 'pepco-load-capacity',
      name: 'Pepco load capacity',
      description: 'Maryland feeder capacity for new load',
      service: 'https://services3.arcgis.com/agWTKEK7X5K1Bx7o/arcgis/rest/services/PHI_EV_Load_Serving_Capacity/FeatureServer/0',
      sourceUrl: 'https://www.pepco.com/smart-energy/innovation-technology/electric-vehicles/ev-load-capacity-map',
      sourceLabel: 'Pepco Load Serving Capacity',
      attribution: 'Pepco',
      where: "Region = 'Pepco' AND State = 'MD'",
      geometry: 'line',
      color: '#00b4d8',
      lineColor: ['step', ['coalesce', ['get', 'Capacity_MW'], 0], '#d73027', .25, '#f46d43', 1, '#fee08b', 2, '#a6d96a', 4, '#1a9850'],
      lineWidthFields: [['Capacity_MW', 'Available load capacity (MW)'], ['Feeder_Capacity_MW', 'Feeder capacity (MW)'], ['Transformer_or_Network_Capacity_MW', 'Transformer / network capacity (MW)'], ['Substation_Capacity_MW', 'Substation capacity (MW)'], ['Voltage_kV', 'Voltage (kV)']],
      focus: { center: [-76.98, 39.02], zoom: 9.5 },
      minZoom: 9,
      outFields: ['FEEDERID', 'Feeder', 'Voltage_kV', 'Capacity_MW', 'Region', 'State', 'District', 'Substation', 'Transformer', 'Feeder_Capacity_MW', 'Transformer_or_Network_Capacity_MW', 'Substation_Capacity_MW', 'UpdateDate'],
      titleFields: ['Feeder', 'FEEDERID', 'Substation'],
      facts: [['Feeder', 'Feeder'], ['Substation', 'Substation'], ['Available load capacity (MW)', 'Capacity_MW'], ['Feeder capacity (MW)', 'Feeder_Capacity_MW'], ['Transformer capacity (MW)', 'Transformer_or_Network_Capacity_MW'], ['Substation capacity (MW)', 'Substation_Capacity_MW'], ['Voltage (kV)', 'Voltage_kV'], ['Updated', 'UpdateDate']],
    },
    {
      id: 'delmarva-generation-hosting',
      name: 'Delmarva generation hosting',
      description: 'Maryland feeder DER capacity',
      service: 'https://services3.arcgis.com/agWTKEK7X5K1Bx7o/arcgis/rest/services/PHI_Hosting_Capacity_Public/FeatureServer/2',
      sourceUrl: 'https://www.delmarva.com/smart-energy/my-green-power-connection/developers-contractors/technical-consideration/hosting-capacity-map',
      sourceLabel: 'Delmarva Power Hosting Capacity',
      attribution: 'Delmarva Power',
      where: "Region = 'Delmarva' AND State = 'MD'",
      geometry: 'line',
      color: '#95d5b2',
      lineColor: ['step', ['coalesce', ['get', 'Allowable_PV_kW'], 0], '#d73027', 250, '#f46d43', 1000, '#fee08b', 3000, '#a6d96a', 6000, '#1a9850'],
      lineWidthFields: [['Allowable_PV_kW', 'Allowable PV (kW)'], ['Total_Active_Gen_kW', 'Active generation (kW)'], ['Total_Pending_Gen_kW', 'Pending generation (kW)']],
      focus: { center: [-75.75, 38.75], zoom: 8.8 },
      minZoom: 8,
      outFields: ['Region', 'State', 'Substation', 'FeederID', 'Allowable_PV_kW', 'Voltage', 'Total_Active_Gen_kW', 'Total_Pending_Gen_kW', 'UpdateDate'],
      titleFields: ['FeederID', 'Substation'],
      facts: [['Feeder', 'FeederID'], ['Substation', 'Substation'], ['Allowable PV (kW)', 'Allowable_PV_kW'], ['Voltage (kV)', 'Voltage'], ['Active generation (kW)', 'Total_Active_Gen_kW'], ['Pending generation (kW)', 'Total_Pending_Gen_kW'], ['Updated', 'UpdateDate']],
    },
    {
      id: 'delmarva-load-capacity',
      name: 'Delmarva load capacity',
      description: 'Maryland feeder capacity for new load',
      service: 'https://services3.arcgis.com/agWTKEK7X5K1Bx7o/arcgis/rest/services/PHI_EV_Load_Serving_Capacity/FeatureServer/0',
      sourceUrl: 'https://www.delmarva.com/smart-energy/innovation-technology/ev-load-capacity-map',
      sourceLabel: 'Delmarva Power Load Serving Capacity',
      attribution: 'Delmarva Power',
      where: "Region = 'DPL' AND State = 'MD'",
      geometry: 'line',
      color: '#48cae4',
      lineColor: ['step', ['coalesce', ['get', 'Capacity_MW'], 0], '#d73027', .25, '#f46d43', 1, '#fee08b', 2, '#a6d96a', 4, '#1a9850'],
      lineWidthFields: [['Capacity_MW', 'Available load capacity (MW)'], ['Feeder_Capacity_MW', 'Feeder capacity (MW)'], ['Transformer_or_Network_Capacity_MW', 'Transformer / network capacity (MW)'], ['Substation_Capacity_MW', 'Substation capacity (MW)'], ['Voltage_kV', 'Voltage (kV)']],
      focus: { center: [-75.75, 38.75], zoom: 8.8 },
      minZoom: 8,
      outFields: ['FEEDERID', 'Feeder', 'Voltage_kV', 'Capacity_MW', 'Region', 'State', 'District', 'Substation', 'Transformer', 'Feeder_Capacity_MW', 'Transformer_or_Network_Capacity_MW', 'Substation_Capacity_MW', 'UpdateDate'],
      titleFields: ['Feeder', 'FEEDERID', 'Substation'],
      facts: [['Feeder', 'Feeder'], ['Substation', 'Substation'], ['Available load capacity (MW)', 'Capacity_MW'], ['Feeder capacity (MW)', 'Feeder_Capacity_MW'], ['Transformer capacity (MW)', 'Transformer_or_Network_Capacity_MW'], ['Substation capacity (MW)', 'Substation_Capacity_MW'], ['Voltage (kV)', 'Voltage_kV'], ['Updated', 'UpdateDate']],
    },
    {
      id: 'potomac-edison-generation-hosting',
      name: 'Potomac Edison generation hosting',
      description: 'Transformer solar accommodation limits',
      service: 'https://services9.arcgis.com/QhIvHlqYDjdoPWZG/arcgis/rest/services/Full_Map_xfmr_MD/FeatureServer/0',
      sourceUrl: 'https://firstenergycorp.maps.arcgis.com/apps/webappviewer/index.html?id=fe8d1f209a944b4c92ee3acb016cc8d4',
      sourceLabel: 'Potomac Edison Hosting Capacity Map',
      attribution: 'Potomac Edison',
      geometry: 'point',
      color: '#80ed99',
      scaleFields: [['RemainNum', 'Remaining generation capacity']],
      focus: { center: [-78.15, 39.45], zoom: 8.6 },
      minZoom: 8,
      outFields: ['FID', 'RemainNum', 'Remaining'],
      titleFields: ['Remaining', 'FID'],
      facts: [['Remaining solar accommodation', 'Remaining'], ['Remaining capacity value', 'RemainNum'], ['Feature ID', 'FID']],
    },
    {
      id: 'smeco-generation-hosting',
      name: 'SMECO generation hosting',
      description: 'Southern Maryland 15 kV feeder capacity',
      service: 'https://services3.arcgis.com/x1bcT7boxsEGsJym/arcgis/rest/services/SMECO_2024_CIRCUITS_101024/FeatureServer/1',
      sourceUrl: 'https://www.arcgis.com/home/item.html?id=3a9b5e720dac470b9634e9c7cf9f922e',
      sourceLabel: 'SMECO Hosting Capacity Map',
      attribution: 'SMECO',
      geometry: 'line',
      color: '#57cc99',
      lineColor: ['step', ['coalesce', ['get', 'MaxCapacity'], 0], '#d73027', .25, '#f46d43', .5, '#fee08b', 1, '#a6d96a', 2, '#1a9850'],
      lineWidthFields: [['MaxCapacity', 'Published maximum capacity']],
      focus: { center: [-76.62, 38.45], zoom: 8.8 },
      minZoom: 8,
      outFields: ['OBJECTID', 'SubId', 'FeederId', 'SectId', 'MaxCapacity'],
      titleFields: ['FeederId', 'SubId', 'OBJECTID'],
      facts: [['Substation ID', 'SubId'], ['Feeder ID', 'FeederId'], ['Section ID', 'SectId'], ['Published maximum capacity', 'MaxCapacity']],
    },
    {
      id: 'electric-transmission-lines',
      name: 'Electric transmission lines (2024)',
      description: 'Public U.S. network; archived after its 2024 update',
      service: 'https://services2.arcgis.com/FiaPA4ga0iQKduv3/arcgis/rest/services/US_Electric_Power_Transmission_Lines/FeatureServer/0',
      sourceUrl: 'https://www.arcgis.com/home/item.html?id=d4090758322c4d32a4cd002ffaa0aa12',
      sourceLabel: 'U.S. Electric Power Transmission Lines (HIFLD / U.S. Government)',
      geometry: 'line',
      color: '#ff6b35',
      focus: { center: [-76.75, 39.05], zoom: 7.4 },
      lineColor: HIFLD_TRANSMISSION_COLORS,
      lineColorThemes: transmissionLineThemes('VOLTAGE', HIFLD_TRANSMISSION_COLORS),
      lineWidthFields: [['VOLT_CLASS', 'Voltage class'], ['VOLTAGE', 'Voltage (kV)']],
      colorLegend: {
        field: 'VOLT_CLASS',
        label: 'Voltage class',
        entries: TRANSMISSION_VOLTAGE_COLORS,
        fallback: { label: 'Other / unknown', color: '#aab9c5' },
      },
      minZoom: 7,
      outFields: ['ID', 'TYPE', 'STATUS', 'OWNER', 'VOLTAGE', 'VOLT_CLASS', 'INFERRED', 'SUB_1', 'SUB_2', 'SOURCE', 'SOURCEDATE', 'VAL_METHOD', 'VAL_DATE'],
      titleFields: ['ID', 'OWNER'],
      facts: [['Line ID', 'ID'], ['Type', 'TYPE'], ['Status', 'STATUS'], ['Owner', 'OWNER'], ['Voltage', 'VOLTAGE'], ['Voltage class', 'VOLT_CLASS'], ['Inferred attributes', 'INFERRED'], ['Origin', 'SUB_1'], ['Destination', 'SUB_2'], ['Source', 'SOURCE'], ['Source date', 'SOURCEDATE'], ['Validation method', 'VAL_METHOD'], ['Validation date', 'VAL_DATE']],
    },
  ];
  const BASEMAP_STYLES = {
    collective: 'https://tiles.openfreemap.org/styles/liberty',
    dark: 'https://tiles.openfreemap.org/styles/dark',
    fiord: 'https://tiles.openfreemap.org/styles/fiord',
    positron: 'https://tiles.openfreemap.org/styles/positron',
    bright: 'https://tiles.openfreemap.org/styles/bright',
    liberty: 'https://tiles.openfreemap.org/styles/liberty',
  };
  const UI_STATE_STORAGE_KEY = 'codecollective.datacenters.ui-state.v1';
  const ENERGY_SOURCES = {
    SUN: { label: 'Solar', light: '#69c7ff', color: '#167fc1', dark: '#064a7d' },
    BIT: { label: 'Coal', light: '#59616a', color: '#20262c', dark: '#050708' },
    SUB: { label: 'Coal', light: '#59616a', color: '#20262c', dark: '#050708' },
    LIG: { label: 'Coal', light: '#59616a', color: '#20262c', dark: '#050708' },
    WC: { label: 'Coal', light: '#59616a', color: '#20262c', dark: '#050708' },
    RC: { label: 'Coal', light: '#59616a', color: '#20262c', dark: '#050708' },
    NG: { label: 'Natural gas', light: '#c58a62', color: '#865033', dark: '#4a281b' },
    PG: { label: 'Propane gas', light: '#c58a62', color: '#865033', dark: '#4a281b' },
    DFO: { label: 'Oil / diesel', light: '#ffb454', color: '#c76522', dark: '#743010' },
    RFO: { label: 'Oil / diesel', light: '#ffb454', color: '#c76522', dark: '#743010' },
    WAT: { label: 'Hydroelectric', light: '#70ebef', color: '#16a5b5', dark: '#075f74' },
    WND: { label: 'Wind', light: '#ffffff', color: '#b9c4cc', dark: '#53606a' },
    NUC: { label: 'Nuclear', light: '#9affbd', color: '#25c965', dark: '#08732e' },
    MWH: { label: 'Battery storage', light: '#d7b4ff', color: '#8d65ca', dark: '#4c317e' },
    LFG: { label: 'Landfill gas', light: '#b7cf70', color: '#718e39', dark: '#3d5520' },
    MSW: { label: 'Municipal waste', light: '#f4d06f', color: '#b38b25', dark: '#695012' },
    MSB: { label: 'Municipal waste', light: '#f4d06f', color: '#b38b25', dark: '#695012' },
    MSN: { label: 'Municipal waste', light: '#f4d06f', color: '#b38b25', dark: '#695012' },
    OBG: { label: 'Biomass', light: '#d0c779', color: '#8b8436', dark: '#514c1e' },
    WDS: { label: 'Biomass', light: '#d0c779', color: '#8b8436', dark: '#514c1e' },
    UNKNOWN: { label: 'Undisclosed', light: '#aab9c5', color: '#657887', dark: '#344550' },
  };
  const LIFECYCLE_COLORS = {
    operating: { label: 'Existing / operating', light: '#8ae7bc', color: '#208a5d', dark: '#0d5136' },
    development: { label: 'Permitted / developing', light: '#93d8ff', color: '#1d84c7', dark: '#0e4469' },
    proposal: { label: 'Proposed / planned', light: '#ffd98a', color: '#d9911f', dark: '#7d4e0c' },
    paused: { label: 'Paused / blocked', light: '#ffaaa5', color: '#d24a43', dark: '#6d1f1b' },
    unknown: { label: 'Unknown', light: '#c6d0d8', color: '#738392', dark: '#384654' },
  };
  const PLANNED_UNCONTESTED_COLOR = {
    label: 'Planned / unbuilt / uncontested',
    light: '#fffbd1',
    color: '#fff15f',
    dark: '#9a5e00',
  };
  const SENTIMENT_COLORS = {
    supportive: { label: 'Supportive', light: '#8de6b4', color: '#24995f', dark: '#0f5634' },
    mixed: { label: 'Mixed / unclear', light: '#e8d98d', color: '#ae8f22', dark: '#655111' },
    opposed: { label: 'Opposed', light: '#ffaeac', color: '#d14643', dark: '#741d1c' },
    unknown: { label: 'Insufficient evidence', light: '#cbd6df', color: '#708191', dark: '#374655' },
  };
  const PLANT_TECH_COLORS = {
    nuclear: { label: 'Nuclear', light: '#9affbd', color: '#25c965', dark: '#08732e' },
    gas: { label: 'Combustion / gas', light: '#d2ad90', color: '#8e5a38', dark: '#4d2e1a' },
    solar: { label: 'Solar', light: '#93d7ff', color: '#1d89cf', dark: '#0d4770' },
    battery: { label: 'Battery / storage', light: '#ddc2ff', color: '#8b63c9', dark: '#4b3375' },
    hydro: { label: 'Hydroelectric', light: '#7cecf4', color: '#16a5b5', dark: '#085d69' },
    wind: { label: 'Wind', light: '#ffffff', color: '#b9c4cc', dark: '#53606a' },
    coal: { label: 'Coal', light: '#848b93', color: '#373d43', dark: '#101316' },
    waste: { label: 'Waste / biomass', light: '#dfd38f', color: '#9a8d38', dark: '#574f1f' },
    other: { label: 'Other technology', light: '#c4d1db', color: '#70808f', dark: '#354350' },
  };
  const PLANT_SCALE_COLORS = {
    peaker: { label: 'Peaker / small plant', light: '#ffd3a7', color: '#d97e1f', dark: '#7f470d' },
    regional: { label: 'Regional plant', light: '#a9d7ff', color: '#2f8fd4', dark: '#114c77' },
    utility: { label: 'Utility-scale plant', light: '#a7ecc3', color: '#2caa6d', dark: '#12613c' },
    mega: { label: 'Very large plant', light: '#f4b4ff', color: '#bb58cb', dark: '#672974' },
    unknown: { label: 'Unknown size', light: '#c6d0d8', color: '#738392', dark: '#384654' },
  };
  const BRIGHT_BOLT_SOURCE_COLORS = {
    SUN: '#4db8ff',
    BIT: '#6f7a86',
    SUB: '#6f7a86',
    LIG: '#6f7a86',
    WC: '#6f7a86',
    RC: '#6f7a86',
    NG: '#f3c572',
    PG: '#f3c572',
    DFO: '#d5a56d',
    RFO: '#d5a56d',
    WAT: '#52e3ff',
    WND: '#dce6ec',
    NUC: '#52ef82',
    MWH: '#c5b2ff',
    LFG: '#bedf67',
    MSW: '#f2de74',
    MSB: '#f2de74',
    MSN: '#f2de74',
    OBG: '#d8cb6d',
    WDS: '#d8cb6d',
    UNKNOWN: '#ffd84f',
  };

  const escapeHtml = (value) => String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');

  const known = (value, suffix = '') => value === null || value === undefined || value === ''
    ? '<span class="dc-unknown">Not publicly disclosed</span>'
    : `${escapeHtml(value)}${suffix}`;

  const number = (value, digits = 0) => Number(value).toLocaleString('en-US', {
    maximumFractionDigits: digits,
  });

  function markerSourceCodes(record) {
    if (record.record_type === 'power_plant') {
      const codes = record.generation_fuel_codes?.length
        ? record.generation_fuel_codes
        : record.energy_source_codes;
      return [...new Set(codes?.filter((code) => ENERGY_SOURCES[code]) || [])];
    }

    const codes = [];
    const onSite = String(record.on_site_generation_technology || '').toLowerCase();
    const gas = String(record.on_site_natural_gas_power_plant || '').toLowerCase();
    const backup = String(record.backup_generation_fuel || '').toLowerCase();
    if (onSite.includes('battery')) codes.push('MWH');
    if (gas.includes('natural gas') && !/not identified|not disclosed/.test(gas)) codes.push('NG');
    if (/diesel|fuel oil/.test(backup)) codes.push('DFO');
    return [...new Set(codes)];
  }

  function markerGradient(sourceCodes) {
    const sources = (sourceCodes.length ? sourceCodes : ['UNKNOWN'])
      .map((code) => ENERGY_SOURCES[code])
      .filter((source, index, all) => all.findIndex((candidate) => candidate.label === source.label) === index);
    const highlight = 'radial-gradient(circle at 30% 22%, rgba(255,255,255,.78) 0 7%, rgba(255,255,255,.2) 22%, transparent 48%)';
    if (sources.length === 1) {
      const source = sources[0];
      return `${highlight}, linear-gradient(145deg, ${source.light} 0%, ${source.color} 48%, ${source.dark} 100%)`;
    }
    const stops = sources.flatMap((source, index) => {
      const start = (index / sources.length) * 100;
      const end = ((index + 1) / sources.length) * 100;
      return `${source.color} ${start}% ${end}%`;
    }).join(', ');
    return `${highlight}, conic-gradient(from -35deg, ${stops})`;
  }

  function markerPalette(sourceCodes) {
    return (sourceCodes.length ? sourceCodes : ['UNKNOWN'])
      .map((code) => ENERGY_SOURCES[code] || ENERGY_SOURCES.UNKNOWN)
      .filter((source, index, all) => all.findIndex((candidate) => candidate.label === source.label) === index);
  }

  function classifySentiment(record) {
    if (record.public_sentiment_score == null) return 'unknown';
    if (record.public_sentiment_score > 0) return 'supportive';
    if (record.public_sentiment_score < 0) return 'opposed';
    return 'mixed';
  }

  function classifyPlantTechnology(record) {
    const technology = String(record.primary_technology || '').toLowerCase();
    if (!technology) return 'other';
    if (technology.includes('nuclear')) return 'nuclear';
    if (technology.includes('solar')) return 'solar';
    if (technology.includes('battery')) return 'battery';
    if (technology.includes('hydro')) return 'hydro';
    if (technology.includes('wind')) return 'wind';
    if (technology.includes('coal')) return 'coal';
    if (technology.includes('biomass') || technology.includes('landfill') || technology.includes('waste')) return 'waste';
    if (
      technology.includes('gas')
      || technology.includes('combustion')
      || technology.includes('steam')
      || technology.includes('turbine')
      || technology.includes('internal combustion')
      || technology.includes('combined cycle')
    ) return 'gas';
    return 'other';
  }

  function classifyPlantScale(record) {
    const capacity = Number(record.nameplate_capacity_mw);
    if (!Number.isFinite(capacity)) return 'unknown';
    if (capacity < 25) return 'peaker';
    if (capacity < 250) return 'regional';
    if (capacity < 1000) return 'utility';
    return 'mega';
  }

  function stylePaletteForRecord(record, attribute) {
    if (record.record_type === 'data_center') {
      if (isPlannedUncontestedDataCenter(record)) return [PLANNED_UNCONTESTED_COLOR];
      if (attribute === 'lifecycle') return [LIFECYCLE_COLORS[lifecycleStage(record)] || LIFECYCLE_COLORS.unknown];
      if (attribute === 'sentiment') return [SENTIMENT_COLORS[classifySentiment(record)]];
      return markerPalette(markerSourceCodes(record));
    }
    if (attribute === 'technology') return [PLANT_TECH_COLORS[classifyPlantTechnology(record)]];
    if (attribute === 'scale') return [PLANT_SCALE_COLORS[classifyPlantScale(record)]];
    return markerPalette(markerSourceCodes(record));
  }

  function iconFillForRecord(record, attribute) {
    const customColor = record.record_type === 'data_center' ? layerCustomColors.get('datacenters') : null;
    if (customColor) {
      return `radial-gradient(circle at 30% 22%, rgba(255,255,255,.78) 0 7%, rgba(255,255,255,.2) 22%, transparent 48%), linear-gradient(145deg, ${adjustHexColor(customColor, 1.28)} 0%, ${customColor} 48%, ${adjustHexColor(customColor, .58)} 100%)`;
    }
    const palette = stylePaletteForRecord(record, attribute);
    const highlight = 'radial-gradient(circle at 30% 22%, rgba(255,255,255,.78) 0 7%, rgba(255,255,255,.2) 22%, transparent 48%)';
    if (palette.length === 1) {
      const source = palette[0];
      return `${highlight}, linear-gradient(145deg, ${source.light} 0%, ${source.color} 48%, ${source.dark} 100%)`;
    }
    const stops = palette.flatMap((source, index) => {
      const start = (index / palette.length) * 100;
      const end = ((index + 1) / palette.length) * 100;
      return `${source.color} ${start}% ${end}%`;
    }).join(', ');
    return `${highlight}, conic-gradient(from -35deg, ${stops})`;
  }

  function outlineColorForRecord(record, attribute) {
    if (attribute === 'none') return '#ffffff';
    const palette = stylePaletteForRecord(record, attribute);
    return mixColors(palette.map((source) => hexToRgb(source.dark)));
  }

  function markerSourceLabel(sourceCodes) {
    const codes = sourceCodes.length ? sourceCodes : ['UNKNOWN'];
    return [...new Set(codes.map((code) => ENERGY_SOURCES[code].label))].join(' + ');
  }

  function hexToRgb(hex) {
    const normalized = hex.replace('#', '');
    const value = normalized.length === 3
      ? normalized.split('').map((part) => part + part).join('')
      : normalized;
    return {
      r: Number.parseInt(value.slice(0, 2), 16),
      g: Number.parseInt(value.slice(2, 4), 16),
      b: Number.parseInt(value.slice(4, 6), 16),
    };
  }

  function rgbToHex({ r, g, b }) {
    return `#${[r, g, b].map((value) => Math.max(0, Math.min(255, Math.round(value))).toString(16).padStart(2, '0')).join('')}`;
  }

  function rgbToRgbaString({ r, g, b }, alpha = 1) {
    return `rgba(${Math.round(r)}, ${Math.round(g)}, ${Math.round(b)}, ${alpha})`;
  }

  function normalizeVector3(vector) {
    const magnitude = Math.hypot(vector.x, vector.y, vector.z) || 1;
    return {
      x: vector.x / magnitude,
      y: vector.y / magnitude,
      z: vector.z / magnitude,
    };
  }

  function mixColors(colors) {
    const total = colors.reduce((sum, color) => ({
      r: sum.r + color.r,
      g: sum.g + color.g,
      b: sum.b + color.b,
    }), { r: 0, g: 0, b: 0 });
    return rgbToHex({
      r: total.r / colors.length,
      g: total.g / colors.length,
      b: total.b / colors.length,
    });
  }

  function adjustHexColor(hex, factor) {
    const { r, g, b } = hexToRgb(hex);
    return rgbToHex({ r: r * factor, g: g * factor, b: b * factor });
  }

  function energyColorForMarker(sourceCodes) {
    const palette = markerPalette(sourceCodes);
    return mixColors(palette.map((source) => hexToRgb(source.color)));
  }

  function markerAccentColor(record, attribute) {
    if (record.record_type === 'power_plant' && layerCustomColors.has('power-plants')) {
      return layerCustomColors.get('power-plants');
    }
    if (record.record_type === 'power_plant' && attribute === 'energy') {
      const codes = markerSourceCodes(record);
      const palette = (codes.length ? codes : ['UNKNOWN'])
        .map((code) => BRIGHT_BOLT_SOURCE_COLORS[code] || BRIGHT_BOLT_SOURCE_COLORS.UNKNOWN)
        .map(hexToRgb);
      return mixColors(palette);
    }
    const palette = stylePaletteForRecord(record, attribute);
    return mixColors(palette.map((source) => hexToRgb(source.color)));
  }

  const POINT_SCALE_LABELS = {
    acreage: 'Site acreage',
    backup_generator_capacity_mw: 'Backup generation capacity (MW)',
    capital_investment_usd: 'Capital investment (USD)',
    employees_committed: 'Committed jobs',
    generator_count: 'Generator count',
    nameplate_capacity_mw: 'Nameplate capacity (MW)',
    average_generation_mwh: 'Average generation / output (MWh)',
    planning_sustained_output_mw: 'Planning output · annual average (MW)',
    annual_capacity_factor: 'Annual capacity factor',
    estimated_power_draw_mw: 'Estimated power draw (MW)',
    projected_power_demand_mw: 'Projected demand · unbuilt facilities (MW)',
    reported_annual_energy_mwh: 'Reported annual energy (MWh)',
    reported_grid_demand_mw: 'Net draw · reported grid demand (MW)',
    reported_power_capacity_mw: 'Total draw · published envelope or projected demand (MW)',
    ups_capacity_mw: 'UPS power capacity (MW)',
    ups_energy_mwh: 'UPS energy capacity (MWh)',
  };
  const POINT_SCALE_EXCLUDED_FIELDS = new Set([
    'latitude', 'longitude', 'latitude_decimal_places', 'longitude_decimal_places',
    'eia_plant_code', 'generation_year', 'shared_coordinate_count',
    'aerial_frame_width_m', 'aerial_frame_height_m', 'public_sentiment_score',
    'net_generation_mwh',
  ]);

  function pointScaleLabel(field) {
    if (POINT_SCALE_LABELS[field]) return POINT_SCALE_LABELS[field];
    return field.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
      .replace(/\bMw\b/g, 'MW').replace(/\bMwh\b/g, 'MWh').replace(/\bUsd\b/g, 'USD');
  }

  function numericPointScaleOptions(records, configuredFields = []) {
    const fields = new Map(configuredFields);
    records.forEach((record) => Object.entries(record || {}).forEach(([field, value]) => {
      if (POINT_SCALE_EXCLUDED_FIELDS.has(field) || typeof value !== 'number' || !Number.isFinite(value)) return;
      if (!fields.has(field)) fields.set(field, pointScaleLabel(field));
    }));
    return [['none', 'Uniform size'], ...[...fields.entries()].sort((a, b) => a[1].localeCompare(b[1]))];
  }

  function dataCenterPointScaleOptions(records) {
    const reportedCount = (field) => records.filter((record) => {
      const value = record[field];
      return value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value));
    }).length;
    return numericPointScaleOptions(records, [
      ['projected_power_demand_mw', `Projected demand · unbuilt facilities (${reportedCount('projected_power_demand_mw')} projects)`],
      ['estimated_power_draw_mw', `Estimated power draw (${reportedCount('estimated_power_draw_mw')} values)`],
      ['reported_grid_demand_mw', `Net draw · reported grid demand (${reportedCount('reported_grid_demand_mw')} public values)`],
      ['reported_power_capacity_mw', `Total draw · published envelope or projected demand (${records.filter((record) => {
        const value = record.reported_power_capacity_mw ?? record.projected_power_demand_mw;
        return value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value));
      }).length} values)`],
    ]);
  }

  function pointScaleFactors(records, field) {
    const factors = new Map(records.map((record) => [record, 1]));
    if (!field || field === 'none') return factors;
    const powerPlantRecords = records.length > 0 && records.every((record) => record.record_type === 'power_plant');
    const sizeFloor = powerPlantRecords ? .18 : .65;
    const sizeCeiling = powerPlantRecords ? 2.3 : 2;
    const missingFactor = powerPlantRecords ? .18 : .55;
    const numericValue = (record) => {
      if (field === 'average_generation_mwh') return powerPlantAverageGeneration(record);
      const rawValue = field === 'reported_power_capacity_mw'
        ? record.reported_power_capacity_mw ?? record.projected_power_demand_mw
        : record[field];
      if (rawValue === null || rawValue === undefined || rawValue === '') return null;
      const value = Number(rawValue);
      return Number.isFinite(value) ? value : null;
    };
    const values = records
      .map(numericValue)
      .filter((value) => value !== null);
    if (!values.length) {
      records.forEach((record) => factors.set(record, .55));
      return factors;
    }
    const nonnegative = Math.min(...values) >= 0;
    const transform = (value) => nonnegative ? Math.log1p(value) : value;
    const transformed = values.map(transform);
    const minimum = Math.min(...transformed);
    const maximum = Math.max(...transformed);
    records.forEach((record) => {
      const value = numericValue(record);
      if (value === null) {
        factors.set(record, missingFactor);
        return;
      }
      const normalized = maximum === minimum ? .5 : (transform(value) - minimum) / (maximum - minimum);
      factors.set(record, sizeFloor + (Math.max(0, Math.min(1, normalized)) * (sizeCeiling - sizeFloor)));
    });
    return factors;
  }

  let powerPlantBoltLayer = null;

  function createShader(gl, type, source) {
    const shader = gl.createShader(type);
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (gl.getShaderParameter(shader, gl.COMPILE_STATUS)) return shader;
    const error = gl.getShaderInfoLog(shader) || 'shader compile failed';
    gl.deleteShader(shader);
    throw new Error(error);
  }

  function createProgram(gl, vertexSource, fragmentSource) {
    const vertexShader = createShader(gl, gl.VERTEX_SHADER, vertexSource);
    const fragmentShader = createShader(gl, gl.FRAGMENT_SHADER, fragmentSource);
    const program = gl.createProgram();
    gl.attachShader(program, vertexShader);
    gl.attachShader(program, fragmentShader);
    gl.linkProgram(program);
    gl.deleteShader(vertexShader);
    gl.deleteShader(fragmentShader);
    if (gl.getProgramParameter(program, gl.LINK_STATUS)) return program;
    const error = gl.getProgramInfoLog(program) || 'program link failed';
    gl.deleteProgram(program);
    throw new Error(error);
  }

  async function loadLightningBoltMesh() {
    const response = await fetch('/datacenters/models/lightning-bolt.gltf');
    if (!response.ok) throw new Error(`Lightning bolt model request failed (${response.status})`);
    const model = await response.json();
    const meshDefinition = model.meshes?.[0];
    const primitive = meshDefinition?.primitives?.[0];
    const encoded = model.buffers?.[0]?.uri?.split(',', 2)?.[1];
    const outline2d = meshDefinition?.extras?.outline2d;
    if (!primitive || !encoded || !Array.isArray(outline2d)) throw new Error('Lightning bolt model is missing embedded mesh data');

    const binary = Uint8Array.from(atob(encoded), (character) => character.charCodeAt(0));
    const componentReaders = {
      5125: { bytes: 4, read: (view, offset) => view.getUint32(offset, true), ArrayType: Uint32Array },
      5126: { bytes: 4, read: (view, offset) => view.getFloat32(offset, true), ArrayType: Float32Array },
    };
    const componentCounts = { SCALAR: 1, VEC2: 2, VEC3: 3 };
    const readAccessor = (accessorIndex) => {
      const accessor = model.accessors[accessorIndex];
      const bufferView = model.bufferViews[accessor.bufferView];
      const format = componentReaders[accessor.componentType];
      const componentCount = componentCounts[accessor.type];
      if (!format || !componentCount) throw new Error(`Unsupported lightning bolt accessor ${accessorIndex}`);
      const stride = bufferView.byteStride || (format.bytes * componentCount);
      const start = (bufferView.byteOffset || 0) + (accessor.byteOffset || 0);
      const source = new DataView(binary.buffer, binary.byteOffset, binary.byteLength);
      const values = new format.ArrayType(accessor.count * componentCount);
      for (let item = 0; item < accessor.count; item += 1) {
        for (let component = 0; component < componentCount; component += 1) {
          values[(item * componentCount) + component] = format.read(
            source,
            start + (item * stride) + (component * format.bytes),
          );
        }
      }
      return values;
    };

    const positions = readAccessor(primitive.attributes.POSITION);
    const normals = readAccessor(primitive.attributes.NORMAL);
    const indices = readAccessor(primitive.indices);
    let minY = Number.POSITIVE_INFINITY;
    let maxY = Number.NEGATIVE_INFINITY;
    for (let index = 1; index < positions.length; index += 3) {
      const y = positions[index];
      if (y < minY) minY = y;
      if (y > maxY) maxY = y;
    }
    return {
      positions,
      normals,
      indices,
      outline: buildLightningOutlineMesh(outline2d.map(([x, y]) => ({ x, y }))),
      bounds: { minY, maxY },
    };
  }

  function polygonArea(points) {
    let area = 0;
    points.forEach((point, index) => {
      const next = points[(index + 1) % points.length];
      area += (point.x * next.y) - (next.x * point.y);
    });
    return area * 0.5;
  }

  function normalize2D(vector) {
    const length = Math.hypot(vector.x, vector.y);
    return length > 0 ? { x: vector.x / length, y: vector.y / length } : { x: 0, y: 0 };
  }

  function buildLightningOutlineMesh(points) {
    if (!Array.isArray(points) || points.length < 3) {
      return {
        positions: new Float32Array(),
        normals: new Float32Array(),
        indices: new Uint32Array(),
      };
    }
    const outlineWidth = .045;
    const winding = polygonArea(points) >= 0 ? 1 : -1;
    const outerPoints = points.map((point, index) => {
      const previous = points[(index + points.length - 1) % points.length];
      const next = points[(index + 1) % points.length];
      const incoming = normalize2D({ x: point.x - previous.x, y: point.y - previous.y });
      const outgoing = normalize2D({ x: next.x - point.x, y: next.y - point.y });
      const incomingNormal = winding > 0
        ? { x: incoming.y, y: -incoming.x }
        : { x: -incoming.y, y: incoming.x };
      const outgoingNormal = winding > 0
        ? { x: outgoing.y, y: -outgoing.x }
        : { x: -outgoing.y, y: outgoing.x };
      const miter = normalize2D({
        x: incomingNormal.x + outgoingNormal.x,
        y: incomingNormal.y + outgoingNormal.y,
      });
      const reference = outgoingNormal;
      const divider = Math.abs((miter.x * reference.x) + (miter.y * reference.y));
      const scale = outlineWidth / Math.max(.35, divider);
      return {
        x: point.x + (miter.x * scale),
        y: point.y + (miter.y * scale),
      };
    });

    const positions = [];
    const normals = [];
    const indices = [];
    points.forEach((point, index) => {
      const outer = outerPoints[index];
      positions.push(point.x, point.y, 0, outer.x, outer.y, 0);
      normals.push(0, 0, 1, 0, 0, 1);
    });
    for (let index = 0; index < points.length; index += 1) {
      const next = (index + 1) % points.length;
      const base = index * 2;
      const nextBase = next * 2;
      indices.push(base, nextBase, nextBase + 1, base, nextBase + 1, base + 1);
    }
    return {
      positions: new Float32Array(positions),
      normals: new Float32Array(normals),
      indices: new Uint32Array(indices),
    };
  }

  function createPowerPlantBoltLayer(map) {
    const vertexSource = `
      precision highp float;
      attribute vec3 a_position;
      attribute vec3 a_normal;
      attribute vec2 a_anchor;
      attribute vec3 a_accentColor;
      attribute vec3 a_outlineColor;
      attribute float a_phase;
      attribute float a_size;
      attribute float a_hover;
      attribute float a_fillFraction;
      uniform mat4 u_matrix;
      uniform vec2 u_viewportSize;
      uniform float u_time;
      uniform float u_scale;
      uniform float u_fillMinY;
      uniform float u_fillMaxY;
      uniform mediump float u_glowPass;
      uniform mediump float u_outlineOnly;
      varying vec3 v_accentColor;
      varying vec3 v_outlineColor;
      varying float v_light;
      varying float v_hover;
      varying float v_fillY;
      varying float v_fillFraction;

      void main() {
        vec4 clip = u_matrix * vec4(a_anchor, 0.0, 1.0);
        float pulse = 1.0 + (sin((u_time * 2.1) + (a_phase * 1.7)) * 0.04);
        float rotation = (u_time * 1.15) + a_phase;
        float cosAngle = cos(rotation);
        float sinAngle = sin(rotation);
        vec3 rotated = vec3(
          (a_position.x * cosAngle) + (a_position.z * sinAngle),
          a_position.y,
          (-a_position.x * sinAngle) + (a_position.z * cosAngle)
        );
        vec3 rotatedNormal = normalize(vec3(
          (a_normal.x * cosAngle) + (a_normal.z * sinAngle),
          a_normal.y,
          (-a_normal.x * sinAngle) + (a_normal.z * cosAngle)
        ));
        float tilt = -0.18;
        vec2 modelScreen = vec2(
          rotated.x,
          -((rotated.y * cos(tilt)) - (rotated.z * sin(tilt)))
        );
        float hoverScale = 1.0 + (a_hover * u_glowPass * 0.32);
        vec2 offsetPixels = modelScreen * a_size * u_scale * pulse * hoverScale;
        vec2 offsetClip = vec2(
          (offsetPixels.x / u_viewportSize.x) * 2.0 * clip.w,
          (-offsetPixels.y / u_viewportSize.y) * 2.0 * clip.w
        );
        gl_Position = clip + vec4(offsetClip, 0.0, 0.0);
        v_accentColor = a_accentColor;
        v_outlineColor = a_outlineColor;
        v_light = 0.42 + (0.58 * max(dot(rotatedNormal, normalize(vec3(-0.35, 0.55, 0.75))), 0.0));
        v_hover = a_hover;
        v_fillY = a_position.y;
        v_fillFraction = a_fillFraction;
      }
    `;
    const fragmentSource = `
      precision mediump float;
      uniform mediump float u_fillMinY;
      uniform mediump float u_fillMaxY;
      uniform mediump float u_glowPass;
      uniform mediump float u_outlineOnly;
      varying vec3 v_accentColor;
      varying vec3 v_outlineColor;
      varying float v_light;
      varying float v_hover;
      varying float v_fillY;
      varying float v_fillFraction;

      void main() {
        vec3 energizedColor = mix(v_accentColor, vec3(1.0), 0.3);
        vec3 litColor = min(vec3(1.0), energizedColor * (0.95 + (v_light * 0.35)));
        float fillFraction = clamp(v_fillFraction, 0.0, 1.0);
        float fillCutoff = mix(u_fillMinY, u_fillMaxY, fillFraction);
        float filled = step(v_fillY, fillCutoff);
        if (u_outlineOnly > 0.5) {
          vec3 outlineColor = min(vec3(1.0), v_outlineColor * mix(0.88, 1.08, v_hover));
          gl_FragColor = vec4(outlineColor, mix(0.92, 1.0, v_hover));
          return;
        }
        if (filled < 0.5) discard;
        if (u_glowPass > 0.5) {
          vec3 glowColor = mix(energizedColor * 0.52, vec3(1.0), v_hover * 0.7);
          float glowAlpha = mix(0.38, 0.92, v_hover);
          gl_FragColor = vec4(glowColor * glowAlpha, glowAlpha);
          return;
        }
        gl_FragColor = vec4(litColor, 1.0);
      }
    `;

    const state = {
      entries: [],
      records: [],
      hoveredRecordId: null,
      ready: false,
      removed: false,
      dirty: false,
      error: null,
      ext: null,
      program: null,
      instanceBuffer: null,
      positionBuffer: null,
      normalBuffer: null,
      indexBuffer: null,
      outlinePositionBuffer: null,
      outlineNormalBuffer: null,
      outlineIndexBuffer: null,
      indexCount: 0,
      outlineIndexCount: 0,
      vertexCount: 0,
      renderCount: 0,
      lastGlError: null,
      antialiasSamples: 0,
      fillMinY: 0,
      fillMaxY: 1,
      attribs: {},
      uniforms: {},
    };

    return {
      id: POWER_PLANT_WEBGL_LAYER_ID,
      type: 'custom',
      renderingMode: '2d',
      onAdd(_map, gl) {
        try {
          state.program = createProgram(gl, vertexSource, fragmentSource);
        } catch (error) {
          state.error = error.message;
          console.error('Unable to compile WebGL lightning bolt shaders', error);
          return;
        }
        state.ext = gl.getExtension('ANGLE_instanced_arrays');
        if (!state.ext && !gl.drawElementsInstanced) {
          throw new Error('Instanced WebGL markers unavailable');
        }
        if (!gl.drawElementsInstanced && !gl.getExtension('OES_element_index_uint')) {
          throw new Error('32-bit WebGL mesh indices unavailable');
        }
        state.attribs = {
          position: gl.getAttribLocation(state.program, 'a_position'),
          normal: gl.getAttribLocation(state.program, 'a_normal'),
          anchor: gl.getAttribLocation(state.program, 'a_anchor'),
          accentColor: gl.getAttribLocation(state.program, 'a_accentColor'),
          outlineColor: gl.getAttribLocation(state.program, 'a_outlineColor'),
          phase: gl.getAttribLocation(state.program, 'a_phase'),
          size: gl.getAttribLocation(state.program, 'a_size'),
          hover: gl.getAttribLocation(state.program, 'a_hover'),
          fillFraction: gl.getAttribLocation(state.program, 'a_fillFraction'),
        };
        state.uniforms = {
          matrix: gl.getUniformLocation(state.program, 'u_matrix'),
          viewportSize: gl.getUniformLocation(state.program, 'u_viewportSize'),
          time: gl.getUniformLocation(state.program, 'u_time'),
          scale: gl.getUniformLocation(state.program, 'u_scale'),
          fillMinY: gl.getUniformLocation(state.program, 'u_fillMinY'),
          fillMaxY: gl.getUniformLocation(state.program, 'u_fillMaxY'),
          glowPass: gl.getUniformLocation(state.program, 'u_glowPass'),
          outlineOnly: gl.getUniformLocation(state.program, 'u_outlineOnly'),
        };
        state.antialiasSamples = gl.getParameter(gl.SAMPLES);
        state.instanceBuffer = gl.createBuffer();
        state.dirty = true;
        loadLightningBoltMesh().then((mesh) => {
          if (state.removed) return;
          state.positionBuffer = gl.createBuffer();
          gl.bindBuffer(gl.ARRAY_BUFFER, state.positionBuffer);
          gl.bufferData(gl.ARRAY_BUFFER, mesh.positions, gl.STATIC_DRAW);
          state.normalBuffer = gl.createBuffer();
          gl.bindBuffer(gl.ARRAY_BUFFER, state.normalBuffer);
          gl.bufferData(gl.ARRAY_BUFFER, mesh.normals, gl.STATIC_DRAW);
          state.indexBuffer = gl.createBuffer();
          gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, state.indexBuffer);
          gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, mesh.indices, gl.STATIC_DRAW);
          state.outlinePositionBuffer = gl.createBuffer();
          gl.bindBuffer(gl.ARRAY_BUFFER, state.outlinePositionBuffer);
          gl.bufferData(gl.ARRAY_BUFFER, mesh.outline.positions, gl.STATIC_DRAW);
          state.outlineNormalBuffer = gl.createBuffer();
          gl.bindBuffer(gl.ARRAY_BUFFER, state.outlineNormalBuffer);
          gl.bufferData(gl.ARRAY_BUFFER, mesh.outline.normals, gl.STATIC_DRAW);
          state.outlineIndexBuffer = gl.createBuffer();
          gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, state.outlineIndexBuffer);
          gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, mesh.outline.indices, gl.STATIC_DRAW);
          state.vertexCount = mesh.positions.length / 3;
          state.indexCount = mesh.indices.length;
          state.outlineIndexCount = mesh.outline.indices.length;
          state.fillMinY = mesh.bounds.minY;
          state.fillMaxY = mesh.bounds.maxY;
          state.ready = true;
          map.triggerRepaint();
        }).catch((error) => {
          state.error = error.message;
          console.error('Unable to initialize WebGL lightning bolts', error);
        });
      },
      render(gl, options) {
        if (!state.ready || !state.entries.length) return;
        const boltOutlineScale = normalizeBoltOutlineScale(layerFilters.powerPlants.outlineScale);
        if (state.dirty) {
          const payload = new Float32Array(state.entries.length * 12);
          state.entries.forEach((entry, index) => {
            const offset = index * 12;
            payload[offset + 0] = entry.mercatorX;
            payload[offset + 1] = entry.mercatorY;
            payload[offset + 2] = entry.accent.r / 255;
            payload[offset + 3] = entry.accent.g / 255;
            payload[offset + 4] = entry.accent.b / 255;
            payload[offset + 5] = entry.outline.r / 255;
            payload[offset + 6] = entry.outline.g / 255;
            payload[offset + 7] = entry.outline.b / 255;
            payload[offset + 8] = entry.phase;
            payload[offset + 9] = entry.size;
            payload[offset + 10] = entry.record.id === state.hoveredRecordId ? 1 : 0;
            payload[offset + 11] = entry.fillFraction;
          });
          gl.bindBuffer(gl.ARRAY_BUFFER, state.instanceBuffer);
          gl.bufferData(gl.ARRAY_BUFFER, payload, gl.DYNAMIC_DRAW);
          state.dirty = false;
        }

        const divisor = (location, value) => {
          if (gl.vertexAttribDivisor) gl.vertexAttribDivisor(location, value);
          else state.ext.vertexAttribDivisorANGLE(location, value);
        };
        const drawElementsInstanced = (mode, count, type, offset, instances) => {
          if (gl.drawElementsInstanced) gl.drawElementsInstanced(mode, count, type, offset, instances);
          else state.ext.drawElementsInstancedANGLE(mode, count, type, offset, instances);
        };

        gl.useProgram(state.program);
        gl.bindBuffer(gl.ARRAY_BUFFER, state.positionBuffer);
        gl.enableVertexAttribArray(state.attribs.position);
        gl.vertexAttribPointer(state.attribs.position, 3, gl.FLOAT, false, 0, 0);
        divisor(state.attribs.position, 0);
        gl.bindBuffer(gl.ARRAY_BUFFER, state.normalBuffer);
        gl.enableVertexAttribArray(state.attribs.normal);
        gl.vertexAttribPointer(state.attribs.normal, 3, gl.FLOAT, false, 0, 0);
        divisor(state.attribs.normal, 0);

        gl.bindBuffer(gl.ARRAY_BUFFER, state.instanceBuffer);
        const stride = 12 * 4;
        gl.enableVertexAttribArray(state.attribs.anchor);
        gl.vertexAttribPointer(state.attribs.anchor, 2, gl.FLOAT, false, stride, 0);
        divisor(state.attribs.anchor, 1);
        gl.enableVertexAttribArray(state.attribs.accentColor);
        gl.vertexAttribPointer(state.attribs.accentColor, 3, gl.FLOAT, false, stride, 2 * 4);
        divisor(state.attribs.accentColor, 1);
        gl.enableVertexAttribArray(state.attribs.outlineColor);
        gl.vertexAttribPointer(state.attribs.outlineColor, 3, gl.FLOAT, false, stride, 5 * 4);
        divisor(state.attribs.outlineColor, 1);
        gl.enableVertexAttribArray(state.attribs.phase);
        gl.vertexAttribPointer(state.attribs.phase, 1, gl.FLOAT, false, stride, 8 * 4);
        divisor(state.attribs.phase, 1);
        gl.enableVertexAttribArray(state.attribs.size);
        gl.vertexAttribPointer(state.attribs.size, 1, gl.FLOAT, false, stride, 9 * 4);
        divisor(state.attribs.size, 1);
        gl.enableVertexAttribArray(state.attribs.hover);
        gl.vertexAttribPointer(state.attribs.hover, 1, gl.FLOAT, false, stride, 10 * 4);
        divisor(state.attribs.hover, 1);
        gl.enableVertexAttribArray(state.attribs.fillFraction);
        gl.vertexAttribPointer(state.attribs.fillFraction, 1, gl.FLOAT, false, stride, 11 * 4);
        divisor(state.attribs.fillFraction, 1);

        gl.uniformMatrix4fv(state.uniforms.matrix, false, options.defaultProjectionData.mainMatrix);
        gl.uniform2f(state.uniforms.viewportSize, map.getCanvas().clientWidth, map.getCanvas().clientHeight);
        gl.uniform1f(state.uniforms.time, performance.now() * 0.001);
        gl.uniform1f(state.uniforms.fillMinY, state.fillMinY);
        gl.uniform1f(state.uniforms.fillMaxY, state.fillMaxY);
        gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, state.indexBuffer);
        gl.enable(gl.BLEND);
        gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
        const depthTestEnabled = gl.isEnabled(gl.DEPTH_TEST);
        const depthWriteEnabled = gl.getParameter(gl.DEPTH_WRITEMASK);
        const alphaToCoverageEnabled = gl.isEnabled(gl.SAMPLE_ALPHA_TO_COVERAGE);
        const cullFaceEnabled = gl.isEnabled(gl.CULL_FACE);
        const cullFaceMode = gl.getParameter(gl.CULL_FACE_MODE);
        const frontFaceMode = gl.getParameter(gl.FRONT_FACE);
        gl.disable(gl.DEPTH_TEST);
        gl.depthMask(false);
        if (state.antialiasSamples > 1) gl.enable(gl.SAMPLE_ALPHA_TO_COVERAGE);
        gl.enable(gl.CULL_FACE);
        gl.cullFace(gl.BACK);
        gl.frontFace(gl.CCW);

        gl.uniform1f(state.uniforms.glowPass, 1.0);
        gl.uniform1f(state.uniforms.outlineOnly, 0.0);
        gl.uniform1f(state.uniforms.scale, 1.16);
        drawElementsInstanced(gl.TRIANGLES, state.indexCount, gl.UNSIGNED_INT, 0, state.entries.length);

        if (state.outlineIndexCount > 0) {
          gl.bindBuffer(gl.ARRAY_BUFFER, state.outlinePositionBuffer);
          gl.vertexAttribPointer(state.attribs.position, 3, gl.FLOAT, false, 0, 0);
          gl.bindBuffer(gl.ARRAY_BUFFER, state.outlineNormalBuffer);
          gl.vertexAttribPointer(state.attribs.normal, 3, gl.FLOAT, false, 0, 0);
          gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, state.outlineIndexBuffer);
          gl.uniform1f(state.uniforms.glowPass, 0.0);
          gl.uniform1f(state.uniforms.outlineOnly, 1.0);
          gl.uniform1f(state.uniforms.scale, boltOutlineScale);
          drawElementsInstanced(gl.TRIANGLES, state.outlineIndexCount, gl.UNSIGNED_INT, 0, state.entries.length);
          gl.bindBuffer(gl.ARRAY_BUFFER, state.positionBuffer);
          gl.vertexAttribPointer(state.attribs.position, 3, gl.FLOAT, false, 0, 0);
          gl.bindBuffer(gl.ARRAY_BUFFER, state.normalBuffer);
          gl.vertexAttribPointer(state.attribs.normal, 3, gl.FLOAT, false, 0, 0);
          gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, state.indexBuffer);
        }

        gl.uniform1f(state.uniforms.glowPass, 0.0);
        gl.uniform1f(state.uniforms.outlineOnly, 0.0);
        gl.uniform1f(state.uniforms.scale, 1.0);
        drawElementsInstanced(gl.TRIANGLES, state.indexCount, gl.UNSIGNED_INT, 0, state.entries.length);

        if (!alphaToCoverageEnabled) gl.disable(gl.SAMPLE_ALPHA_TO_COVERAGE);
        gl.cullFace(cullFaceMode);
        gl.frontFace(frontFaceMode);
        if (!cullFaceEnabled) gl.disable(gl.CULL_FACE);
        gl.depthMask(depthWriteEnabled);
        if (depthTestEnabled) gl.enable(gl.DEPTH_TEST);
        state.renderCount += 1;
        state.lastGlError = gl.getError();
        map.triggerRepaint();
      },
      onRemove(_map, gl) {
        state.removed = true;
        if (state.positionBuffer) gl.deleteBuffer(state.positionBuffer);
        if (state.normalBuffer) gl.deleteBuffer(state.normalBuffer);
        if (state.indexBuffer) gl.deleteBuffer(state.indexBuffer);
        if (state.outlinePositionBuffer) gl.deleteBuffer(state.outlinePositionBuffer);
        if (state.outlineNormalBuffer) gl.deleteBuffer(state.outlineNormalBuffer);
        if (state.outlineIndexBuffer) gl.deleteBuffer(state.outlineIndexBuffer);
        if (state.instanceBuffer) gl.deleteBuffer(state.instanceBuffer);
        if (state.program) gl.deleteProgram(state.program);
        state.ready = false;
      },
      setRecords(records) {
        state.records = records;
        if (!records.some((record) => record.id === state.hoveredRecordId)) state.hoveredRecordId = null;
        const sizeFactors = pointScaleFactors(records, layerFilters.powerPlants.sizeBy);
        state.entries = records.map((record, index) => {
          const coordinate = maplibregl.MercatorCoordinate.fromLngLat([record.longitude, record.latitude], 0);
          return {
            record,
            mercatorX: coordinate.x,
            mercatorY: coordinate.y,
            accent: hexToRgb(markerAccentColor(record, layerFilters.powerPlants.colorBy)),
            outline: hexToRgb(outlineColorForRecord(record, layerFilters.powerPlants.outlineBy)),
            phase: (index * 2.399963229728653) % (Math.PI * 2),
            size: 36 * sizeFactors.get(record),
            fillFraction: powerPlantFillFraction(record, layerFilters.powerPlants.fillBy, layerFilters.powerPlants.fillFraction),
          };
        }).sort((left, right) => left.size - right.size || left.record.id.localeCompare(right.record.id));
        state.dirty = true;
        map.triggerRepaint();
      },
      setHoveredRecord(record) {
        const recordId = record?.id || null;
        if (recordId === state.hoveredRecordId) return;
        state.hoveredRecordId = recordId;
        state.dirty = true;
        map.triggerRepaint();
      },
      getDiagnostics() {
        return {
          ready: state.ready,
          error: state.error,
          recordCount: state.records.length,
          instanceCount: state.entries.length,
          vertexCount: state.vertexCount,
          indexCount: state.indexCount,
          outlineIndexCount: state.outlineIndexCount,
          renderCount: state.renderCount,
          lastGlError: state.lastGlError,
          antialiasSamples: state.antialiasSamples,
          outlineScale: normalizeBoltOutlineScale(layerFilters.powerPlants.outlineScale),
          alphaToCoverage: state.antialiasSamples > 1,
          hoveredRecordId: state.hoveredRecordId,
          sizeBy: layerFilters.powerPlants.sizeBy,
          fillBy: layerFilters.powerPlants.fillBy,
          fillFraction: layerFilters.powerPlants.fillFraction,
          minimumSize: state.entries.length ? Math.min(...state.entries.map((entry) => entry.size)) : 0,
          maximumSize: state.entries.length ? Math.max(...state.entries.map((entry) => entry.size)) : 0,
          drawOrderAscending: state.entries.every((entry, index) => index === 0 || state.entries[index - 1].size <= entry.size),
          topmostRecordId: state.entries.at(-1)?.record.id || null,
          topmostSize: state.entries.at(-1)?.size || 0,
        };
      },
      getExportEntries() {
        return state.entries.map((entry) => ({
          longitude: entry.record.longitude,
          latitude: entry.record.latitude,
          accent: rgbToHex(entry.accent),
          outline: rgbToHex(entry.outline),
          size: entry.size,
          fillFraction: entry.fillFraction,
        }));
      },
      hitTest(point) {
        let best = null;
        state.entries.forEach((entry) => {
          const { record } = entry;
          const projected = map.project([record.longitude, record.latitude]);
          const dx = projected.x - point.x;
          const dy = projected.y - point.y;
          const distance = Math.hypot(dx, dy);
          if (distance > entry.size && !(Math.abs(dx) <= entry.size * .67 && Math.abs(dy) <= entry.size)) return;
          if (!best || entry.size > best.size || (entry.size === best.size && distance < best.distance)) {
            best = { record, distance, size: entry.size };
          }
        });
        return best
          ? {
            record: best.record,
            size: best.size,
            zOffset: state.entries.length ? best.size / Math.max(...state.entries.map((entry) => entry.size), 1) : 0,
          }
          : null;
      },
    };
  }

  function ensurePowerPlantBoltLayer(map) {
    if (map.getLayer(POWER_PLANT_WEBGL_LAYER_ID) && powerPlantBoltLayer) return powerPlantBoltLayer;
    powerPlantBoltLayer = createPowerPlantBoltLayer(map);
    map.addLayer(powerPlantBoltLayer);
    applyMapLayerOrder(map);
    return powerPlantBoltLayer;
  }

  function applyMarkerAppearance(record, element) {
    const colorBy = layerFilters.datacenters.colorBy;
    const outlineBy = layerFilters.datacenters.outlineBy;
    const glow = dataCenterGlow(record, layerFilters.datacenters.glowBy);
    const glowDistance = normalizeGlowDistance(layerFilters.datacenters.glowDistance);
    const glowBlur = normalizeGlowBlur(layerFilters.datacenters.glowBlur);
    element.style.setProperty('--marker-icon-fill', iconFillForRecord(record, colorBy));
    const outline = outlineColorForRecord(record, outlineBy);
    element.style.setProperty('--marker-outline-color', outline);
    element.style.setProperty('--marker-glow-color', glow.color);
    element.style.setProperty('--marker-glow-opacity', String(glow.opacity));
    element.style.setProperty('--marker-glow-scale', String(glow.scale * glowDistance));
    element.style.setProperty('--marker-glow-blur', String(glowBlur));
    element.style.setProperty('--marker-glow-edge-color', glow.edgeColor || glow.color);
    element.style.setProperty('--marker-glow-edge-opacity', glow.edgeOpacity || '0%');
    element.style.setProperty('--marker-glow-edge-soft-opacity', glow.edgeSoftOpacity || '0%');
    element.style.setProperty('--marker-glow-ring-width', String(glow.ringWidth || .045));
    element.style.setProperty('--marker-glow-edge-spread', String(glow.edgeSpread || .24));
    element.dataset.glow = glow.kind;
    element.dataset.exportColors = JSON.stringify(stylePaletteForRecord(record, colorBy).map((entry) => entry.color));
    element.dataset.exportOutline = outline;
    element.dataset.exportGlowColor = glow.color;
    element.dataset.exportGlowEdgeColor = glow.edgeColor || glow.color;
    element.dataset.exportGlowOpacity = String(glow.opacity);
    element.dataset.exportGlowScale = String(glow.scale * glowDistance);
    element.dataset.exportGlowBlur = String(glowBlur);
    element.dataset.exportGlowRingWidth = String(glow.ringWidth || .045);
  }

  function dataCenterGlow(record, glowBy) {
    if (glowBy !== 'contestation' || !Number.isInteger(record.contestation_score)) {
      return { kind: 'none', color: 'transparent', edgeColor: 'transparent', opacity: 0, scale: 1 };
    }
    if (record.contestation_score >= 4) {
      return { kind: 'contested', color: '#ff263f', edgeColor: '#ff263f', edgeOpacity: '0%', edgeSoftOpacity: '0%', opacity: 1, scale: 2.15 };
    }
    if (record.contestation_score === 3) {
      return { kind: 'contested', color: '#ff4b5f', edgeColor: '#ff4b5f', edgeOpacity: '0%', edgeSoftOpacity: '0%', opacity: .68, scale: 1.9 };
    }
    if (record.contestation_score === 0) {
      if (isPlannedUncontestedDataCenter(record)) {
        return { kind: 'planned-uncontested', color: '#fff15f', edgeColor: '#ffb000', edgeOpacity: '100%', edgeSoftOpacity: '80%', ringWidth: .12, edgeSpread: .5, opacity: 1, scale: 2.15 };
      }
      return { kind: 'quiet', color: '#ffffff', edgeColor: '#32dfff', edgeOpacity: '100%', edgeSoftOpacity: '82%', ringWidth: .12, edgeSpread: .52, opacity: 1, scale: 2.1 };
    }
    return { kind: 'none', color: 'transparent', edgeColor: 'transparent', opacity: 0, scale: 1 };
  }

  function powerPlantFillFraction(record, fillBy, fillFraction) {
    if (fillBy === 'custom') {
      return Number.isFinite(fillFraction) ? Math.max(0, Math.min(1, fillFraction)) : 1;
    }
    if (fillBy === 'resource-adjusted-utilization') {
      const utilization = powerPlantResourceAdjustedUtilization(record);
      if (Number.isFinite(utilization)) return utilization;
    }
    return 1;
  }

  function powerPlantCapacityFactor(record) {
    const explicit = Number(record.annual_capacity_factor);
    if (Number.isFinite(explicit)) return Math.max(0, explicit);
    const capacity = Number(record.nameplate_capacity_mw);
    const output = Number(record.planning_sustained_output_mw);
    if (Number.isFinite(capacity) && capacity > 0 && Number.isFinite(output)) return Math.max(0, output / capacity);
    return null;
  }

  function plantTechnologyUtilizationBenchmark(record) {
    const technology = classifyPlantTechnology(record);
    const benchmarks = {
      solar: .2,
      wind: .35,
      hydro: .45,
      nuclear: .9,
      coal: .6,
      gas: .5,
      waste: .7,
      battery: .12,
      other: 1,
    };
    return benchmarks[technology] || benchmarks.other;
  }

  function powerPlantResourceAdjustedUtilization(record) {
    const factor = powerPlantCapacityFactor(record);
    const benchmark = plantTechnologyUtilizationBenchmark(record);
    if (!Number.isFinite(factor) || !Number.isFinite(benchmark) || benchmark <= 0) return null;
    return Math.max(0, Math.min(1, factor / benchmark));
  }

  function powerPlantAverageGeneration(record) {
    const values = [record.net_generation_mwh, record.reported_annual_energy_mwh]
      .map((value) => Number(value))
      .filter((value) => Number.isFinite(value));
    if (!values.length) return null;
    return values.reduce((sum, value) => sum + value, 0) / values.length;
  }

  function transmissionStatusExpression() {
    return ['downcase', ['to-string', ['coalesce', ['get', 'Status'], ['get', 'STATUS'], ['get', 'status'], ['get', 'Phase'], ['get', 'phase'], '']]];
  }

  function transmissionProposalExpression() {
    return ['match', transmissionStatusExpression(), ['proposed', 'proposal', 'planned', 'planning', 'pending', 'contested', 'under review', 'moratorium', 'paused'], true, false];
  }

  function transmissionLineColorExpression(config) {
    const baseColor = remoteLineColor(config);
    return config.id.includes('transmission')
      ? ['case', transmissionProposalExpression(), '#ff263f', baseColor]
      : baseColor;
  }

  function transmissionLineWidthExpression(config) {
    const base = ['interpolate', ['linear'], ['zoom'], config.minZoom, 1, 15, 4];
    return base;
  }

  function transmissionLineOpacityExpression(config) {
    if (!config.id.includes('transmission')) return .88;
    return ['case', transmissionProposalExpression(), 1, .88];
  }

  function transmissionLineBlurExpression(config) {
    if (!config.id.includes('transmission')) return 0;
    return ['case', transmissionProposalExpression(), 4.5, 0];
  }

  let enviroScreenData = null;
  let enviroScreenRequest = null;
  let parcelHoverTimer = null;
  let parcelHoverAbort = null;
  let parcelBoundaryAbort = null;
  let inspectorParcelAbort = null;
  let hoveredParcel = null;
  let parcelBoundaryData = { type: 'FeatureCollection', features: [] };
  const remoteLayerStates = new Map();
  const layerCustomColors = new Map();
  const layerZoomRanges = new Map();
  const layerPreviewSearchIndex = new Map();
  const layerCardOrigins = new Map();
  let esriBuildingsOverlay = null;
  let esriBuildingsEnabled = false;
  let aerialAnimationSettings = { speed: 1, distance: 1 };
  let activeTagFilters = [];
  let tagFilterMode = 'and';
  let inspectorHoverKey = null;
  let inspectorPinnedKey = null;
  let inspectorHoverLayerId = null;
  let inspectorPinnedLayerId = null;
  let hoveredDataCenterElement = null;
  let visibleDataCenterHoverEntries = [];
  let deckHoverTarget = null;
  let streetStyleLayerIds = [];
  const layerFilters = {
    datacenters: { text: '', status: 'all', energy: 'all', sentiment: 'all', powerScale: 'all', colorBy: 'energy', outlineBy: 'lifecycle', glowBy: 'contestation', glowDistance: 1, glowBlur: 1, sizeBy: 'none' },
    powerPlants: { text: '', energy: 'all', colorBy: 'energy', outlineBy: 'technology', fillBy: 'none', fillFraction: 1, sizeBy: 'none', outlineScale: 1.04 },
    neonStreets: { scope: 'i95', lineWidth: 1 },
    enviroscreen: { text: '', scoreBand: 'all', community: 'all' },
    parcels: { text: '' },
  };
  let layerSearch = '';
  let layerOrder = [];
  let layerOrderDragId = null;
  let activeLayerConfigId = null;
  let activeLayerColorId = null;
  let activeLayerContext = null;

  function defaultLayerZoomRange(layerId) {
    const bounded = (min, max) => normalizeZoomRange(min, max, { min: MAP_MIN_ZOOM, max: MAP_MAX_ZOOM });
    if (layerId === 'datacenters' || layerId === 'power-plants') return bounded(MAP_MIN_ZOOM, MAP_MAX_ZOOM);
    if (layerId === ESRI_BUILDINGS.id) return bounded(ESRI_BUILDINGS.minZoom ?? MAP_MIN_ZOOM, ESRI_BUILDINGS.maxZoom ?? MAP_MAX_ZOOM);
    const remote = REMOTE_LAYERS.find((config) => config.id === layerId);
    if (remote) return bounded(remote.minZoom ?? MAP_MIN_ZOOM, remote.maxZoom ?? MAP_MAX_ZOOM);
    const core = CORE_LAYER_PREVIEWS[layerId];
    if (core) return bounded(core.minZoom ?? core.source?.minzoom ?? MAP_MIN_ZOOM, core.maxZoom ?? core.source?.maxzoom ?? MAP_MAX_ZOOM);
    return bounded(MAP_MIN_ZOOM, MAP_MAX_ZOOM);
  }

  function normalizeZoomRange(minValue, maxValue, fallback = { min: MAP_MIN_ZOOM, max: MAP_MAX_ZOOM }) {
    const min = Number(minValue);
    const max = Number(maxValue);
    let normalizedMin = Number.isFinite(min) ? min : fallback.min;
    let normalizedMax = Number.isFinite(max) ? max : fallback.max;
    normalizedMin = Math.max(MAP_MIN_ZOOM, Math.min(MAP_MAX_ZOOM, normalizedMin));
    normalizedMax = Math.max(MAP_MIN_ZOOM, Math.min(MAP_MAX_ZOOM, normalizedMax));
    if (normalizedMax < normalizedMin) normalizedMax = normalizedMin;
    return {
      min: Number(normalizedMin.toFixed(2)),
      max: Number(normalizedMax.toFixed(2)),
    };
  }

  function zoomRangeForLayer(layerId) {
    const fallback = defaultLayerZoomRange(layerId);
    return normalizeZoomRange(layerZoomRanges.get(layerId)?.min, layerZoomRanges.get(layerId)?.max, fallback);
  }

  function layerShownAtZoom(layerId, zoom) {
    const range = zoomRangeForLayer(layerId);
    return zoom >= range.min && zoom <= range.max;
  }

  function zoomRangeLabel(layerId) {
    const range = zoomRangeForLayer(layerId);
    return `${number(range.min, 2)}–${number(range.max, 2)}`;
  }

  function zoomRangeChanged(layerId) {
    const defaults = defaultLayerZoomRange(layerId);
    const range = zoomRangeForLayer(layerId);
    return range.min !== defaults.min || range.max !== defaults.max;
  }

  const FILTER_OPTIONS = {
    status: [
      ['all', 'All lifecycle stages'],
      ['unbuilt', 'Unbuilt with projected demand'],
      ['operating', 'Existing / operating'],
      ['development', 'Permitted / developing'],
      ['proposal', 'Proposed / planned'],
      ['paused', 'Paused / blocked'],
    ],
    energy: [
      ['all', 'All energy sources'],
      ['SUN', 'Solar'],
      ['BIT', 'Coal'],
      ['NG', 'Natural gas / propane'],
      ['DFO', 'Oil / diesel'],
      ['WND', 'Wind'],
      ['WAT', 'Hydroelectric'],
      ['NUC', 'Nuclear'],
      ['MWH', 'Battery storage'],
      ['WASTE', 'Waste / biomass'],
      ['UNKNOWN', 'Undisclosed'],
    ],
    datacenterIconColor: [
      ['energy', 'Energy profile'],
      ['lifecycle', 'Lifecycle stage'],
      ['sentiment', 'Public response'],
    ],
    datacenterIconOutline: [
      ['none', 'No semantic outline'],
      ['lifecycle', 'Lifecycle stage'],
      ['sentiment', 'Public response'],
      ['energy', 'Energy profile'],
    ],
    datacenterIconGlow: [
      ['contestation', 'Contestation · red / planned yellow / quiet white'],
      ['none', 'No glow'],
    ],
    plantIconColor: [
      ['energy', 'Fuel / energy profile'],
      ['technology', 'Plant technology'],
      ['scale', 'Plant size'],
    ],
    plantBoltOutline: [
      ['none', 'Neutral light outline'],
      ['energy', 'Fuel / energy profile'],
      ['technology', 'Plant technology'],
      ['scale', 'Plant size'],
    ],
    plantBoltFill: [
      ['none', 'Full bolt'],
      ['resource-adjusted-utilization', 'Resource-adjusted annual utilization'],
      ['custom', 'Custom fraction from bottom'],
    ],
    sentiment: [
      ['all', 'All public-response evidence'],
      ['opposed', 'Documented opposition'],
      ['supportive', 'Documented support'],
      ['mixed', 'Mixed / unclear'],
      ['unknown', 'Insufficient evidence'],
    ],
    powerScale: [
      ['all', 'All power classes'],
      ['sub-megawatt', 'Sub-megawatt'],
      ['small', 'Small · 1 to under 5 MW'],
      ['medium', 'Medium · 5 to under 20 MW'],
      ['large', 'Large · 20 to under 100 MW'],
      ['very-large', 'Very large · 100 MW or more'],
      ['unknown', 'Power draw undisclosed'],
    ],
    enviroScoreBand: [
      ['all', 'All EJ scores'],
      ['25', '25 and above'],
      ['50', '50 and above'],
      ['75', '75 and above'],
    ],
    enviroCommunity: [
      ['all', 'All communities'],
      ['overburdened', 'Overburdened only'],
      ['underserved', 'Underserved only'],
      ['either', 'Overburdened or underserved'],
      ['both', 'Both flags present'],
    ],
  };

  function normalizeLineWidthMultiplier(value) {
    const width = Number(value);
    return Number.isFinite(width) ? Math.max(.25, Math.min(5, width)) : 1;
  }

  function normalizeLineWidthBy(config, value) {
    const selected = String(value || 'zoom');
    return lineWidthFieldOptions(config).some(([field]) => field === selected) ? selected : 'zoom';
  }

  function normalizeGlowDistance(value) {
    const distance = Number(value);
    return Number.isFinite(distance) ? Math.max(.35, Math.min(2.5, distance)) : 1;
  }

  function normalizeGlowBlur(value) {
    const blur = Number(value);
    return Number.isFinite(blur) ? Math.max(0, Math.min(2.5, blur)) : 1;
  }

  function normalizeBoltOutlineScale(value) {
    const scale = Number(value);
    return Number.isFinite(scale) ? Math.max(.5, Math.min(2, scale)) : 1.04;
  }

  function scaledLineWidth(expression, multiplier) {
    const scale = normalizeLineWidthMultiplier(multiplier);
    if (Array.isArray(expression) && expression[0] === 'interpolate') {
      return expression.map((part, index) => (index > 2 && index % 2 === 0 && typeof part === 'number' ? part * scale : part));
    }
    return expression;
  }

  function fieldExistsInOutFields(config, field) {
    if (!config) return false;
    return (config.outFields || []).includes(field) || (config.facts || []).some((fact) => fact[1] === field);
  }

  function lineWidthFieldOptions(config) {
    const configured = config?.lineWidthFields || [];
    const inferred = [
      ['VOLT_CLASS', 'Voltage class'],
      ['VOLTAGE', 'Voltage (kV)'],
      ['Voltage_kV', 'Voltage (kV)'],
      ['Voltage', 'Voltage (kV)'],
      ['Capacity_MW', 'Available load capacity (MW)'],
      ['Feeder_Capacity_MW', 'Feeder capacity (MW)'],
      ['Transformer_or_Network_Capacity_MW', 'Transformer / network capacity (MW)'],
      ['Substation_Capacity_MW', 'Substation capacity (MW)'],
      ['Max_FEEDER_AVAIL_CAP_MW_MIN', 'Maximum feeder capacity (MW)'],
      ['Sum_FEEDER_AVAIL_CAP_MW_MIN', 'Feeder capacity sum (MW)'],
      ['Allowable_PV_kW', 'Allowable PV (kW)'],
      ['Total_Active_Gen_kW', 'Active generation (kW)'],
      ['Total_Pending_Gen_kW', 'Pending generation (kW)'],
      ['MaxCapacity', 'Published maximum capacity'],
    ].filter(([field]) => fieldExistsInOutFields(config, field));
    const seen = new Set();
    return [...LINE_WIDTH_BY_DEFAULT, ...configured, ...inferred].filter(([field]) => {
      if (seen.has(field)) return false;
      seen.add(field);
      return true;
    });
  }

  function lineWidthStopsForField(field) {
    const lower = String(field || '').toLowerCase();
    if (lower.includes('volt')) return [0, .8, 69, 1.1, 115, 1.4, 230, 2, 345, 2.7, 500, 3.5, 735, 4.3];
    if (lower.includes('kw')) return [0, .7, 250, 1, 1000, 1.5, 3000, 2.2, 6000, 3, 10000, 4];
    if (lower.includes('mw') || lower.includes('maxcapacity')) return [0, .7, .25, 1, 1, 1.4, 2, 1.8, 4, 2.5, 8, 3.5, 15, 4.5];
    return [0, .7, 1, 1, 2, 1.4, 5, 2, 10, 2.8, 25, 4];
  }

  function voltageClassLineWidthExpression(multiplier) {
    const scale = normalizeLineWidthMultiplier(multiplier);
    return [
      'match', ['to-string', ['get', 'VOLT_CLASS']],
      'Under 100', 1 * scale,
      '100-161', 1.4 * scale,
      '220-287', 2 * scale,
      '345', 2.7 * scale,
      '500', 3.5 * scale,
      '735 And Above', 4.3 * scale,
      'DC', 3.2 * scale,
      'Dc', 3.2 * scale,
      1 * scale,
    ];
  }

  function lineWidthExpressionForField(field, multiplier) {
    if (field === 'VOLT_CLASS') return voltageClassLineWidthExpression(multiplier);
    return scaledLineWidth(['interpolate', ['linear'], ['to-number', ['get', field], 0], ...lineWidthStopsForField(field)], multiplier);
  }

  function normalizePowerPlantLayerFilters(filters) {
    filters.outlineScale = normalizeBoltOutlineScale(filters.outlineScale);
    if (filters.fillBy === 'resource-adjusted-utilization' && (!filters.sizeBy || filters.sizeBy === 'none')) {
      filters.sizeBy = 'planning_sustained_output_mw';
    }
    return filters;
  }

  function layerOrderIds() {
    return [
      'datacenters',
      'power-plants',
      'neon-streets',
      'enviroscreen',
      'parcels',
      ESRI_BUILDINGS.id,
      ...REMOTE_LAYERS.map((config) => config.id),
    ];
  }

  function normalizeLayerOrder(order) {
    const validIds = layerOrderIds();
    const valid = new Set(validIds);
    const normalized = [];
    (Array.isArray(order) ? order : []).forEach((id) => {
      if (valid.has(id) && !normalized.includes(id)) normalized.push(id);
    });
    validIds.forEach((id) => {
      if (!normalized.includes(id)) normalized.push(id);
    });
    return normalized;
  }

  function renderedLayerIdsForUiLayer(layerId) {
    if (layerId === 'power-plants') return [POWER_PLANT_WEBGL_LAYER_ID];
    if (layerId === 'neon-streets') return [NEON_STREET_GLOW_LAYER_ID, NEON_STREET_CORE_LAYER_ID, NEON_STREET_LABEL_LAYER_ID];
    if (layerId === 'enviroscreen') return [ENVIROSCREEN_FILL_ID, ENVIROSCREEN_LINE_ID];
    if (layerId === 'parcels') return [PARCEL_LAYER_ID, PARCEL_HOVER_FILL_ID, PARCEL_HOVER_LINE_ID];
    const remoteConfig = REMOTE_LAYERS.find((config) => config.id === layerId);
    if (remoteConfig) return remoteRenderLayerIds(remoteConfig);
    return [];
  }

  function selectedOverlayLayerIds() {
    return layerOrder.filter((layerId) => document.getElementById(`show-${layerId}`)?.checked);
  }

  function layerZIndex(layerId) {
    const ordered = selectedOverlayLayerIds();
    const index = ordered.indexOf(layerId);
    return index === -1 ? -1 : ordered.length - index;
  }

  function applyMapLayerOrder(map) {
    if (!map?.getStyle?.()?.layers) return;
    selectedOverlayLayerIds().slice().reverse().forEach((layerId) => {
      renderedLayerIdsForUiLayer(layerId).forEach((renderLayerId) => {
        if (!map.getLayer(renderLayerId)) return;
        try {
          map.moveLayer(renderLayerId);
        } catch (_error) {
          // Some style reload windows briefly reject layer moves; the next render pass retries.
        }
      });
    });
  }

  function readUiState() {
    let state = {};
    try {
      state = JSON.parse(localStorage.getItem(UI_STATE_STORAGE_KEY) || '{}');
    } catch (_error) {
      state = {};
    }
    const parameters = new URLSearchParams(window.location.search);
    if (parameters.has('theme')) state.theme = parameters.get('theme');
    if (parameters.has('base')) state.baseLayer = parameters.get('base');
    if (parameters.has('layers')) state.layers = parameters.get('layers').split(',').filter(Boolean);
    if (parameters.has('order')) state.layerOrder = parameters.get('order').split(',').filter(Boolean);
    if (parameters.has('hover')) state.hover = parameters.get('hover').split(',').filter(Boolean);
    if (parameters.has('q')) state.search = parameters.get('q');
    if (parameters.has('z')) state.zoom = Number(parameters.get('z'));
    if (parameters.has('c')) {
      const [lng, lat] = parameters.get('c').split(',').map(Number);
      if (Number.isFinite(lng) && Number.isFinite(lat)) {
        state.center = [lng, lat];
      }
    }
    if (parameters.has('o')) {
      const [bearing, pitch] = parameters.get('o').split(',').map(Number);
      if (Number.isFinite(bearing) || Number.isFinite(pitch)) {
        state.orientation = {
          bearing: Number.isFinite(bearing) ? bearing : 0,
          pitch: Number.isFinite(pitch) ? pitch : 0,
        };
      }
    }
    if (parameters.has('filters')) {
      try {
        state.filters = JSON.parse(parameters.get('filters'));
      } catch (_error) {
        // Ignore a malformed share URL and retain any valid locally stored filters.
      }
    }
    if (parameters.has('animation')) {
      const [speed, distance] = parameters.get('animation').split(',').map(Number);
      state.animation = { speed, distance };
    }
    if (parameters.has('tags')) {
      try {
        state.tagFilters = JSON.parse(parameters.get('tags'));
      } catch (_error) {
        state.tagFilters = [];
      }
    }
    if (parameters.has('tagMode')) state.tagFilterMode = parameters.get('tagMode');
    if (parameters.has('mapTitle')) state.mapTitle = parameters.get('mapTitle');
    if (parameters.has('showTitle')) state.showMapTitle = parameters.get('showTitle') === '1';
    if (parameters.has('colors')) {
      try {
        state.colors = JSON.parse(parameters.get('colors'));
      } catch (_error) {
        state.colors = {};
      }
    }
    return state;
  }

  function applyUiState(state, themeSelect) {
    if (state.theme && BASEMAP_STYLES[state.theme]) themeSelect.value = state.theme;
    if (Array.isArray(state.layers)) {
      document.querySelectorAll('input[id^="show-"]:not(.dc-base-layer-toggle):not(#show-map-title)').forEach((input) => {
        input.checked = state.layers.includes(input.id.slice(5));
      });
    }
    layerOrder = normalizeLayerOrder(state.layerOrder);
    const baseLayerId = BASE_LAYER_IDS.has(state.baseLayer) ? state.baseLayer : 'street-map';
    document.querySelectorAll('.dc-base-layer-toggle').forEach((input) => {
      input.checked = state.baseLayer === 'none' ? false : input.id === `show-${baseLayerId}`;
    });
    if (Array.isArray(state.hover)) {
      document.querySelectorAll('input[id^="hover-"]').forEach((input) => {
        input.checked = state.hover.includes(input.id.slice(6));
      });
    }
    layerSearch = String(state.search || '').trim().toLowerCase();
    document.getElementById('layer-search').value = layerSearch;
    if (state.filters?.datacenters) {
      Object.assign(layerFilters.datacenters, state.filters.datacenters);
      layerFilters.datacenters.glowDistance = normalizeGlowDistance(layerFilters.datacenters.glowDistance);
      layerFilters.datacenters.glowBlur = normalizeGlowBlur(layerFilters.datacenters.glowBlur);
    }
    if (state.filters?.powerPlants) {
      Object.assign(layerFilters.powerPlants, state.filters.powerPlants);
      normalizePowerPlantLayerFilters(layerFilters.powerPlants);
    }
    if (state.filters?.neonStreets) Object.assign(layerFilters.neonStreets, state.filters.neonStreets);
    if (state.filters?.enviroscreen) Object.assign(layerFilters.enviroscreen, state.filters.enviroscreen);
    if (state.filters?.parcels) Object.assign(layerFilters.parcels, state.filters.parcels);
    layerCustomColors.clear();
    Object.entries(state.colors || {}).forEach(([layerId, color]) => {
      if (/^#[0-9a-f]{6}$/i.test(String(color))) layerCustomColors.set(layerId, String(color).toLowerCase());
    });
    layerZoomRanges.clear();
    Object.entries(state.filters?.zoomRanges || {}).forEach(([layerId, range]) => {
      layerZoomRanges.set(layerId, normalizeZoomRange(range?.min, range?.max, defaultLayerZoomRange(layerId)));
    });
    aerialAnimationSettings = normalizeAerialAnimationSettings(state.animation);
    activeTagFilters = normalizeTagFilters(state.tagFilters);
    tagFilterMode = state.tagFilterMode === 'or' ? 'or' : 'and';
    document.getElementById('map-title-input').value = String(state.mapTitle || 'Infrastructure map').slice(0, 120);
    document.getElementById('show-map-title').checked = Boolean(state.showMapTitle);
    REMOTE_LAYERS.forEach((config) => {
      const remoteState = remoteLayerStates.get(config.id);
      if (!remoteState) return;
      remoteState.enabled = document.getElementById(`show-${config.id}`).checked;
      const savedFilter = state.filters?.remote?.[config.id] || {};
      remoteState.text = String(savedFilter.text || '').trim().toLowerCase();
      remoteState.sizeBy = String(savedFilter.sizeBy || config.defaultSizeBy || 'none');
      remoteState.colorTheme = String(savedFilter.colorTheme || (config.lineColorThemes ? 'uniform' : 'default'));
      remoteState.lineWidth = normalizeLineWidthMultiplier(savedFilter.lineWidth);
      remoteState.lineWidthBy = normalizeLineWidthBy(config, savedFilter.lineWidthBy);
    });
  }

  function normalizedMapView(map) {
    const wrapDegrees = (value) => {
      const wrapped = ((value % 360) + 360) % 360;
      return wrapped > 180 ? wrapped - 360 : wrapped;
    };
    const center = map.getCenter();
    return {
      center: [
        Number(center.lng.toFixed(5)),
        Number(center.lat.toFixed(5)),
      ],
      zoom: Number(map.getZoom().toFixed(2)),
      orientation: {
        bearing: Number(wrapDegrees(map.getBearing()).toFixed(1)),
        pitch: Number(map.getPitch().toFixed(1)),
      },
    };
  }

  function currentUiState(map = null) {
    const checkedIds = (prefix) => [...document.querySelectorAll(`input[id^="${prefix}"]:checked:not(.dc-base-layer-toggle)`)]
      .filter((input) => input.id !== 'show-map-title')
      .map((input) => input.id.slice(prefix.length));
    const selectedBaseLayer = document.querySelector('.dc-base-layer-toggle:checked');
    const remoteFilters = {};
    REMOTE_LAYERS.forEach((config) => {
      const text = remoteLayerStates.get(config.id)?.text || '';
      const remoteState = remoteLayerStates.get(config.id);
      const defaultColorTheme = config.lineColorThemes ? 'uniform' : 'default';
      if (text || remoteState?.sizeBy !== 'none' || remoteState?.colorTheme !== defaultColorTheme || remoteState?.lineWidth !== 1 || remoteState?.lineWidthBy !== 'zoom') {
        remoteFilters[config.id] = {
          text,
          sizeBy: remoteState?.sizeBy || 'none',
          colorTheme: remoteState?.colorTheme || defaultColorTheme,
          lineWidth: normalizeLineWidthMultiplier(remoteState?.lineWidth),
          lineWidthBy: normalizeLineWidthBy(config, remoteState?.lineWidthBy),
        };
      }
    });
    const zoomRanges = {};
    [
      ...Object.keys(CORE_LAYER_PREVIEWS),
      ESRI_BUILDINGS.id,
      ...REMOTE_LAYERS.map((config) => config.id),
    ].forEach((layerId) => {
      if (!zoomRangeChanged(layerId)) return;
      zoomRanges[layerId] = zoomRangeForLayer(layerId);
    });
    const viewState = map ? normalizedMapView(map) : {};
    return {
      theme: document.getElementById('map-theme').value,
      baseLayer: selectedBaseLayer ? selectedBaseLayer.id.slice(5) : 'none',
      layers: checkedIds('show-'),
      layerOrder: normalizeLayerOrder(layerOrder),
      hover: checkedIds('hover-'),
      search: layerSearch,
      animation: { ...aerialAnimationSettings },
      tagFilters: [...activeTagFilters],
      tagFilterMode,
      mapTitle: document.getElementById('map-title-input').value.trim() || 'Infrastructure map',
      showMapTitle: document.getElementById('show-map-title').checked,
      colors: Object.fromEntries(layerCustomColors),
      ...viewState,
      filters: {
        datacenters: { ...layerFilters.datacenters },
        powerPlants: { ...layerFilters.powerPlants },
        neonStreets: { ...layerFilters.neonStreets },
        enviroscreen: { ...layerFilters.enviroscreen },
        parcels: { ...layerFilters.parcels },
        remote: remoteFilters,
        zoomRanges,
      },
    };
  }

  function persistUiState(map = activeLayerContext?.map || null) {
    const state = currentUiState(map);
    try {
      localStorage.setItem(UI_STATE_STORAGE_KEY, JSON.stringify(state));
    } catch (_error) {
      // URL state remains available when storage is disabled or full.
    }
    const url = new URL(window.location.href);
    url.searchParams.set('theme', state.theme);
    url.searchParams.set('base', state.baseLayer);
    url.searchParams.set('layers', state.layers.join(','));
    url.searchParams.set('order', state.layerOrder.join(','));
    url.searchParams.set('hover', state.hover.join(','));
    url.searchParams.set('q', state.search);
    url.searchParams.set('animation', `${state.animation.speed},${state.animation.distance}`);
    url.searchParams.set('tags', JSON.stringify(state.tagFilters));
    url.searchParams.set('tagMode', state.tagFilterMode);
    url.searchParams.set('mapTitle', state.mapTitle);
    url.searchParams.set('showTitle', state.showMapTitle ? '1' : '0');
    url.searchParams.set('colors', JSON.stringify(state.colors));
    if (Array.isArray(state.center) && state.center.length === 2) {
      url.searchParams.set('c', `${state.center[0]},${state.center[1]}`);
    }
    if (Number.isFinite(state.zoom)) url.searchParams.set('z', String(state.zoom));
    if (state.orientation) url.searchParams.set('o', `${state.orientation.bearing},${state.orientation.pitch}`);
    url.searchParams.set('filters', JSON.stringify(state.filters));
    history.replaceState(null, '', `${url.pathname}?${url.searchParams}${url.hash}`);
  }

  function setupUiStatePersistence(map) {
    document.querySelectorAll('#map-theme, input[id^="show-"], input[id^="hover-"]').forEach((control) => {
      control.addEventListener('change', () => persistUiState(map));
    });
    let pendingPersistenceFrame = 0;
    const persistMapView = () => {
      if (pendingPersistenceFrame) cancelAnimationFrame(pendingPersistenceFrame);
      pendingPersistenceFrame = requestAnimationFrame(() => persistUiState(map));
    };
    map.on('moveend', persistMapView);
    map.on('zoomend', persistMapView);
    map.on('rotateend', persistMapView);
    map.on('pitchend', persistMapView);
  }

  function layerCardId(card) {
    return card?.dataset?.layerPreview || '';
  }

  function overlayLayerCards() {
    const baseIds = new Set(BASE_LAYER_CONFIGS.map((config) => config.id));
    return [...document.querySelectorAll('.dc-controls .dc-layer-option[data-layer-preview]')]
      .filter((card) => !baseIds.has(layerCardId(card)));
  }

  function selectedLayerCardIds() {
    return selectedOverlayLayerIds().filter((layerId) => document.querySelector(`.dc-layer-option[data-layer-preview="${CSS.escape(layerId)}"]`));
  }

  function markLayerCardOrigins() {
    overlayLayerCards().forEach((card) => {
      const layerId = layerCardId(card);
      if (layerCardOrigins.has(layerId)) return;
      const marker = document.createComment(`layer-origin:${layerId}`);
      card.parentNode.insertBefore(marker, card);
      layerCardOrigins.set(layerId, marker);
    });
  }

  function restoreLayerCard(card) {
    const marker = layerCardOrigins.get(layerCardId(card));
    if (marker?.parentNode) marker.parentNode.insertBefore(card, marker.nextSibling);
  }

  function syncDataCenterMarkerZOrder() {
    const z = layerZIndex('datacenters');
    document.querySelectorAll('.dc-map-marker--center').forEach((element) => {
      element.style.zIndex = z >= 0 ? String(100 + z) : '';
    });
  }

  function renderLayerOrderControls(map = activeLayerContext?.map || null) {
    markLayerCardOrigins();
    layerOrder = normalizeLayerOrder(layerOrder);
    const selectedContainer = document.getElementById('selected-layer-controls');
    const selectedSection = document.getElementById('selected-layer-order-section');
    const selectedIds = selectedLayerCardIds();
    selectedSection.hidden = selectedIds.length === 0;

    selectedIds.forEach((layerId) => {
      const card = document.querySelector(`.dc-layer-option[data-layer-preview="${CSS.escape(layerId)}"]`);
      if (!card) return;
      card.draggable = true;
      card.classList.add('is-layer-selected-order');
      selectedContainer.append(card);
    });

    overlayLayerCards().forEach((card) => {
      const layerId = layerCardId(card);
      const selected = selectedIds.includes(layerId);
      card.draggable = selected;
      card.classList.toggle('is-layer-selected-order', selected);
      if (!selected) restoreLayerCard(card);
    });

    applyMapLayerOrder(map);
    syncDataCenterMarkerZOrder();
    filterLayerCards(layerSearch);
  }

  function moveLayerOrderItem(draggedId, targetId) {
    if (!draggedId || !targetId || draggedId === targetId) return false;
    const selectedIds = selectedLayerCardIds();
    const withoutDragged = selectedIds.filter((id) => id !== draggedId);
    const targetIndex = withoutDragged.indexOf(targetId);
    if (targetIndex === -1) return false;
    withoutDragged.splice(targetIndex, 0, draggedId);
    const remaining = normalizeLayerOrder(layerOrder).filter((id) => !withoutDragged.includes(id));
    layerOrder = [...withoutDragged, ...remaining];
    return true;
  }

  function setupLayerOrdering(map) {
    markLayerCardOrigins();
    layerOrder = normalizeLayerOrder(layerOrder);
    overlayLayerCards().forEach((card) => {
      card.addEventListener('dragstart', (event) => {
        if (!card.draggable) {
          event.preventDefault();
          return;
        }
        layerOrderDragId = layerCardId(card);
        card.classList.add('is-layer-dragging');
        event.dataTransfer.effectAllowed = 'move';
        event.dataTransfer.setData('text/plain', layerOrderDragId);
      });
      card.addEventListener('dragover', (event) => {
        if (!layerOrderDragId || !card.draggable) return;
        event.preventDefault();
        event.dataTransfer.dropEffect = 'move';
        card.classList.add('is-layer-drop-target');
      });
      card.addEventListener('dragleave', () => {
        card.classList.remove('is-layer-drop-target');
      });
      card.addEventListener('drop', (event) => {
        event.preventDefault();
        card.classList.remove('is-layer-drop-target');
        if (moveLayerOrderItem(layerOrderDragId || event.dataTransfer.getData('text/plain'), layerCardId(card))) {
          renderLayerOrderControls(map);
          persistUiState(map);
        }
      });
      card.addEventListener('dragend', () => {
        card.classList.remove('is-layer-dragging');
        document.querySelectorAll('.is-layer-drop-target').forEach((target) => target.classList.remove('is-layer-drop-target'));
        layerOrderDragId = null;
      });
    });
    document.querySelectorAll('input[id^="show-"]:not(.dc-base-layer-toggle):not(#show-map-title)').forEach((input) => {
      input.addEventListener('change', () => renderLayerOrderControls(map));
    });
    renderLayerOrderControls(map);
  }

  function setupMapTitleControls(map) {
    const input = document.getElementById('map-title-input');
    const checkbox = document.getElementById('show-map-title');
    const overlay = document.createElement('div');
    overlay.id = 'rendered-map-title';
    overlay.className = 'dc-rendered-map-title';
    overlay.setAttribute('aria-hidden', 'true');
    map.getContainer().append(overlay);

    const sync = () => {
      const title = input.value.trim() || 'Infrastructure map';
      overlay.textContent = title;
      overlay.hidden = !checkbox.checked;
      document.getElementById('map-title').textContent = title;
      persistUiState(map);
    };
    input.addEventListener('input', sync);
    checkbox.addEventListener('change', sync);
    sync();
  }

  function activeBaseLayerId() {
    return document.querySelector('.dc-base-layer-toggle:checked')?.id.slice(5) || null;
  }

  function baseRasterSourceId(config) {
    return `base-${config.id}`;
  }

  function ensureMapFallbackBackground(map) {
    if (map.getLayer(MAP_FALLBACK_BACKGROUND_LAYER_ID)) return;
    const firstLayerId = map.getStyle().layers[0]?.id;
    map.addLayer({
      id: MAP_FALLBACK_BACKGROUND_LAYER_ID,
      type: 'background',
      paint: {
        'background-color': '#002a61',
        'background-opacity': 1,
      },
    }, firstLayerId);
  }

  function applyBaseLayerState(map) {
    const activeId = activeBaseLayerId();
    map.getContainer().classList.toggle('dc-map--no-base', activeId === null);
    ensureMapFallbackBackground(map);
    map.setLayoutProperty(
      MAP_FALLBACK_BACKGROUND_LAYER_ID,
      'visibility',
      activeId === 'street-map' ? 'none' : 'visible',
    );
    streetStyleLayerIds.forEach((layerId) => {
      if (!map.getLayer(layerId)) return;
      map.setLayoutProperty(layerId, 'visibility', activeId === 'street-map' ? 'visible' : 'none');
    });

    BASE_LAYER_CONFIGS.filter((config) => config.source).forEach((config) => {
      const sourceId = baseRasterSourceId(config);
      if (map.getLayer(sourceId)) map.removeLayer(sourceId);
      if (map.getSource(sourceId)) map.removeSource(sourceId);
      if (activeId !== config.id) return;
      map.addSource(sourceId, config.source);
      const firstStreetLayer = streetStyleLayerIds.find((layerId) => map.getLayer(layerId));
      map.addLayer({
        id: sourceId,
        type: 'raster',
        source: sourceId,
        paint: {
          'raster-opacity': 1,
          'raster-fade-duration': 120,
          'raster-resampling': 'linear',
        },
      }, firstStreetLayer);
    });
    applyNeonStreetLayer(map);
    map.triggerRepaint();
  }

  function neonStreetFilter(scope = layerFilters.neonStreets.scope) {
    const lineGeometry = ['match', ['geometry-type'], ['LineString', 'MultiLineString'], true, false];
    const roadClass = ['get', 'class'];
    let scopeFilter;
    if (scope === 'all') {
      scopeFilter = ['match', roadClass, ['motorway', 'trunk', 'primary', 'secondary', 'tertiary', 'minor', 'street', 'street_limited', 'service'], true, false];
    } else if (scope === 'major') {
      scopeFilter = ['match', roadClass, ['motorway', 'trunk', 'primary'], true, false];
    } else if (scope === 'interstates') {
      scopeFilter = ['==', ['get', 'network'], 'us-interstate'];
    } else {
      scopeFilter = ['all', ['==', ['get', 'network'], 'us-interstate'], ['==', ['get', 'ref'], '95']];
    }
    return ['all', lineGeometry, scopeFilter];
  }

  function isStreetStyleRoadLayer(layer) {
    return layer.source === 'openmaptiles'
      && (layer['source-layer'] === 'transportation' || layer['source-layer'] === 'transportation_name');
  }

  function applyNeonStreetLayer(map) {
    const enabled = document.getElementById('show-neon-streets')?.checked ?? false;
    const shownAtZoom = layerShownAtZoom('neon-streets', map.getZoom());
    const streetBaseVisible = activeBaseLayerId() === 'street-map';
    const style = map.getStyle();
    if (!style?.layers) return;
    const styleLayersById = new Map(style.layers.map((layer) => [layer.id, layer]));
    streetStyleLayerIds.forEach((layerId) => {
      const layer = styleLayersById.get(layerId);
      if (!layer || !isStreetStyleRoadLayer(layer)) return;
      map.setLayoutProperty(layerId, 'visibility', streetBaseVisible && !enabled ? 'visible' : 'none');
    });
    if (!map.getSource('openmaptiles')) return;

    const firstLabel = style.layers.find((layer) => layer.type === 'symbol' && streetStyleLayerIds.includes(layer.id))?.id;
    const color = layerCustomColors.get('neon-streets') || '#00eaff';
    const filter = neonStreetFilter();
    if (!map.getLayer(NEON_STREET_GLOW_LAYER_ID)) {
      map.addLayer({
        id: NEON_STREET_GLOW_LAYER_ID,
        type: 'line',
        source: 'openmaptiles',
        'source-layer': 'transportation_name',
        filter,
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: {
          'line-color': color,
          'line-width': scaledLineWidth(['interpolate', ['exponential', 1.35], ['zoom'], 5, 3, 9, 5, 13, 10, 17, 22], layerFilters.neonStreets.lineWidth),
          'line-blur': ['interpolate', ['linear'], ['zoom'], 5, 2, 12, 4, 17, 8],
          'line-opacity': .72,
        },
      }, firstLabel);
    }
    if (!map.getLayer(NEON_STREET_CORE_LAYER_ID)) {
      map.addLayer({
        id: NEON_STREET_CORE_LAYER_ID,
        type: 'line',
        source: 'openmaptiles',
        'source-layer': 'transportation_name',
        filter,
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: {
          'line-color': '#e8ffff',
          'line-width': scaledLineWidth(['interpolate', ['exponential', 1.3], ['zoom'], 5, .8, 9, 1.15, 13, 2.2, 17, 5], layerFilters.neonStreets.lineWidth),
          'line-opacity': .98,
        },
      }, firstLabel);
    }
    if (!map.getLayer(NEON_STREET_LABEL_LAYER_ID)) {
      map.addLayer({
        id: NEON_STREET_LABEL_LAYER_ID,
        type: 'symbol',
        source: 'openmaptiles',
        'source-layer': 'transportation_name',
        filter: neonStreetFilter(),
        minzoom: 6,
        layout: {
          'symbol-placement': 'line',
          'symbol-spacing': 520,
          'text-field': ['case', ['==', ['get', 'network'], 'us-interstate'], ['concat', 'I-', ['get', 'ref']], ['coalesce', ['get', 'ref'], ['get', 'name']]],
          'text-font': ['Noto Sans Bold'],
          'text-size': ['interpolate', ['linear'], ['zoom'], 6, 10, 13, 13, 17, 16],
          'text-keep-upright': true,
        },
        paint: {
          'text-color': '#f2ffff',
          'text-halo-color': color,
          'text-halo-width': 2.4,
          'text-halo-blur': 1.2,
        },
      }, firstLabel);
    }
    [NEON_STREET_GLOW_LAYER_ID, NEON_STREET_CORE_LAYER_ID, NEON_STREET_LABEL_LAYER_ID].forEach((layerId) => {
      map.setFilter(layerId, filter);
      map.setLayoutProperty(layerId, 'visibility', enabled && shownAtZoom ? 'visible' : 'none');
    });
    applyMapLayerOrder(map);
    map.setPaintProperty(NEON_STREET_GLOW_LAYER_ID, 'line-color', color);
    map.setPaintProperty(NEON_STREET_GLOW_LAYER_ID, 'line-width', scaledLineWidth(['interpolate', ['exponential', 1.35], ['zoom'], 5, 3, 9, 5, 13, 10, 17, 22], layerFilters.neonStreets.lineWidth));
    map.setPaintProperty(NEON_STREET_CORE_LAYER_ID, 'line-width', scaledLineWidth(['interpolate', ['exponential', 1.3], ['zoom'], 5, .8, 9, 1.15, 13, 2.2, 17, 5], layerFilters.neonStreets.lineWidth));
    map.setPaintProperty(NEON_STREET_LABEL_LAYER_ID, 'text-halo-color', color);
    const labels = { i95: 'I-95', interstates: 'All interstates', major: 'Major roads', all: 'All streets' };
    document.getElementById('neon-streets-status').textContent = enabled
      ? shownAtZoom
        ? `${labels[layerFilters.neonStreets.scope] || labels.i95} · neon route overlay`
        : `Visible only from zoom ${zoomRangeLabel('neon-streets')}`
      : 'Off · OpenFreeMap road overlay';
  }

  function drawExportDataCenterMarkers(map, context, scaleX, scaleY) {
    const containerRect = map.getContainer().getBoundingClientRect();
    let count = 0;
    map.getContainer().querySelectorAll('.dc-map-marker--center:not([hidden])').forEach((marker) => {
      const rect = marker.getBoundingClientRect();
      const x = ((rect.left + rect.width / 2) - containerRect.left) * scaleX;
      const y = ((rect.top + rect.height / 2) - containerRect.top) * scaleY;
      if (x < 0 || y < 0 || x > context.canvas.width || y > context.canvas.height) return;
      const size = Math.max(18 * scaleX, rect.width * scaleX);
      const outline = marker.dataset.exportOutline || '#ffffff';
      let colors = ['#657887'];
      try {
        colors = JSON.parse(marker.dataset.exportColors || '[]').filter((color) => /^#[0-9a-f]{6}$/i.test(color));
      } catch (_error) {
        colors = ['#657887'];
      }
      if (!colors.length) colors = ['#657887'];

      context.save();
      context.translate(x, y);
      const glowColor = /^#[0-9a-f]{6}$/i.test(marker.dataset.exportGlowColor || '')
        ? marker.dataset.exportGlowColor
        : null;
      const glowEdgeColor = /^#[0-9a-f]{6}$/i.test(marker.dataset.exportGlowEdgeColor || '')
        ? marker.dataset.exportGlowEdgeColor
        : glowColor;
      const glowOpacity = Math.max(0, Math.min(1, Number(marker.dataset.exportGlowOpacity) || 0));
      const glowScale = Math.max(.1, Number(marker.dataset.exportGlowScale) || 1);
      const glowBlur = normalizeGlowBlur(marker.dataset.exportGlowBlur);
      const glowRingWidth = Math.max(0, Math.min(.25, Number(marker.dataset.exportGlowRingWidth) || 0));
      if (glowColor && glowOpacity > 0) {
        const rgb = hexToRgb(glowColor);
        const edgeRgb = hexToRgb(glowEdgeColor || glowColor);
        const radius = size * glowScale / 2;
        const midStop = Math.max(.14, Math.min(.34, .18 + (glowBlur * .05)));
        const fadeStop = Math.max(.4, Math.min(.78, .5 + (glowBlur * .08)));
        const glow = context.createRadialGradient(0, 0, size * .12, 0, 0, radius);
        glow.addColorStop(0, `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, ${glowOpacity})`);
        glow.addColorStop(midStop, `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, ${glowOpacity * .5})`);
        glow.addColorStop(fadeStop, `rgba(${edgeRgb.r}, ${edgeRgb.g}, ${edgeRgb.b}, ${glowOpacity * .22})`);
        glow.addColorStop(1, `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 0)`);
        context.fillStyle = glow;
        context.beginPath();
        context.arc(0, 0, radius, 0, Math.PI * 2);
        context.fill();
        if (glowRingWidth > 0) {
          context.strokeStyle = `rgba(${edgeRgb.r}, ${edgeRgb.g}, ${edgeRgb.b}, ${Math.min(1, glowOpacity * .92)})`;
          context.lineWidth = Math.max(1, size * glowRingWidth);
          context.beginPath();
          context.arc(0, 0, Math.max(1, radius - (context.lineWidth / 2)), 0, Math.PI * 2);
          context.stroke();
        }
      }
      context.shadowColor = 'rgba(0, 0, 0, .72)';
      context.shadowBlur = size * .2;
      context.shadowOffsetY = size * .08;
      const outer = context.createLinearGradient(-size / 2, -size / 2, size / 2, size / 2);
      outer.addColorStop(0, '#31557b');
      outer.addColorStop(.56, '#102b4b');
      outer.addColorStop(1, '#061423');
      context.fillStyle = outer;
      context.strokeStyle = outline;
      context.lineWidth = Math.max(2, size * .085);
      context.beginPath();
      context.roundRect(-size / 2, -size / 2, size, size, size * .15);
      context.fill();
      context.stroke();
      context.shadowColor = 'transparent';

      const rackWidth = size * .52;
      const rackHeight = size * .62;
      context.fillStyle = '#071b30';
      context.beginPath();
      context.roundRect(-rackWidth / 2, -rackHeight / 2, rackWidth, rackHeight, size * .06);
      context.fill();
      const bayHeight = rackHeight / 3.8;
      for (let bay = 0; bay < 3; bay += 1) {
        const top = (-rackHeight / 2) + (bay * rackHeight / 3) + size * .045;
        const fill = context.createLinearGradient(-rackWidth / 2, top, rackWidth / 2, top + bayHeight);
        const color = colors[bay % colors.length];
        fill.addColorStop(0, adjustHexColor(color, 1.35));
        fill.addColorStop(1, adjustHexColor(color, .62));
        context.fillStyle = fill;
        context.fillRect(-rackWidth * .4, top, rackWidth * .8, bayHeight);
        context.fillStyle = '#dff8ff';
        context.beginPath();
        context.arc(rackWidth * .27, top + bayHeight / 2, Math.max(1.2, size * .035), 0, Math.PI * 2);
        context.fill();
      }
      context.restore();
      count += 1;
    });
    return count;
  }

  function drawExportPowerPlantMarkers(map, context, scaleX, scaleY) {
    const entries = powerPlantBoltLayer?.getExportEntries?.() || [];
    let count = 0;
    entries.forEach((entry) => {
      const projected = map.project([entry.longitude, entry.latitude]);
      const x = projected.x * scaleX;
      const y = projected.y * scaleY;
      if (x < 0 || y < 0 || x > context.canvas.width || y > context.canvas.height) return;
      const height = Math.max(25 * scaleY, entry.size * scaleY);
      const width = height * .54;
      const fillFraction = Math.max(0, Math.min(1, Number(entry.fillFraction) || 0));
      context.save();
      context.translate(x, y);
      context.beginPath();
      context.moveTo(-.20 * width, -.50 * height);
      context.lineTo(.14 * width, -.50 * height);
      context.lineTo(.03 * width, -.14 * height);
      context.lineTo(.30 * width, -.14 * height);
      context.lineTo(-.07 * width, .50 * height);
      context.lineTo(.02 * width, .12 * height);
      context.lineTo(-.24 * width, .12 * height);
      context.closePath();
      context.clip();
      context.beginPath();
      context.rect(-width, (.5 - fillFraction) * height, width * 2, height * fillFraction);
      context.clip();
      context.beginPath();
      context.moveTo(-.20 * width, -.50 * height);
      context.lineTo(.14 * width, -.50 * height);
      context.lineTo(.03 * width, -.14 * height);
      context.lineTo(.30 * width, -.14 * height);
      context.lineTo(-.07 * width, .50 * height);
      context.lineTo(.02 * width, .12 * height);
      context.lineTo(-.24 * width, .12 * height);
      context.closePath();
      context.shadowColor = entry.accent;
      context.shadowBlur = height * .2;
      context.shadowOffsetY = height * .025;
      context.fillStyle = entry.accent;
      context.fill();
      context.strokeStyle = entry.accent;
      context.lineWidth = Math.max(2, height * .045);
      context.lineJoin = 'round';
      context.stroke();
      context.restore();
      count += 1;
    });
    return count;
  }

  function drawExportMapTitle(context, title, scaleX, scaleY) {
    if (!title) return false;
    const paddingX = 18 * scaleX;
    const paddingY = 10 * scaleY;
    const maxWidth = context.canvas.width * .78;
    let fontSize = 20 * Math.min(scaleX, scaleY);
    context.save();
    context.font = `700 ${fontSize}px Mattone, Arial, sans-serif`;
    while (fontSize > 12 * Math.min(scaleX, scaleY) && context.measureText(title).width > maxWidth - paddingX * 2) {
      fontSize -= Math.min(scaleX, scaleY);
      context.font = `700 ${fontSize}px Mattone, Arial, sans-serif`;
    }
    const width = Math.min(maxWidth, context.measureText(title).width + paddingX * 2);
    const height = fontSize + paddingY * 2;
    const left = (context.canvas.width - width) / 2;
    const top = 14 * scaleY;
    context.fillStyle = 'rgba(0, 29, 67, .9)';
    context.strokeStyle = 'rgba(143, 210, 237, .85)';
    context.lineWidth = Math.max(2, scaleX);
    context.beginPath();
    context.roundRect(left, top, width, height, 6 * scaleX);
    context.fill();
    context.stroke();
    context.fillStyle = '#f8fbff';
    context.textAlign = 'center';
    context.textBaseline = 'middle';
    context.fillText(title, context.canvas.width / 2, top + height / 2, width - paddingX * 2);
    context.restore();
    return true;
  }

  function downloadMapPng(map) {
    const button = document.getElementById('download-map-png');
    const status = document.getElementById('map-download-status');
    const boltLayerVisible = Boolean(map.getLayer(POWER_PLANT_WEBGL_LAYER_ID))
      && map.getLayoutProperty(POWER_PLANT_WEBGL_LAYER_ID, 'visibility') !== 'none';
    button.disabled = true;
    status.textContent = 'Preparing high-resolution map PNG.';
    if (boltLayerVisible) map.setLayoutProperty(POWER_PLANT_WEBGL_LAYER_ID, 'visibility', 'none');
    map.triggerRepaint();
    requestAnimationFrame(() => requestAnimationFrame(() => {
      try {
        const source = map.getCanvas();
        const output = document.createElement('canvas');
        output.width = source.width;
        output.height = source.height;
        const context = output.getContext('2d');
        context.fillStyle = '#002a61';
        context.fillRect(0, 0, output.width, output.height);
        context.drawImage(source, 0, 0);
        if (boltLayerVisible) map.setLayoutProperty(POWER_PLANT_WEBGL_LAYER_ID, 'visibility', 'visible');
        const scaleX = output.width / source.clientWidth;
        const scaleY = output.height / source.clientHeight;
        const dataCenterMarkerCount = drawExportDataCenterMarkers(map, context, scaleX, scaleY);
        const powerPlantMarkerCount = drawExportPowerPlantMarkers(map, context, scaleX, scaleY);
        const mapTitle = document.getElementById('show-map-title').checked
          ? (document.getElementById('map-title-input').value.trim() || 'Infrastructure map')
          : '';
        const titleRendered = drawExportMapTitle(context, mapTitle, scaleX, scaleY);

        const attribution = map.getContainer().querySelector('.maplibregl-ctrl-attrib')?.textContent
          ?.replace(/\s+/g, ' ').trim();
        if (attribution) {
          const fontSize = Math.max(18, Math.round(output.width / 90));
          const padding = Math.round(fontSize * .65);
          const barHeight = fontSize + padding * 2;
          context.font = `${fontSize}px sans-serif`;
          context.fillStyle = 'rgba(0, 29, 67, .86)';
          context.fillRect(0, output.height - barHeight, output.width, barHeight);
          context.fillStyle = '#f8fbff';
          context.textBaseline = 'middle';
          context.fillText(attribution, padding, output.height - barHeight / 2, output.width - padding * 2);
        }

        output.toBlob((blob) => {
          if (!blob) {
            button.disabled = false;
            status.textContent = 'PNG download failed: encoding returned no data.';
            return;
          }
          const url = URL.createObjectURL(blob);
          const link = document.createElement('a');
          link.href = url;
          link.download = `maryland-infrastructure-map-z${map.getZoom().toFixed(2)}.png`;
          link.click();
          setTimeout(() => URL.revokeObjectURL(url), 1000);
          button.disabled = false;
          status.textContent = `PNG downloaded at ${output.width} by ${output.height} pixels.`;
          window.__lastMapExportDiagnostics = {
            width: output.width,
            height: output.height,
            pixelRatio: scaleX,
            dataCenterMarkerCount,
            powerPlantMarkerCount,
            titleRendered,
            title: mapTitle,
          };
        }, 'image/png');
      } catch (error) {
        if (boltLayerVisible && map.getLayer(POWER_PLANT_WEBGL_LAYER_ID)) {
          map.setLayoutProperty(POWER_PLANT_WEBGL_LAYER_ID, 'visibility', 'visible');
        }
        button.disabled = false;
        status.textContent = `PNG download failed: ${error.message}`;
      }
    }));
  }

  function setupBaseLayerControls(map) {
    document.querySelectorAll('.dc-base-layer-toggle').forEach((input) => {
      input.addEventListener('change', () => {
        if (input.checked) {
          document.querySelectorAll('.dc-base-layer-toggle').forEach((other) => {
            if (other !== input) other.checked = false;
          });
        }
        applyBaseLayerState(map);
        persistUiState(map);
      });
    });
  }

  Promise.all(Object.entries(DATA_URLS).map(async ([key, url]) => {
    const response = await fetch(url, { cache: 'no-store' });
    if (!response.ok) throw new Error(`${url}: HTTP ${response.status}`);
    return [key, await response.json()];
  }))
    .then((entries) => initialize(Object.fromEntries(entries)))
    .catch((error) => {
      document.getElementById('record-detail').innerHTML = `<h2>Data unavailable</h2><p>${escapeHtml(error.message)}</p>`;
    });

  function initialize(data) {
    const sourceById = new Map(data.sources.map((source) => [source.id, source]));
    const themeSelect = document.getElementById('map-theme');
    const restoredUiState = readUiState();
    document.getElementById('close-record-detail').addEventListener('click', closePinnedInspector);
    if (restoredUiState.theme && BASEMAP_STYLES[restoredUiState.theme]) themeSelect.value = restoredUiState.theme;
    const map = new maplibregl.Map({
      container: 'datacenter-map',
      style: BASEMAP_STYLES[themeSelect.value],
      center: Array.isArray(restoredUiState.center) ? restoredUiState.center : [-76.75, 39.05],
      zoom: 7.25,
      maxZoom: 18,
      pixelRatio: Math.max(window.devicePixelRatio || 1, 3),
      antialias: true,
      preserveDrawingBuffer: true,
      attributionControl: false,
    });
    if (Number.isFinite(restoredUiState.zoom)) map.setZoom(restoredUiState.zoom);
    if (restoredUiState.orientation) {
      if (Number.isFinite(restoredUiState.orientation.bearing)) map.setBearing(restoredUiState.orientation.bearing);
      if (Number.isFinite(restoredUiState.orientation.pitch)) map.setPitch(restoredUiState.orientation.pitch);
    }
    window.__codeCollectiveDatacenterMap = map;
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-left');
    map.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-right');
    document.getElementById('download-map-png').addEventListener('click', () => downloadMapPng(map));
    map.on('style.load', () => {
      streetStyleLayerIds = map.getStyle().layers.map((layer) => layer.id);
      if (themeSelect.value === 'collective') applyCollectiveTheme(map);
      applyBaseLayerState(map);
      if (document.getElementById('show-enviroscreen').checked) setEnviroScreenVisibility(map, true);
      if (document.getElementById('show-parcels').checked) setParcelVisibility(map, true);
      restoreRemoteLayers(map);
      updateEsriBuildingsLayer(map);
      ensurePowerPlantBoltLayer(map);
      powerPlantBoltLayer?.setRecords(allRecords.filter((record) => record.record_type === 'power_plant' && matchesFilters(record)));
      renderLayerOrderControls(map);
    });
    themeSelect.addEventListener('change', () => {
      map.setStyle(BASEMAP_STYLES[themeSelect.value]);
    });

    const markerById = new Map();
    const entityImageByRecordId = new Map((data.entityImages || [])
      .map((image) => [image.record_id || image.plant_id, image]));
    const allRecords = data.infrastructure.map((record) => ({
      ...record,
      entity_image: record.entity_image || entityImageByRecordId.get(record.id) || null,
    }));
    const dataCenters = allRecords.filter((record) => record.record_type === 'data_center');
    const powerPlants = allRecords.filter((record) => record.record_type === 'power_plant');
    setupRemoteLayerControls(map);
    setupEsriBuildingsControl(map);
    setupBaseLayerControls(map);
    applyUiState(restoredUiState, themeSelect);
    refreshLayerZoomBadges();
    setupMapTitleControls(map);

    dataCenters.forEach((record) => {
      if (!Number.isFinite(record.latitude) || !Number.isFinite(record.longitude)) return;
      const sourceCodes = markerSourceCodes(record);
      const element = document.createElement('button');
      element.type = 'button';
      element.className = 'dc-map-marker dc-map-marker--center';
      element.setAttribute('aria-label', record.name);
      element.dataset.recordId = record.id;
      element.dataset.energySources = sourceCodes.length ? sourceCodes.join(' ') : 'UNKNOWN';
      element.innerHTML = '<span class="dc-map-icon dc-map-icon--center"></span>';
      applyMarkerAppearance(record, element);
      element.addEventListener('click', (event) => {
        event.stopPropagation();
        pinHoverTarget({
          kind: 'data-center',
          key: `record:${record.id}`,
          layerId: 'datacenters',
          record,
          render: () => selectRecord(record, sourceById),
        });
      });
      element.addEventListener('focus', () => selectHoveredRecord(record, sourceById));
      element.addEventListener('blur', clearInspectorHover);
      const marker = new maplibregl.Marker({
        element,
        anchor: 'center',
        subpixelPositioning: true,
      })
        .setLngLat([record.longitude, record.latitude])
        .setSubpixelPositioning(true)
        .addTo(map);
      markerById.set(record.id, marker);
    });

    document.getElementById('datacenter-layer-count').textContent = number(dataCenters.length);
    document.getElementById('power-plant-layer-count').textContent = number(powerPlants.length);
    setupLayerCardPreviews();
    setupLayerOrdering(map);
    document.getElementById('show-datacenters').addEventListener('change', () => renderResults(allRecords, markerById));
    document.getElementById('show-power-plants').addEventListener('change', () => renderResults(allRecords, markerById));
    document.getElementById('show-neon-streets').addEventListener('change', () => {
      applyNeonStreetLayer(map);
      persistUiState(map);
    });
    document.getElementById('show-enviroscreen').addEventListener('change', (event) => {
      setEnviroScreenVisibility(map, event.target.checked);
    });
    document.getElementById('show-parcels').addEventListener('change', (event) => {
      setParcelVisibility(map, event.target.checked);
    });
    document.getElementById('hover-parcels').addEventListener('change', (event) => {
      if (!event.target.checked) {
        clearTimeout(parcelHoverTimer);
        parcelHoverAbort?.abort();
        clearParcelHighlight(map);
        map.getCanvas().style.cursor = '';
      }
      updateParcelStatus(map);
    });
    document.getElementById('layer-search').addEventListener('input', (event) => {
      layerSearch = event.target.value.trim().toLowerCase();
      filterLayerCards(layerSearch);
      persistUiState();
    });
    setupLayerFilterUi(map, allRecords, markerById);
    setupLayerColorUi();
    setupTagFilterUi();
    setupUiStatePersistence(map);

    renderResults(allRecords, markerById);
    filterLayerCards(layerSearch);
    renderSources(data.sources);
    map.on('mousemove', (event) => handleMapHover(map, event, sourceById));
    window.__resolveDatacenterHoverTargets = (point) => {
      topMapHoverTarget(map, new maplibregl.Point(point.x, point.y), sourceById);
      return window.__lastHoverArbitration;
    };
    map.on('click', (event) => handleMapClick(map, event, sourceById));
    map.getCanvas().addEventListener('mouseleave', () => {
      updateHoveredDataCenterMarker(null);
      powerPlantBoltLayer?.setHoveredRecord(null);
      clearInspectorHover();
    });
    map.on('moveend', () => {
      applyZoomVisibility(map, allRecords, markerById);
    });
    if (map.loaded()) {
      streetStyleLayerIds = map.getStyle().layers.map((layer) => layer.id);
      applyBaseLayerState(map);
      if (document.getElementById('show-enviroscreen').checked) setEnviroScreenVisibility(map, true);
      if (document.getElementById('show-parcels').checked) setParcelVisibility(map, true);
      restoreRemoteLayers(map);
      ensurePowerPlantBoltLayer(map);
      powerPlantBoltLayer?.setRecords(allRecords.filter((record) => record.record_type === 'power_plant' && matchesFilters(record)));
      renderLayerOrderControls(map);
    }
    persistUiState(map);
    window.__codeCollectiveDatacenterUiReady = true;
  }

  function remoteSourceId(config) {
    return `remote-${config.id}`;
  }

  function remoteRenderLayerIds(config) {
    const sourceId = remoteSourceId(config);
    if (config.geometry === 'point') return [`${sourceId}-point`];
    if (config.geometry === 'line') return [`${sourceId}-line`];
    return [`${sourceId}-fill`, `${sourceId}-line`];
  }

  function remoteRequestPrecision(zoom) {
    if (zoom < 5) return 1;
    if (zoom < 8) return 2;
    return 3;
  }

  function remoteService(config, zoom) {
    if (!config.services) return config.service;
    return config.services.find(([minimumZoom]) => zoom >= minimumZoom)?.[1]
      || config.services[config.services.length - 1][1];
  }

  function remoteMaxAllowableOffset(config, zoom) {
    const normalizedZoom = Math.max(0, zoom - 6);
    if (config.geometry === 'polygon') return Math.max(.00005, .012 / (2 ** normalizedZoom));
    if (config.geometry === 'line') return Math.max(.00002, .006 / (2 ** normalizedZoom));
    return Math.max(.000005, .003 / (2 ** Math.max(0, zoom - 7)));
  }

  function remoteResultRecordCount(config, zoom) {
    if (config.maxFeatures) return String(config.maxFeatures);
    if (config.geometry === 'point') return '2000';
    if (zoom < 5) return '1200';
    if (zoom < 8) return '1600';
    return '2000';
  }

  function setupRemoteLayerControls(map) {
    const container = document.getElementById('remote-layer-controls');
    container.innerHTML = REMOTE_LAYERS.map((config) => `
      <div class="dc-layer-option dc-layer-option--remote" data-layer-preview="${escapeHtml(config.id)}">
        <div class="dc-layer-toprow">
          <span class="dc-layer-name"><strong>${escapeHtml(config.name)}</strong><small>${escapeHtml(config.description)}</small></span>
          <span class="dc-layer-controls-row">
            <button class="dc-layer-color" type="button" data-layer-color="${escapeHtml(config.id)}" aria-label="Change ${escapeHtml(config.name)} color" title="Change layer color"><i class="dc-layer-symbol" style="--layer-color: ${config.color}" aria-hidden="true"></i></button>
            <span class="dc-layer-zoom" data-layer-zoom="${escapeHtml(config.id)}">z ${escapeHtml(zoomRangeLabel(config.id))}</span>
            <label class="dc-layer-toggle"><input id="show-${config.id}" type="checkbox"> Render</label>
            <label class="dc-layer-toggle"><input id="hover-${config.id}" type="checkbox" checked> Hover</label>
            ${config.focus ? `<button class="dc-layer-locate" type="button" data-layer-locate="${escapeHtml(config.id)}" aria-label="Zoom to ${escapeHtml(config.name)} coverage" title="Zoom to layer coverage">⌖</button>` : ''}
            <button class="dc-layer-gear" type="button" data-layer-config="${escapeHtml(config.id)}" aria-label="Configure ${escapeHtml(config.name)} layer">⚙</button>
          </span>
        </div>
        <p id="status-${config.id}" class="dc-layer-status" aria-live="polite">${escapeHtml(config.statusOffText || 'Off · live official service')}</p>
      </div>`).join('');

    REMOTE_LAYERS.forEach((config) => {
      remoteLayerStates.set(config.id, {
        enabled: false,
        data: null,
        filteredData: null,
        abort: null,
        requestKey: '',
        text: '',
        sizeBy: config.defaultSizeBy || 'none',
        colorTheme: config.lineColorThemes ? 'uniform' : 'default',
        lineWidth: 1,
        lineWidthBy: 'zoom',
      });
      layerPreviewSearchIndex.set(config.id, [
        config.name,
        config.description,
        config.category,
        ...(config.tags || []),
        config.sourceLabel,
      ].filter(Boolean).join(' ').toLowerCase());
      document.getElementById(`show-${config.id}`).addEventListener('change', (event) => {
        const state = remoteLayerStates.get(config.id);
        state.enabled = event.target.checked;
        setRemoteLayerVisibility(map, config, state.enabled);
      });
      document.querySelector(`[data-layer-locate="${config.id}"]`)?.addEventListener('click', () => {
        map.easeTo({ center: config.focus.center, zoom: config.focus.zoom, duration: 700 });
      });
    });
  }

  function layerPreviewCategory(config) {
    if (config.category) return config.category;
    if (config.id.includes('load-capacity')) return 'Load-serving capacity';
    if (config.id.includes('generation-hosting')) return 'Generation interconnection capacity';
    if (config.id.includes('transmission')) return 'Transmission infrastructure';
    if (config.id.includes('substation')) return 'Substation infrastructure';
    return 'Live map service';
  }

  function layerPreviewStatus(config) {
    const status = config.statusId ? document.getElementById(config.statusId)?.textContent : null;
    if (status) return `${status.trim()}${config.statusSuffix || ''}`;
    return document.getElementById(`status-${config.id}`)?.textContent?.trim() || 'Ready';
  }

  function renderLayerCardPreview(config) {
    if (inspectorPinnedKey) return;
    const visible = document.getElementById(`show-${config.id}`)?.checked;
    const hover = document.getElementById(`hover-${config.id}`)?.checked;
    const detail = prepareInspectorDetail();
    detail.innerHTML = `
      <h2>${escapeHtml(config.name)}</h2>
      <p class="dc-type">${escapeHtml(layerPreviewCategory(config))} · ${visible ? 'visible' : 'hidden'}</p>
      <p>${escapeHtml(config.description)}</p>
      ${config.tags?.length ? `<p class="dc-record-note">Tags: ${escapeHtml(config.tags.join(', '))}</p>` : ''}
      ${renderFactGroup('Layer', [
        ['Visibility', visible ? 'On' : 'Off'],
        ['Map-feature hover', hover ? 'Enabled' : 'Disabled'],
        ['Current status', known(layerPreviewStatus(config))],
        ['Visible zoom range', known(zoomRangeLabel(config.id))],
      ])}
      <p class="dc-record-note">Hovering this card previews its purpose and state; it does not enable or query the layer.</p>
      <div class="dc-record-sources"><strong>Source</strong><ul><li><a href="${escapeHtml(config.sourceUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(config.sourceLabel)}</a></li></ul></div>`;
  }

  function setupLayerCardPreviews() {
    const previews = new Map([
      ...Object.entries(CORE_LAYER_PREVIEWS),
      ...REMOTE_LAYERS.map((config) => [config.id, config]),
      [ESRI_BUILDINGS.id, { ...ESRI_BUILDINGS, category: 'Streaming 3D reference' }],
    ]);
    previews.forEach((config, id) => {
      layerPreviewSearchIndex.set(id, [
        config.name,
        config.description,
        config.category,
        ...(config.tags || []),
        config.sourceLabel,
      ].filter(Boolean).join(' ').toLowerCase());
    });
    document.querySelectorAll('[data-layer-preview]').forEach((card) => {
      const preview = () => {
        const config = previews.get(card.dataset.layerPreview);
        if (config) renderLayerCardPreview(config);
      };
      card.addEventListener('pointerenter', preview);
      card.addEventListener('focusin', preview);
    });
  }

  function filterLayerCards(query) {
    const normalized = String(query || '').trim().toLowerCase();
    let visibleCount = 0;
    document.querySelectorAll('.dc-controls .dc-layer-option[data-layer-preview]').forEach((card) => {
      const indexedText = layerPreviewSearchIndex.get(card.dataset.layerPreview) || card.textContent.toLowerCase();
      const matches = !normalized || indexedText.includes(normalized);
      card.hidden = !matches;
      if (matches) visibleCount += 1;
    });
    document.getElementById('layer-search-empty').hidden = visibleCount > 0;
  }

  function setupEsriBuildingsControl(map) {
    const container = document.getElementById('remote-layer-controls');
    container.insertAdjacentHTML('afterbegin', `
      <div class="dc-layer-option dc-layer-option--remote" data-layer-preview="${ESRI_BUILDINGS.id}">
        <div class="dc-layer-toprow">
          <span class="dc-layer-name"><strong>${escapeHtml(ESRI_BUILDINGS.name)}</strong><small>${escapeHtml(ESRI_BUILDINGS.description)}</small></span>
          <span class="dc-layer-controls-row">
            <span class="dc-layer-color" aria-label="Source-textured 3D building color" title="Colors are supplied by the Esri scene"><i class="dc-layer-symbol" style="--layer-color: ${ESRI_BUILDINGS.color}" aria-hidden="true"></i></span>
            <span class="dc-layer-zoom" data-layer-zoom="${ESRI_BUILDINGS.id}">z ${escapeHtml(zoomRangeLabel(ESRI_BUILDINGS.id))}</span>
            <label class="dc-layer-toggle"><input id="show-${ESRI_BUILDINGS.id}" type="checkbox"> Render</label>
            <label class="dc-layer-toggle"><input id="hover-${ESRI_BUILDINGS.id}" type="checkbox" checked> Hover</label>
            <button class="dc-layer-locate" type="button" data-layer-locate="${ESRI_BUILDINGS.id}" aria-label="Zoom to Baltimore buildings" title="Zoom to Baltimore buildings">⌖</button>
            <button class="dc-layer-gear" type="button" data-layer-config="${ESRI_BUILDINGS.id}" aria-label="Configure ${escapeHtml(ESRI_BUILDINGS.name)} layer">⚙</button>
          </span>
        </div>
        <p id="status-${ESRI_BUILDINGS.id}" class="dc-layer-status" aria-live="polite">Off · live Esri scene service</p>
      </div>`);
    document.getElementById(`show-${ESRI_BUILDINGS.id}`).addEventListener('change', (event) => {
      esriBuildingsEnabled = event.target.checked;
      updateEsriBuildingsLayer(map);
    });
    document.querySelector(`[data-layer-locate="${ESRI_BUILDINGS.id}"]`).addEventListener('click', () => {
      map.easeTo({ ...ESRI_BUILDINGS.focus, duration: 900 });
    });
  }

  function esriBuildingProperties(object) {
    const attributes = object?.attributes || object?.properties || object || {};
    return Object.fromEntries(Object.entries(attributes)
      .filter(([, value]) => ['string', 'number', 'boolean'].includes(typeof value)));
  }

  function renderEsriBuildingDetail(info) {
    const object = info.object;
    const properties = esriBuildingProperties(object);
    const title = properties.name || properties.building || ESRI_BUILDINGS.name;
    const facts = [
      ['Building type', properties.building],
      ['Height', properties.height == null ? null : `${number(properties.height, 1)} m`],
      ['Levels', properties.building_levels],
      ['Feature source', properties.source],
      ['Object ID', properties.ObjectID],
      ['OpenStreetMap ID', properties.OSMID],
      ['Scene node', object.id],
      ['Mesh detail depth', object.depth],
      ['Tile geometry memory', object.gpuMemoryUsageInBytes == null ? null : `${number(object.gpuMemoryUsageInBytes / 1024, 0)} KiB`],
    ];
    const detail = prepareInspectorDetail();
    detail.innerHTML = `
      <h2>${escapeHtml(String(title))}</h2>
      <p class="dc-type">${escapeHtml(ESRI_BUILDINGS.name)} · live official scene service</p>
      ${renderFactGroup('Building mesh', facts.map(([label, value]) => [label, known(value)]))}
      <p class="dc-record-note">This 3D mesh streams directly from Esri for the current view. Feature attributes appear when supplied by the selected scene node.</p>
      <div class="dc-record-sources"><strong>Source</strong><ul><li><a href="${ESRI_BUILDINGS.sourceUrl}" target="_blank" rel="noopener noreferrer">${escapeHtml(ESRI_BUILDINGS.sourceLabel)}</a></li></ul></div>`;
  }

  function updateEsriBuildingsLayer(map) {
    const toggle = document.getElementById(`show-${ESRI_BUILDINGS.id}`);
    if (!toggle) return;
    esriBuildingsEnabled = toggle.checked;
    const status = document.getElementById(`status-${ESRI_BUILDINGS.id}`);
    if (!esriBuildingsEnabled) {
      deckHoverTarget = null;
      esriBuildingsOverlay?.setProps({ layers: [] });
      status.textContent = 'Off · live Esri scene service';
      return;
    }
    const range = zoomRangeForLayer(ESRI_BUILDINGS.id);
    if (!layerShownAtZoom(ESRI_BUILDINGS.id, map.getZoom())) {
      esriBuildingsOverlay?.setProps({ layers: [] });
      status.textContent = `Visible only from zoom ${number(range.min, 2)} through ${number(range.max, 2)}`;
      return;
    }
    if (!window.deck?.MapboxOverlay || !window.deck?.Tile3DLayer || !window.loaders?.I3SLoader) {
      status.textContent = '3D renderer unavailable';
      return;
    }
    if (!esriBuildingsOverlay) {
      esriBuildingsOverlay = new deck.MapboxOverlay({ interleaved: false, layers: [] });
      map.addControl(esriBuildingsOverlay);
    }
    status.textContent = 'Streaming buildings for current view…';
    esriBuildingsOverlay.setProps({
      layers: [new deck.Tile3DLayer({
        id: ESRI_BUILDINGS.id,
        data: ESRI_BUILDINGS.service,
        loader: loaders.I3SLoader,
        pickable: true,
        opacity: .88,
        onTilesetLoad: () => {
          if (esriBuildingsEnabled) status.textContent = 'Visible · live meshes · © Esri and contributors';
        },
        onHover: (info) => {
          if (!info.object || !document.getElementById(`hover-${ESRI_BUILDINGS.id}`).checked) {
            deckHoverTarget = null;
            clearInspectorHover('esri-building:');
            return;
          }
          const objectId = info.object.id ?? info.object.attributes?.OBJECTID ?? info.index;
          deckHoverTarget = {
            kind: 'esri-building',
            key: `esri-building:${objectId}`,
            layerId: ESRI_BUILDINGS.id,
            z: Number.MAX_SAFE_INTEGER - 1,
            render: () => renderEsriBuildingDetail(info),
          };
          showHoverTarget(map, deckHoverTarget);
        },
        onError: (error) => {
          status.textContent = `Scene service unavailable · ${error.message || error}`;
        },
      })],
    });
    applyMapLayerOrder(map);
  }

  function setRemoteLayerVisibility(map, config, enabled) {
    const state = remoteLayerStates.get(config.id);
    if (!state) return;
    state.enabled = enabled;
    if (!enabled) {
      state.abort?.abort();
      remoteRenderLayerIds(config).forEach((layerId) => {
        if (map.getLayer(layerId)) map.setLayoutProperty(layerId, 'visibility', 'none');
      });
      document.getElementById(`status-${config.id}`).textContent = config.statusOffText || 'Off · live official service';
      return;
    }
    loadRemoteLayer(map, config);
  }

  function scaleRemotePointData(config, data, sizeBy) {
    if (config.geometry !== 'point' || !sizeBy || sizeBy === 'none') return data;
    const properties = (data.features || []).map((feature) => feature.properties || {});
    const factors = pointScaleFactors(properties, sizeBy);
    return {
      ...data,
      features: (data.features || []).map((feature) => ({
        ...feature,
        properties: { ...feature.properties, _dcPointScale: factors.get(feature.properties || {}) || 1 },
      })),
    };
  }

  function remoteLineColor(config) {
    const selectedTheme = remoteLayerStates.get(config.id)?.colorTheme || (config.lineColorThemes ? 'uniform' : 'default');
    if (selectedTheme === 'uniform') return layerCustomColors.get(config.id) || config.lineColor || config.color;
    return config.lineColorThemes?.find((theme) => theme.id === selectedTheme)?.expression
      || config.lineColor
      || config.color;
  }

  function remoteLayerColor(config) {
    return layerCustomColors.get(config.id) || config.color;
  }

  function transmissionStatusExpression() {
    return ['downcase', ['to-string', ['coalesce', ['get', 'Status'], ['get', 'STATUS'], ['get', 'status'], ['get', 'Phase'], ['get', 'phase'], '']]];
  }

  function transmissionProposalExpression() {
    return ['match', transmissionStatusExpression(), ['proposed', 'proposal', 'planned', 'planning', 'pending', 'contested', 'under review', 'moratorium', 'paused'], true, false];
  }

  function transmissionLineColorExpression(config) {
    const baseColor = remoteLineColor(config);
    return config.id.includes('transmission')
      ? ['case', transmissionProposalExpression(), '#ff263f', baseColor]
      : baseColor;
  }

  function transmissionLineWidthExpression(config) {
    const remoteState = remoteLayerStates.get(config.id);
    const multiplier = remoteState?.lineWidth || 1;
    const lineWidthBy = normalizeLineWidthBy(config, remoteState?.lineWidthBy);
    if (lineWidthBy !== 'zoom') return lineWidthExpressionForField(lineWidthBy, multiplier);
    const base = ['interpolate', ['linear'], ['zoom'], config.minZoom, 1, 15, 4];
    return scaledLineWidth(base, multiplier);
  }

  function transmissionLineOpacityExpression(config) {
    if (!config.id.includes('transmission')) return .88;
    return ['case', transmissionProposalExpression(), 1, .88];
  }

  function transmissionLineBlurExpression(config) {
    if (!config.id.includes('transmission')) return 0;
    return ['case', transmissionProposalExpression(), 4.5, 0];
  }

  function addRemoteLayer(map, config, data) {
    if (!map.isStyleLoaded()) {
      window.setTimeout(() => addRemoteLayer(map, config, data), 250);
      return;
    }
    const state = remoteLayerStates.get(config.id);
    const query = state?.text?.trim().toLowerCase() || '';
    const filteredData = query ? {
      ...data,
      features: (data.features || []).filter((feature) => Object.values(feature.properties || {})
        .some((value) => String(value ?? '').toLowerCase().includes(query))),
    } : data;
    const visibleData = scaleRemotePointData(config, filteredData, state?.sizeBy);
    if (state) state.filteredData = visibleData;
    const sourceId = remoteSourceId(config);
    const existingSource = map.getSource(sourceId);
    if (existingSource) existingSource.setData(visibleData);
    else map.addSource(sourceId, { type: 'geojson', data: visibleData, attribution: config.attribution || config.sourceLabel });
    const firstLabel = map.getStyle().layers.find((layer) => layer.type === 'symbol')?.id;
    if (config.geometry === 'point') {
      const layerId = `${sourceId}-point`;
      if (!map.getLayer(layerId)) {
        map.addLayer(config.pointSymbol === 'interchange-arrow' ? {
          id: layerId,
          type: 'symbol',
          source: sourceId,
          layout: {
            'text-field': '➤',
            'text-size': ['interpolate', ['linear'], ['zoom'],
              5, ['*', 15, ['coalesce', ['get', '_dcPointScale'], 1]],
              9, ['*', 22, ['coalesce', ['get', '_dcPointScale'], 1]],
              14, ['*', 30, ['coalesce', ['get', '_dcPointScale'], 1]]],
            'text-rotate': ['+',
              ['coalesce', ['get', 'axis_rotation_degrees'], 0],
              ['case', ['==', ['downcase', ['coalesce', ['get', 'statewide_flow_direction'], '']], 'net import'], 0, 180]],
            'text-rotation-alignment': 'map',
            'text-pitch-alignment': 'map',
            'text-allow-overlap': true,
            'text-ignore-placement': true,
          },
          paint: {
            'text-color': remoteLayerColor(config),
            'text-halo-color': '#9b4c22',
            'text-halo-width': 2.2,
            'text-halo-blur': .35,
          },
        } : {
          id: layerId,
          type: 'circle',
          source: sourceId,
          paint: {
            'circle-radius': ['*', ['interpolate', ['linear'], ['zoom'], config.minZoom, 3.5, 14, 7], ['coalesce', ['get', '_dcPointScale'], 1]],
            'circle-color': remoteLayerColor(config),
            'circle-stroke-color': '#ffffff',
            'circle-stroke-width': 1.2,
            'circle-opacity': .84,
          },
        });
      }
      map.setPaintProperty(layerId, config.pointSymbol === 'interchange-arrow' ? 'text-color' : 'circle-color', remoteLayerColor(config));
    } else if (config.geometry === 'line') {
      const lineId = `${sourceId}-line`;
      if (!map.getLayer(lineId)) {
        map.addLayer({
          id: lineId,
          type: 'line',
          source: sourceId,
          paint: {
            'line-color': transmissionLineColorExpression(config),
            'line-width': transmissionLineWidthExpression(config),
            'line-opacity': transmissionLineOpacityExpression(config),
            'line-blur': transmissionLineBlurExpression(config),
          },
        });
      }
      map.setPaintProperty(lineId, 'line-color', transmissionLineColorExpression(config));
      map.setPaintProperty(lineId, 'line-width', transmissionLineWidthExpression(config));
      map.setPaintProperty(lineId, 'line-opacity', transmissionLineOpacityExpression(config));
      map.setPaintProperty(lineId, 'line-blur', transmissionLineBlurExpression(config));
    } else {
      const fillId = `${sourceId}-fill`;
      const lineId = `${sourceId}-line`;
      if (!map.getLayer(fillId)) {
        map.addLayer({
          id: fillId,
          type: 'fill',
          source: sourceId,
          paint: { 'fill-color': layerCustomColors.get(config.id) || config.fillColor || config.color, 'fill-opacity': config.fillOpacity ?? .3 },
        }, firstLabel);
      }
      if (!map.getLayer(lineId)) {
        map.addLayer({
          id: lineId,
          type: 'line',
          source: sourceId,
          paint: {
            'line-color': layerCustomColors.get(config.id) || config.lineColor || config.color,
            'line-width': config.lineWidth || 0,
            'line-opacity': config.lineOpacity ?? 0,
          },
        }, firstLabel);
      }
      map.setPaintProperty(fillId, 'fill-color', layerCustomColors.get(config.id) || config.fillColor || config.color);
      map.setPaintProperty(lineId, 'line-color', layerCustomColors.get(config.id) || config.lineColor || config.color);
    }
    remoteRenderLayerIds(config).forEach((layerId) => {
      if (!map.getLayer(layerId)) return;
      const range = zoomRangeForLayer(config.id);
      if (map.setLayerZoomRange) map.setLayerZoomRange(layerId, range.min, range.max);
      map.setLayoutProperty(layerId, 'visibility', layerShownAtZoom(config.id, map.getZoom()) ? 'visible' : 'none');
    });
    applyMapLayerOrder(map);
  }

  function remoteLayerRendered(map, config) {
    return remoteRenderLayerIds(config).some((layerId) => map.getLayer(layerId));
  }

  function hideRemoteLayer(map, config) {
    remoteRenderLayerIds(config).forEach((layerId) => {
      if (map.getLayer(layerId)) map.setLayoutProperty(layerId, 'visibility', 'none');
    });
  }

  function rehydrateRemoteLayerAfterStyleSettles(map, config) {
    [0, 250, 1000].forEach((delay) => {
      window.setTimeout(() => {
        const state = remoteLayerStates.get(config.id);
        if (!state?.enabled || !state.data) return;
        if (!map.isStyleLoaded()) return;
        if (!remoteLayerRendered(map, config)) addRemoteLayer(map, config, state.data);
      }, delay);
    });
  }

  function staticLayerLoadingText(config) {
    if (config.id === 'power-interchanges') return 'Loading documented transmission crossings…';
    if (config.id === 'county-power-estimates') return 'Loading county residential power estimates…';
    return `Loading ${config.name.toLowerCase()}…`;
  }

  function staticLayerStatus(config, data) {
    const featureCount = data?.features?.length || 0;
    if (config.id === 'power-interchanges') {
      const lineCount = data?.metadata?.line_crossing_count;
      return lineCount
        ? `${number(featureCount)} border corridors · ${number(lineCount)} line crossings · 2024 net import`
        : `${number(featureCount)} border corridors · 2024 Maryland net import`;
    }
    if (config.id === 'county-power-estimates') {
      const averageMw = data?.metadata?.statewide_residential_average_mw;
      const averageText = Number.isFinite(Number(averageMw)) ? ` · ${number(Number(averageMw), 1)} MW statewide residential average` : '';
      return `${number(featureCount)} counties · residential demand estimates${averageText}`;
    }
    return `${number(featureCount)} features`;
  }

  function staticLayerErrorText(config, error) {
    if (config.id === 'power-interchanges') return `Crossing inventory unavailable · ${error.message}`;
    if (config.id === 'county-power-estimates') return `County power estimates unavailable · ${error.message}`;
    return `${config.name} unavailable · ${error.message}`;
  }

  async function loadRemoteLayer(map, config) {
    const state = remoteLayerStates.get(config.id);
    if (!state?.enabled) return;
    const status = document.getElementById(`status-${config.id}`);
    const range = zoomRangeForLayer(config.id);
    const zoom = map.getZoom();
    if (!layerShownAtZoom(config.id, zoom)) {
      state.abort?.abort();
      hideRemoteLayer(map, config);
      status.textContent = `Visible only from zoom ${number(range.min, 2)} through ${number(range.max, 2)}`;
      return;
    }
    if (config.staticDataUrl) {
      if (state.data) {
        addRemoteLayer(map, config, state.data);
        rehydrateRemoteLayerAfterStyleSettles(map, config);
        status.textContent = staticLayerStatus(config, state.data);
        return;
      }
      state.abort?.abort();
      state.abort = new AbortController();
      status.textContent = staticLayerLoadingText(config);
      try {
        const response = await fetch(config.staticDataUrl, { cache: 'no-store', signal: state.abort.signal });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        if (!state.enabled) return;
        state.data = data;
        state.requestKey = config.staticDataUrl;
        addRemoteLayer(map, config, data);
        rehydrateRemoteLayerAfterStyleSettles(map, config);
        status.textContent = staticLayerStatus(config, data);
      } catch (error) {
        if (error.name === 'AbortError') return;
        status.textContent = staticLayerErrorText(config, error);
      }
      return;
    }
    if (zoom < range.min) {
      state.abort?.abort();
      hideRemoteLayer(map, config);
      status.textContent = `Zoom to level ${number(range.min, 2)} to query`;
      return;
    }

    const bounds = map.getBounds();
    const service = remoteService(config, zoom);
    const precision = remoteRequestPrecision(zoom);
    const requestKey = [service, [bounds.getWest(), bounds.getSouth(), bounds.getEast(), bounds.getNorth()]
      .map((value) => Number(value).toFixed(precision)).join(',')].join('|');
    if (requestKey === state.requestKey && state.data) {
      addRemoteLayer(map, config, state.data);
      rehydrateRemoteLayerAfterStyleSettles(map, config);
      return;
    }
    state.abort?.abort();
    state.abort = new AbortController();
    status.textContent = 'Querying current map view…';
    const parameters = new URLSearchParams({
      where: config.where || '1=1',
      geometry: `${bounds.getWest()},${bounds.getSouth()},${bounds.getEast()},${bounds.getNorth()}`,
      geometryType: 'esriGeometryEnvelope',
      inSR: '4326',
      spatialRel: 'esriSpatialRelIntersects',
      outFields: config.outFields.join(','),
      returnGeometry: 'true',
      outSR: '4326',
      geometryPrecision: '6',
      maxAllowableOffset: String(remoteMaxAllowableOffset(config, zoom)),
      resultRecordCount: remoteResultRecordCount(config, zoom),
      f: 'geojson',
    });
    try {
      const response = await fetch(`${service}/query?${parameters}`, { signal: state.abort.signal });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const responseData = await response.json();
      if (responseData.error) throw new Error(responseData.error.message || 'Service query failed');
      const returnedCount = responseData.features?.length || 0;
      const features = (responseData.features || []).filter((feature) => feature.geometry);
      if (returnedCount && !features.length) throw new Error('service returned records without map geometry');
      const data = { ...responseData, features };
      if (!state.enabled) return;
      state.data = data;
      state.requestKey = requestKey;
      addRemoteLayer(map, config, data);
      rehydrateRemoteLayerAfterStyleSettles(map, config);
      const count = data.features.length;
      status.textContent = data.exceededTransferLimit || count >= Number(remoteResultRecordCount(config, zoom))
        ? `${number(count)} features · zoom in for complete results`
        : `${number(count)} features in current view`;
    } catch (error) {
      if (error.name === 'AbortError') return;
      status.textContent = `Service unavailable · ${error.message}`;
    }
  }

  function refreshRemoteLayers(map) {
    REMOTE_LAYERS.forEach((config) => {
      if (remoteLayerStates.get(config.id)?.enabled) loadRemoteLayer(map, config);
    });
  }

  function restoreRemoteLayers(map) {
    REMOTE_LAYERS.forEach((config) => {
      const state = remoteLayerStates.get(config.id);
      if (!state?.enabled) return;
      if (state.data && layerShownAtZoom(config.id, map.getZoom())) addRemoteLayer(map, config, state.data);
      else loadRemoteLayer(map, config);
    });
  }

  function normalizeTagFilters(tags) {
    if (!Array.isArray(tags)) return [];
    return tags
      .map((tag) => String(tag || '').trim())
      .filter((tag, index, all) => tag && all.findIndex((candidate) => candidate.toLowerCase() === tag.toLowerCase()) === index);
  }

  function syncInspectorTagButtons() {
    document.querySelectorAll('[data-filter-tag]').forEach((button) => {
      const active = activeTagFilters.some((tag) => tag.toLowerCase() === button.dataset.filterTag.toLowerCase());
      button.setAttribute('aria-pressed', String(active));
    });
  }

  function renderActiveTagFilters() {
    const container = document.getElementById('active-tag-filters');
    const list = document.getElementById('active-tag-filter-list');
    const clear = document.getElementById('clear-tag-filters');
    const hasFilters = activeTagFilters.length > 0;
    container.classList.toggle('has-active-tags', hasFilters);
    clear.hidden = !hasFilters;
    document.querySelectorAll('[data-tag-filter-mode]').forEach((button) => {
      button.setAttribute('aria-pressed', String(button.dataset.tagFilterMode === tagFilterMode));
    });
    list.innerHTML = hasFilters
      ? activeTagFilters.map((tag) => `<button class="dc-active-tag" type="button" data-remove-tag="${escapeHtml(tag)}" aria-label="Remove ${escapeHtml(tag)} filter">${escapeHtml(tag)}</button>`).join('')
      : '<span class="dc-active-tag-empty">Click a tag in the inspector to filter the map.</span>';
    syncInspectorTagButtons();
  }

  function setTagFilter(tag, enabled) {
    const label = String(tag || '').trim();
    if (!label) return;
    activeTagFilters = enabled
      ? normalizeTagFilters([...activeTagFilters, label])
      : activeTagFilters.filter((candidate) => candidate.toLowerCase() !== label.toLowerCase());
    renderActiveTagFilters();
    applyAllLayerFilters();
  }

  function setupTagFilterUi() {
    document.getElementById('tag-filter-mode').addEventListener('click', (event) => {
      const button = event.target.closest('[data-tag-filter-mode]');
      if (!button || button.dataset.tagFilterMode === tagFilterMode) return;
      tagFilterMode = button.dataset.tagFilterMode;
      renderActiveTagFilters();
      applyAllLayerFilters();
    });
    document.getElementById('active-tag-filter-list').addEventListener('click', (event) => {
      const button = event.target.closest('[data-remove-tag]');
      if (button) setTagFilter(button.dataset.removeTag, false);
    });
    document.getElementById('clear-tag-filters').addEventListener('click', () => {
      activeTagFilters = [];
      renderActiveTagFilters();
      applyAllLayerFilters();
    });
    renderActiveTagFilters();
  }

  function bindInspectorTagFilters(detail) {
    detail.querySelectorAll('[data-filter-tag]').forEach((button) => {
      button.addEventListener('click', () => {
        const active = activeTagFilters.some((tag) => tag.toLowerCase() === button.dataset.filterTag.toLowerCase());
        setTagFilter(button.dataset.filterTag, !active);
      });
    });
    syncInspectorTagButtons();
  }

  const CORE_LAYER_DEFAULT_COLORS = {
    datacenters: '#c76522',
    'power-plants': '#167fc1',
    'neon-streets': '#00eaff',
    enviroscreen: '#01856f',
    parcels: '#79cff1',
  };

  function layerColorConfig(layerId) {
    return REMOTE_LAYERS.find((config) => config.id === layerId)
      || CORE_LAYER_PREVIEWS[layerId]
      || null;
  }

  function defaultLayerColor(layerId) {
    return CORE_LAYER_DEFAULT_COLORS[layerId]
      || REMOTE_LAYERS.find((config) => config.id === layerId)?.color
      || '#72b7d2';
  }

  function refreshLayerColorSwatches() {
    document.querySelectorAll('[data-layer-color]').forEach((button) => {
      const color = layerCustomColors.get(button.dataset.layerColor);
      button.classList.toggle('has-custom-color', Boolean(color));
      if (color) button.style.setProperty('--layer-custom-color', color);
      else button.style.removeProperty('--layer-custom-color');
      button.title = color ? `Custom layer color ${color.toUpperCase()}` : 'Change layer color';
    });
  }

  function refreshLayerZoomBadges() {
    document.querySelectorAll('[data-layer-zoom]').forEach((badge) => {
      const layerId = badge.dataset.layerZoom;
      badge.textContent = `z ${zoomRangeLabel(layerId)}`;
      badge.title = `Visible from zoom ${zoomRangeLabel(layerId)}`;
    });
  }

  function applyLayerColor(layerId) {
    refreshLayerColorSwatches();
    if (!activeLayerContext) return;
    const { map, records, markerById } = activeLayerContext;
    if (layerId === 'datacenters' || layerId === 'power-plants') renderResults(records, markerById);
    if (layerId === 'neon-streets') applyNeonStreetLayer(map);
    if (layerId === 'enviroscreen' && map.getLayer(ENVIROSCREEN_FILL_ID)) {
      addEnviroScreenLayers(map, enviroScreenData || { type: 'FeatureCollection', features: [] });
    }
    if (layerId === 'parcels' && map.getLayer(PARCEL_LAYER_ID)) {
      map.setPaintProperty(PARCEL_LAYER_ID, 'line-color', layerCustomColors.get('parcels') || 'rgba(121, 207, 241, .82)');
      ensureParcelHoverLayers(map, map.getStyle().layers.find((layer) => layer.type === 'symbol')?.id);
    }
    const remoteConfig = REMOTE_LAYERS.find((config) => config.id === layerId);
    const remoteState = remoteConfig && remoteLayerStates.get(layerId);
    if (remoteConfig && remoteState?.data) addRemoteLayer(map, remoteConfig, remoteState.data);
    persistUiState(map);
  }

  function openLayerColorModal(layerId) {
    const config = layerColorConfig(layerId);
    if (!config) return;
    activeLayerColorId = layerId;
    const color = layerCustomColors.get(layerId) || defaultLayerColor(layerId);
    document.getElementById('layer-color-title').textContent = `${config.name} color`;
    document.getElementById('layer-color-input').value = color;
    document.getElementById('layer-color-value').value = color.toUpperCase();
    document.getElementById('layer-color-help').textContent = layerCustomColors.has(layerId)
      ? 'A custom color overrides the source or semantic palette. Use source colors to restore the original styling.'
      : 'Choosing a color overrides the source or semantic palette for this layer.';
    document.getElementById('layer-color-modal').showModal();
  }

  function setupLayerColorUi() {
    document.querySelectorAll('[data-layer-color]').forEach((button) => {
      button.addEventListener('click', () => openLayerColorModal(button.dataset.layerColor));
    });
    const modal = document.getElementById('layer-color-modal');
    const input = document.getElementById('layer-color-input');
    input.addEventListener('input', () => {
      document.getElementById('layer-color-value').value = input.value.toUpperCase();
    });
    modal.addEventListener('click', (event) => {
      if (event.target === modal) modal.close('cancel');
    });
    document.getElementById('reset-layer-color').addEventListener('click', () => {
      if (!activeLayerColorId) return;
      layerCustomColors.delete(activeLayerColorId);
      applyLayerColor(activeLayerColorId);
      modal.close('reset');
    });
    document.getElementById('layer-color-form').addEventListener('submit', (event) => {
      event.preventDefault();
      if (event.submitter?.value === 'cancel') {
        modal.close('cancel');
        return;
      }
      if (activeLayerColorId && /^#[0-9a-f]{6}$/i.test(input.value)) {
        layerCustomColors.set(activeLayerColorId, input.value.toLowerCase());
        applyLayerColor(activeLayerColorId);
      }
      modal.close('apply');
    });
    refreshLayerColorSwatches();
  }

  function setupLayerFilterUi(map, records, markerById) {
    activeLayerContext = { map, records, markerById };
    document.querySelectorAll('.dc-layer-gear').forEach((button) => {
      button.addEventListener('click', () => openLayerFilterModal(button.dataset.layerConfig));
    });
    document.getElementById('reset-layer-filter').addEventListener('click', () => {
      if (!activeLayerConfigId) return;
      resetActiveLayerFilter();
      openLayerFilterModal(activeLayerConfigId);
      refreshLayerZoomBadges();
      applyAllLayerFilters();
    });
    const modal = document.getElementById('layer-filter-modal');
    modal.addEventListener('click', (event) => {
      if (event.target === modal) modal.close('cancel');
    });
    document.getElementById('layer-filter-form').addEventListener('submit', (event) => {
      event.preventDefault();
      if (event.submitter?.value === 'cancel') {
        modal.close('cancel');
        return;
      }
      applyActiveLayerFilter(new FormData(event.currentTarget));
      refreshLayerZoomBadges();
      modal.close('apply');
    });
  }

  function optionMarkup(options, selected) {
    return options.map(([value, label]) => `<option value="${escapeHtml(value)}"${value === selected ? ' selected' : ''}>${escapeHtml(label)}</option>`).join('');
  }

  function renderSearchInput(name, value, placeholder) {
    return `<input name="${escapeHtml(name)}" type="search" value="${escapeHtml(value)}" placeholder="${escapeHtml(placeholder)}">`;
  }

  function fieldMarkup(label, name, value, options = null, help = '') {
    return `<label class="dc-modal-field">${escapeHtml(label)}${options
      ? `<select name="${escapeHtml(name)}">${optionMarkup(options, value)}</select>`
      : renderSearchInput(name, value, 'Filter this layer…')}</label>${help ? `<p class="dc-modal-help">${escapeHtml(help)}</p>` : ''}`;
  }

  function numberFieldMarkup(label, name, value, { min = 0, max = 1, step = 0.01, help = '' } = {}) {
    return `<label class="dc-modal-field">${escapeHtml(label)}<input name="${escapeHtml(name)}" type="number" min="${escapeHtml(min)}" max="${escapeHtml(max)}" step="${escapeHtml(step)}" value="${escapeHtml(value)}"></label>${help ? `<p class="dc-modal-help">${escapeHtml(help)}</p>` : ''}`;
  }

  function zoomRangeMarkup(layerId) {
    const range = zoomRangeForLayer(layerId);
    return `<fieldset class="dc-modal-fieldset"><legend>Visible zoom range</legend>
      <div class="dc-modal-two-col">
        ${numberFieldMarkup('From zoom', 'zoomMin', range.min, { min: MAP_MIN_ZOOM, max: MAP_MAX_ZOOM, step: .25 })}
        ${numberFieldMarkup('Through zoom', 'zoomMax', range.max, { min: MAP_MIN_ZOOM, max: MAP_MAX_ZOOM, step: .25 })}
      </div>
      <p class="dc-modal-help">The map is currently capped at zoom ${MAP_MAX_ZOOM}. Outside this range the layer is hidden and live services are not queried.</p>
    </fieldset>`;
  }

  function applySubmittedZoomRange(layerId, formData) {
    if (!layerId) return;
    layerZoomRanges.set(layerId, normalizeZoomRange(formData.get('zoomMin'), formData.get('zoomMax'), defaultLayerZoomRange(layerId)));
  }

  function openLayerFilterModal(layerId) {
    activeLayerConfigId = layerId;
    const body = document.getElementById('layer-filter-body');
    let title = 'Layer filters';
    if (layerId === 'datacenters') {
      title = 'Data center layer filters';
      const filters = layerFilters.datacenters;
      const records = activeLayerContext.records.filter((record) => record.record_type === 'data_center');
      body.innerHTML = zoomRangeMarkup(layerId)
        + fieldMarkup('Facility text match', 'text', filters.text, null, 'Matches facility, operator, county, city, and technology fields in this layer.')
        + fieldMarkup('Lifecycle', 'status', filters.status, FILTER_OPTIONS.status)
        + fieldMarkup('Energy source', 'energy', filters.energy, FILTER_OPTIONS.energy)
        + fieldMarkup('Public response', 'sentiment', filters.sentiment, FILTER_OPTIONS.sentiment)
        + fieldMarkup('Power scale', 'powerScale', filters.powerScale, FILTER_OPTIONS.powerScale, 'Uses reported grid demand when available; otherwise a published capacity envelope is labeled as a proxy. Backup generation is excluded.')
        + fieldMarkup('Icon color uses', 'colorBy', filters.colorBy, FILTER_OPTIONS.datacenterIconColor)
        + fieldMarkup('Icon outline uses', 'outlineBy', filters.outlineBy, FILTER_OPTIONS.datacenterIconOutline)
        + fieldMarkup('Icon glow uses', 'glowBy', filters.glowBy, FILTER_OPTIONS.datacenterIconGlow, 'Strongly contested facilities glow red. Planned or developing facilities with no documented contestation glow yellow; quiet operating facilities glow white. Intermediate and unknown scores do not glow.')
        + numberFieldMarkup('Glow distance', 'glowDistance', normalizeGlowDistance(filters.glowDistance), { min: .35, max: 2.5, step: .05, help: 'Scales how far the glow extends from each data center icon.' })
        + numberFieldMarkup('Glow blur', 'glowBlur', normalizeGlowBlur(filters.glowBlur), { min: 0, max: 2.5, step: .05, help: 'Scales the softness of the glow edge.' })
        + fieldMarkup('Icon size uses', 'sizeBy', filters.sizeBy, dataCenterPointScaleOptions(records), 'Projected demand applies only to unbuilt facilities and uses planning estimates with explicit confidence. Net draw uses published normal grid demand. Total draw uses projected demand for unbuilt facilities and the best published capacity envelope otherwise; it is not measured consumption. Icons without the selected value use the smallest size.');
    } else if (layerId === 'power-plants') {
      title = 'Power plant layer filters';
      const records = activeLayerContext.records.filter((record) => record.record_type === 'power_plant');
      body.innerHTML = zoomRangeMarkup(layerId)
        + fieldMarkup('Plant text match', 'text', layerFilters.powerPlants.text, null, 'Matches plant, operator, county, city, and technology fields in this layer.')
        + fieldMarkup('Energy source', 'energy', layerFilters.powerPlants.energy, FILTER_OPTIONS.energy)
        + fieldMarkup('Icon color uses', 'colorBy', layerFilters.powerPlants.colorBy, FILTER_OPTIONS.plantIconColor)
        + fieldMarkup('Bolt outline uses', 'outlineBy', layerFilters.powerPlants.outlineBy, FILTER_OPTIONS.plantBoltOutline, 'A real silhouette outline is drawn independently from the fill. Choose Neutral light outline for a fixed pale border.')
        + fieldMarkup('Bolt fill uses', 'fillBy', layerFilters.powerPlants.fillBy || 'none', FILTER_OPTIONS.plantBoltFill, 'Fill the bolt from the bottom. Resource-adjusted annual utilization compares annual output to a technology-specific planning envelope, so solar and wind are not judged as if they should run at nameplate all year.')
        + numberFieldMarkup('Custom fill fraction', 'fillFraction', layerFilters.powerPlants.fillFraction ?? 1, { min: 0, max: 1, step: 0.01, help: 'Only used when Bolt fill uses is set to Custom fraction from bottom.' })
        + numberFieldMarkup('Bolt outline size', 'outlineScale', normalizeBoltOutlineScale(layerFilters.powerPlants.outlineScale), { min: .5, max: 2, step: 0.01, help: 'Scales the WebGL outline pass with fractional values. 1.04 is the compact default; use values below 1 for inset outlines or above 1 for stronger separation from imagery.' })
        + fieldMarkup('Icon size uses', 'sizeBy', layerFilters.powerPlants.sizeBy, numericPointScaleOptions(records, [['planning_sustained_output_mw', 'Planning output · annual average (MW)'], ['average_generation_mwh', 'Average generation / output (MWh)']]), 'Choose annual-average planning output to scale bolts by year-round production rather than spikes.');
    } else if (layerId === 'neon-streets') {
      title = 'Neon streets layer filters';
      body.innerHTML = zoomRangeMarkup(layerId)
        + fieldMarkup('Roads shown', 'scope', layerFilters.neonStreets.scope, [
        ['i95', 'I-95 only'],
        ['interstates', 'All interstates'],
        ['major', 'Interstates and major roads'],
        ['all', 'All streets'],
      ], 'I-95 is the default. Broader modes reuse the same vector tiles without downloading a second road dataset.')
        + numberFieldMarkup('Line width', 'lineWidth', layerFilters.neonStreets.lineWidth, { min: .25, max: 5, step: .25, help: 'Scales both the bright road core and its glow while preserving zoom-dependent widths.' });
    } else if (layerId === 'enviroscreen') {
      title = 'EnviroScreen layer filters';
      const filters = layerFilters.enviroscreen;
      body.innerHTML = zoomRangeMarkup(layerId)
        + fieldMarkup('Tract text match', 'text', filters.text)
        + fieldMarkup('Minimum EJ score', 'scoreBand', filters.scoreBand, FILTER_OPTIONS.enviroScoreBand)
        + fieldMarkup('Community flag', 'community', filters.community, FILTER_OPTIONS.enviroCommunity);
    } else if (layerId === 'parcels') {
      title = 'Parcel layer filters';
      body.innerHTML = zoomRangeMarkup(layerId)
        + fieldMarkup('Account ID text match', 'text', layerFilters.parcels.text, null, 'Filters currently loaded parcel boundaries by public account ID.');
    } else if (layerId === ESRI_BUILDINGS.id) {
      title = `${ESRI_BUILDINGS.name} layer settings`;
      body.innerHTML = zoomRangeMarkup(layerId)
        + `<p class="dc-modal-note">${escapeHtml(ESRI_BUILDINGS.description)}. Meshes are streamed only when the layer is rendered and the current zoom falls inside this range.</p>`;
    } else {
      const config = REMOTE_LAYERS.find((candidate) => candidate.id === layerId);
      if (!config) return;
      title = `${config.name} layer filters`;
      body.innerHTML = zoomRangeMarkup(layerId)
        + fieldMarkup('Feature text match', 'text', remoteLayerStates.get(config.id)?.text || '', null, 'Matches the fields returned from the official live service for the current map view.')
        + (config.geometry === 'point' ? fieldMarkup(
          'Point size uses',
          'sizeBy',
          remoteLayerStates.get(config.id)?.sizeBy || 'none',
          numericPointScaleOptions(
            (remoteLayerStates.get(config.id)?.data?.features || []).map((feature) => feature.properties || {}),
            config.scaleFields || [],
          ),
          'Numeric values are normalized to a bounded screen-space size.',
        ) : '')
        + (config.lineColorThemes ? fieldMarkup(
          'Line color theme',
          'colorTheme',
          remoteLayerStates.get(config.id)?.colorTheme || 'uniform',
          config.lineColorThemes.map((theme) => [theme.id, theme.label]),
          'Heat themes use published voltage as a capacity proxy. They do not show live MW flow.',
        ) : '')
        + (config.geometry === 'line' ? fieldMarkup(
          'Line width scale',
          'lineWidth',
          String(remoteLayerStates.get(config.id)?.lineWidth || 1),
          LINE_WIDTH_OPTIONS,
          'Multiplies this layer after the selected width basis is applied.',
        ) + fieldMarkup(
          'Line width uses',
          'lineWidthBy',
          normalizeLineWidthBy(config, remoteLayerStates.get(config.id)?.lineWidthBy),
          lineWidthFieldOptions(config),
          'Voltage class is a capacity proxy; utility load and hosting layers use published MW/kW capacity fields. These controls do not estimate live line flow.',
        ) : '')
        + `<p class="dc-modal-note">${escapeHtml(config.description)}</p>`;
    }
    document.getElementById('layer-filter-title').textContent = title;
    document.getElementById('layer-filter-modal').showModal();
  }

  function applyActiveLayerFilter(formData) {
    applySubmittedZoomRange(activeLayerConfigId, formData);
    if (activeLayerConfigId === 'datacenters') {
      layerFilters.datacenters = {
        text: String(formData.get('text') || '').trim().toLowerCase(),
        status: String(formData.get('status') || 'all'),
        energy: String(formData.get('energy') || 'all'),
        sentiment: String(formData.get('sentiment') || 'all'),
        powerScale: String(formData.get('powerScale') || 'all'),
        colorBy: String(formData.get('colorBy') || 'energy'),
        outlineBy: String(formData.get('outlineBy') || 'lifecycle'),
        glowBy: String(formData.get('glowBy') || 'contestation'),
        glowDistance: normalizeGlowDistance(formData.get('glowDistance')),
        glowBlur: normalizeGlowBlur(formData.get('glowBlur')),
        sizeBy: String(formData.get('sizeBy') || 'none'),
      };
    } else if (activeLayerConfigId === 'power-plants') {
      layerFilters.powerPlants = {
        text: String(formData.get('text') || '').trim().toLowerCase(),
        energy: String(formData.get('energy') || 'all'),
        colorBy: String(formData.get('colorBy') || 'energy'),
        outlineBy: String(formData.get('outlineBy') || 'technology'),
        fillBy: String(formData.get('fillBy') || 'none'),
        fillFraction: Math.max(0, Math.min(1, Number(formData.get('fillFraction') || 1))),
        outlineScale: normalizeBoltOutlineScale(formData.get('outlineScale')),
        sizeBy: String(formData.get('sizeBy') || 'none'),
      };
      normalizePowerPlantLayerFilters(layerFilters.powerPlants);
    } else if (activeLayerConfigId === 'neon-streets') {
      const scope = String(formData.get('scope') || 'i95');
      layerFilters.neonStreets.scope = ['i95', 'interstates', 'major', 'all'].includes(scope) ? scope : 'i95';
      layerFilters.neonStreets.lineWidth = normalizeLineWidthMultiplier(formData.get('lineWidth'));
    } else if (activeLayerConfigId === 'enviroscreen') {
      layerFilters.enviroscreen = {
        text: String(formData.get('text') || '').trim().toLowerCase(),
        scoreBand: String(formData.get('scoreBand') || 'all'),
        community: String(formData.get('community') || 'all'),
      };
    } else if (activeLayerConfigId === 'parcels') {
      layerFilters.parcels.text = String(formData.get('text') || '').trim().toLowerCase();
    } else {
      const config = REMOTE_LAYERS.find((candidate) => candidate.id === activeLayerConfigId);
      const state = remoteLayerStates.get(activeLayerConfigId);
      if (state) {
        state.text = String(formData.get('text') || '').trim().toLowerCase();
        state.sizeBy = String(formData.get('sizeBy') || 'none');
        state.colorTheme = String(formData.get('colorTheme') || (config?.lineColorThemes ? 'uniform' : 'default'));
        state.lineWidth = normalizeLineWidthMultiplier(formData.get('lineWidth'));
        state.lineWidthBy = normalizeLineWidthBy(config, formData.get('lineWidthBy'));
      }
    }
    applyAllLayerFilters();
  }

  function resetActiveLayerFilter() {
    layerZoomRanges.delete(activeLayerConfigId);
    if (activeLayerConfigId === 'datacenters') {
      layerFilters.datacenters = { text: '', status: 'all', energy: 'all', sentiment: 'all', powerScale: 'all', colorBy: 'energy', outlineBy: 'lifecycle', glowBy: 'contestation', glowDistance: 1, glowBlur: 1, sizeBy: 'none' };
    } else if (activeLayerConfigId === 'power-plants') {
      layerFilters.powerPlants = { text: '', energy: 'all', colorBy: 'energy', outlineBy: 'technology', fillBy: 'none', fillFraction: 1, outlineScale: 1.04, sizeBy: 'none' };
    } else if (activeLayerConfigId === 'neon-streets') {
      layerFilters.neonStreets = { scope: 'i95', lineWidth: 1 };
    } else if (activeLayerConfigId === 'enviroscreen') {
      layerFilters.enviroscreen = { text: '', scoreBand: 'all', community: 'all' };
    } else if (activeLayerConfigId === 'parcels') {
      layerFilters.parcels = { text: '' };
    } else {
      const config = REMOTE_LAYERS.find((candidate) => candidate.id === activeLayerConfigId);
      const state = remoteLayerStates.get(activeLayerConfigId);
      if (state) {
        state.text = '';
        state.sizeBy = 'none';
        state.colorTheme = config?.lineColorThemes ? 'uniform' : 'default';
        state.lineWidth = 1;
        state.lineWidthBy = 'zoom';
      }
    }
  }

  function applyZoomVisibility(map, records = activeLayerContext?.records, markerById = activeLayerContext?.markerById) {
    if (!map) return;
    if (records && markerById) renderResults(records, markerById);
    applyNeonStreetLayer(map);
    if (document.getElementById('show-enviroscreen')?.checked) setEnviroScreenVisibility(map, true);
    if (document.getElementById('show-parcels')?.checked) setParcelVisibility(map, true);
    refreshRemoteLayers(map);
    updateEsriBuildingsLayer(map);
  }

  function applyAllLayerFilters() {
    if (!activeLayerContext) return;
    const { map, records, markerById } = activeLayerContext;
    renderResults(records, markerById);
    applyNeonStreetLayer(map);
    if (enviroScreenData && map.getSource(ENVIROSCREEN_SOURCE_ID)) applyEnviroScreenFilter(map);
    if (map.getSource(PARCEL_SOURCE_ID)) applyParcelFilter(map);
    REMOTE_LAYERS.forEach((config) => {
      const state = remoteLayerStates.get(config.id);
      if (state?.enabled && state.data) addRemoteLayer(map, config, state.data);
    });
    updateEsriBuildingsLayer(map);
    persistUiState();
  }

  function applyCollectiveTheme(map) {
    const setPaint = (layer, property, value) => {
      try {
        map.setPaintProperty(layer.id, property, value);
      } catch (_error) {
        // A provider theme may omit an optional paint property for a layer.
      }
    };

    map.getStyle().layers.forEach((layer) => {
      const semantic = `${layer.id} ${layer['source-layer'] || ''}`.toLowerCase();
      const isWater = semantic.includes('water');
      const isRoad = /road|transportation|bridge|tunnel|motorway|trunk/.test(semantic);
      const isRail = semantic.includes('rail');
      const isBoundary = /boundary|admin/.test(semantic);
      const isPark = /park|landcover|wood|grass|wetland/.test(semantic);
      const isBuilding = semantic.includes('building');

      if (layer.type === 'background') {
        setPaint(layer, 'background-color', '#001a3d');
      } else if (layer.type === 'raster') {
        setPaint(layer, 'raster-saturation', -1);
        setPaint(layer, 'raster-contrast', .18);
        setPaint(layer, 'raster-brightness-min', .06);
        setPaint(layer, 'raster-brightness-max', .28);
      } else if (layer.type === 'fill') {
        setPaint(layer, 'fill-pattern', null);
        setPaint(layer, 'fill-color', isWater
          ? '#075d8f'
          : isPark
            ? '#073954'
            : isBuilding
              ? '#16466f'
              : '#082950');
        setPaint(layer, 'fill-outline-color', isWater ? '#147fb5' : '#17466d');
      } else if (layer.type === 'fill-extrusion') {
        setPaint(layer, 'fill-extrusion-color', '#16466f');
      } else if (layer.type === 'line') {
        setPaint(layer, 'line-color', isWater
          ? '#2697c8'
          : isRoad && !isRail
            ? roadColor(semantic)
            : isBoundary
              ? '#5794bd'
              : '#245271');
        if (isRoad && !isRail) {
          setPaint(layer, 'line-width', roadWidth(semantic));
          setPaint(layer, 'line-opacity', roadOpacity(semantic));
        }
      } else if (layer.type === 'symbol') {
        setPaint(layer, 'text-color', '#b8d9e8');
        setPaint(layer, 'text-halo-color', '#00162f');
        setPaint(layer, 'text-halo-width', 1.1);
      }
    });
  }

  function roadColor(semantic) {
    if (semantic.includes('casing')) return '#102f4d';
    if (semantic.includes('motorway')) return '#7eb2d0';
    if (/trunk|primary/.test(semantic)) return '#6899b9';
    if (/secondary|tertiary/.test(semantic)) return '#4f7d9f';
    return '#365f80';
  }

  function roadWidth(semantic) {
    const isCasing = semantic.includes('casing');
    let stops;
    if (semantic.includes('motorway')) {
      stops = [[5, .42], [8, .6], [11, .92], [14, 1.55], [18, 4.1]];
    } else if (/trunk|primary/.test(semantic)) {
      stops = [[5, .32], [8, .48], [11, .76], [14, 1.3], [18, 3.5]];
    } else if (/secondary|tertiary/.test(semantic)) {
      stops = [[7, .16], [10, .32], [13, .68], [16, 1.4], [19, 3.1]];
    } else if (/service|track|path|pedestrian/.test(semantic)) {
      stops = [[12, 0], [14, .16], [16, .48], [19, 1.25]];
    } else {
      stops = [[10, 0], [12, .16], [14, .42], [16, .88], [19, 2.15]];
    }
    const scaledStops = stops.flatMap(([zoom, width]) => [
      zoom,
      isCasing && width > 0 ? (width * 1.35) + .16 : width,
    ]);
    return ['interpolate', ['exponential', 1.25], ['zoom'], ...scaledStops];
  }

  function roadOpacity(semantic) {
    if (/service|track|path|pedestrian/.test(semantic)) {
      return ['interpolate', ['linear'], ['zoom'], 12, 0, 14, .42, 17, .72, 19, .86];
    }
    if (/minor|street/.test(semantic)) {
      return ['interpolate', ['linear'], ['zoom'], 10, 0, 12, .38, 15, .7, 18, .86];
    }
    return semantic.includes('casing') ? .82 : .92;
  }

  async function setEnviroScreenVisibility(map, enabled) {
    const toggle = document.getElementById('show-enviroscreen');
    const legend = document.getElementById('enviroscreen-legend');
    const status = document.getElementById('enviroscreen-status');
    legend.hidden = !enabled;
    legend.classList.remove('is-error');

    if (!enabled) {
      [ENVIROSCREEN_FILL_ID, ENVIROSCREEN_LINE_ID].forEach((layerId) => {
        if (map.getLayer(layerId)) map.setLayoutProperty(layerId, 'visibility', 'none');
      });
      toggle.removeAttribute('aria-busy');
      return;
    }
    if (!layerShownAtZoom('enviroscreen', map.getZoom())) {
      [ENVIROSCREEN_FILL_ID, ENVIROSCREEN_LINE_ID].forEach((layerId) => {
        if (map.getLayer(layerId)) map.setLayoutProperty(layerId, 'visibility', 'none');
      });
      status.textContent = `Visible only from zoom ${zoomRangeLabel('enviroscreen')}`;
      toggle.removeAttribute('aria-busy');
      return;
    }

    status.textContent = 'Loading official MDE census-tract data…';
    toggle.setAttribute('aria-busy', 'true');
    try {
      if (!enviroScreenData) {
        enviroScreenRequest ||= fetch(ENVIROSCREEN_QUERY).then((response) => {
          if (!response.ok) throw new Error(`MDE service returned HTTP ${response.status}`);
          return response.json();
        });
        enviroScreenData = await enviroScreenRequest;
      }
      if (!toggle.checked) return;
      addEnviroScreenLayers(map, enviroScreenData);
      applyEnviroScreenFilter(map);
      status.textContent = `${number(enviroScreenData.features.length)} census tracts · MDE V3, updated July 24, 2025`;
    } catch (error) {
      enviroScreenRequest = null;
      legend.classList.add('is-error');
      status.textContent = `Layer unavailable: ${error.message}`;
    } finally {
      toggle.removeAttribute('aria-busy');
    }
  }

  function addEnviroScreenLayers(map, data) {
    if (!map.getSource(ENVIROSCREEN_SOURCE_ID)) {
      map.addSource(ENVIROSCREEN_SOURCE_ID, { type: 'geojson', data });
    }
    const firstLabel = map.getStyle().layers.find((layer) => layer.type === 'symbol')?.id;
    if (!map.getLayer(ENVIROSCREEN_FILL_ID)) {
      map.addLayer({
        id: ENVIROSCREEN_FILL_ID,
        type: 'fill',
        source: ENVIROSCREEN_SOURCE_ID,
        paint: {
          'fill-color': layerCustomColors.get('enviroscreen') || [
            'step', ['coalesce', ['get', 'P_EJ'], 0],
            '#01856f', 25,
            '#81ccbf', 50,
            '#dec17e', 75,
            '#a6601b',
          ],
          'fill-opacity': .48,
        },
      }, firstLabel);
    }
    if (!map.getLayer(ENVIROSCREEN_LINE_ID)) {
      map.addLayer({
        id: ENVIROSCREEN_LINE_ID,
        type: 'line',
        source: ENVIROSCREEN_SOURCE_ID,
        paint: {
          'line-color': 'rgba(230, 244, 251, 0)',
          'line-width': 0,
        },
      }, firstLabel);
    }
    const visibility = layerShownAtZoom('enviroscreen', map.getZoom()) ? 'visible' : 'none';
    map.setLayoutProperty(ENVIROSCREEN_FILL_ID, 'visibility', visibility);
    map.setLayoutProperty(ENVIROSCREEN_LINE_ID, 'visibility', visibility);
    map.setPaintProperty(ENVIROSCREEN_FILL_ID, 'fill-color', layerCustomColors.get('enviroscreen') || [
      'step', ['coalesce', ['get', 'P_EJ'], 0],
      '#01856f', 25,
      '#81ccbf', 50,
      '#dec17e', 75,
      '#a6601b',
    ]);
    applyMapLayerOrder(map);
  }

  function applyEnviroScreenFilter(map) {
    if (!enviroScreenData || !map.getSource(ENVIROSCREEN_SOURCE_ID)) return;
    const { text, scoreBand, community } = layerFilters.enviroscreen;
    const features = enviroScreenData.features.filter((feature) => {
      const props = feature.properties || {};
      const geoid = String(props.GEOID20 || '').toLowerCase();
      const score = Number(props.P_EJ || 0);
      const overburdened = Number(props.OVERBURDENED_COMMUNITY || 0) > 0;
      const underserved = Number(props.UNDERSERVED_COMMUNITY || 0) > 0;
      if (text && !geoid.includes(text)) return false;
      if (scoreBand !== 'all' && score < Number(scoreBand)) return false;
      if (community === 'overburdened' && !overburdened) return false;
      if (community === 'underserved' && !underserved) return false;
      if (community === 'either' && !overburdened && !underserved) return false;
      if (community === 'both' && (!overburdened || !underserved)) return false;
      return true;
    });
    map.getSource(ENVIROSCREEN_SOURCE_ID).setData({ type: 'FeatureCollection', features });
  }

  function setParcelVisibility(map, enabled) {
    const legend = document.getElementById('parcel-legend');
    legend.hidden = !enabled;
    legend.classList.remove('is-error');
    if (!enabled) {
      parcelHoverAbort?.abort();
      parcelBoundaryAbort?.abort();
      clearTimeout(parcelHoverTimer);
      hoveredParcel = null;
      [PARCEL_LAYER_ID, PARCEL_HOVER_FILL_ID, PARCEL_HOVER_LINE_ID].forEach((layerId) => {
        if (map.getLayer(layerId)) map.setLayoutProperty(layerId, 'visibility', 'none');
      });
      map.getCanvas().style.cursor = '';
      return;
    }
    if (!layerShownAtZoom('parcels', map.getZoom())) {
      [PARCEL_LAYER_ID, PARCEL_HOVER_FILL_ID, PARCEL_HOVER_LINE_ID].forEach((layerId) => {
        if (map.getLayer(layerId)) map.setLayoutProperty(layerId, 'visibility', 'none');
      });
      document.getElementById('parcel-status').textContent = `Visible only from zoom ${zoomRangeLabel('parcels')}`;
      return;
    }

    try {
      if (!map.getSource(PARCEL_SOURCE_ID)) {
        map.addSource(PARCEL_SOURCE_ID, {
          type: 'geojson',
          data: { type: 'FeatureCollection', features: [] },
          attribution: 'Parcel boundaries: MD iMAP, MDP, SDAT',
        });
      }
      const firstLabel = map.getStyle().layers.find((layer) => layer.type === 'symbol')?.id;
      if (!map.getLayer(PARCEL_LAYER_ID)) {
        const parcelRange = zoomRangeForLayer('parcels');
        map.addLayer({
          id: PARCEL_LAYER_ID,
          type: 'line',
          source: PARCEL_SOURCE_ID,
          minzoom: parcelRange.min,
          maxzoom: parcelRange.max,
          paint: {
            'line-color': layerCustomColors.get('parcels') || 'rgba(121, 207, 241, .82)',
            'line-width': ['interpolate', ['linear'], ['zoom'], 13, .7, 16, 1.2, 19, 1.8],
          },
        }, firstLabel);
      }
      const parcelRange = zoomRangeForLayer('parcels');
      if (map.getLayer(PARCEL_LAYER_ID) && map.setLayerZoomRange) map.setLayerZoomRange(PARCEL_LAYER_ID, parcelRange.min, parcelRange.max);
      map.setPaintProperty(PARCEL_LAYER_ID, 'line-color', layerCustomColors.get('parcels') || 'rgba(121, 207, 241, .82)');
      map.setLayoutProperty(PARCEL_LAYER_ID, 'visibility', 'visible');
      ensureParcelHoverLayers(map, firstLabel);
      loadParcelBoundaries(map);
    } catch (error) {
      legend.classList.add('is-error');
      document.getElementById('parcel-status').textContent = `Layer unavailable: ${error.message}`;
    }
  }

  function ensureParcelHoverLayers(map, firstLabel) {
    if (!map.getSource(PARCEL_HOVER_SOURCE_ID)) {
      map.addSource(PARCEL_HOVER_SOURCE_ID, {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      });
    }
    if (!map.getLayer(PARCEL_HOVER_FILL_ID)) {
      map.addLayer({
        id: PARCEL_HOVER_FILL_ID,
        type: 'fill',
        source: PARCEL_HOVER_SOURCE_ID,
        paint: { 'fill-color': layerCustomColors.get('parcels') || '#f3a712', 'fill-opacity': .16 },
      }, firstLabel);
    }
    if (!map.getLayer(PARCEL_HOVER_LINE_ID)) {
      map.addLayer({
        id: PARCEL_HOVER_LINE_ID,
        type: 'line',
        source: PARCEL_HOVER_SOURCE_ID,
        paint: { 'line-color': layerCustomColors.get('parcels') || '#ffd582', 'line-width': 2 },
      }, firstLabel);
    }
    map.setLayoutProperty(PARCEL_HOVER_FILL_ID, 'visibility', 'visible');
    map.setLayoutProperty(PARCEL_HOVER_LINE_ID, 'visibility', 'visible');
    map.setPaintProperty(PARCEL_HOVER_FILL_ID, 'fill-color', layerCustomColors.get('parcels') || '#f3a712');
    map.setPaintProperty(PARCEL_HOVER_LINE_ID, 'line-color', layerCustomColors.get('parcels') || '#ffd582');
    if (hoveredParcel) map.getSource(PARCEL_HOVER_SOURCE_ID).setData(hoveredParcel);
    applyMapLayerOrder(map);
  }

  function updateParcelStatus(map) {
    if (!document.getElementById('show-parcels').checked) return;
    const status = document.getElementById('parcel-status');
    if (!layerShownAtZoom('parcels', map.getZoom())) {
      status.textContent = `Visible only from zoom ${zoomRangeLabel('parcels')}`;
      return;
    }
    status.textContent = document.getElementById('hover-parcels').checked
      ? 'Property boundaries visible · hover a parcel to query MDP/SDAT.'
      : 'Property boundaries visible · hover details are off.';
  }

  async function loadParcelBoundaries(map) {
    if (!document.getElementById('show-parcels').checked || !map.getSource(PARCEL_SOURCE_ID)) return;
    parcelBoundaryAbort?.abort();
    const source = map.getSource(PARCEL_SOURCE_ID);
    if (!layerShownAtZoom('parcels', map.getZoom())) {
      source.setData({ type: 'FeatureCollection', features: [] });
      updateParcelStatus(map);
      return;
    }

    const bounds = map.getBounds();
    const parameters = new URLSearchParams({
      where: '1=1',
      geometry: `${bounds.getWest()},${bounds.getSouth()},${bounds.getEast()},${bounds.getNorth()}`,
      geometryType: 'esriGeometryEnvelope',
      inSR: '4326',
      spatialRel: 'esriSpatialRelIntersects',
      outFields: 'ACCTID',
      returnGeometry: 'true',
      outSR: '4326',
      geometryPrecision: '6',
      maxAllowableOffset: '0.00001',
      resultRecordCount: String(PARCEL_MAX_FEATURES),
      f: 'geojson',
    });
    parcelBoundaryAbort = new AbortController();
    document.getElementById('parcel-status').textContent = 'Loading property boundaries for this view…';
    try {
      const response = await fetch(`${PARCEL_SERVICE}/0/query?${parameters}`, { signal: parcelBoundaryAbort.signal });
      if (!response.ok) throw new Error(`MDP/SDAT service returned HTTP ${response.status}`);
      const data = await response.json();
      if (data.error) throw new Error(data.error.message || 'MDP/SDAT query failed');
      if (!document.getElementById('show-parcels').checked) return;
      parcelBoundaryData = data;
      applyParcelFilter(map);
      document.getElementById('parcel-status').textContent = data.features.length >= PARCEL_MAX_FEATURES
        ? `Showing ${number(data.features.length)} boundaries · zoom in for a complete view.`
        : document.getElementById('hover-parcels').checked
          ? `${number(data.features.length)} property boundaries visible · hover to look up a record.`
          : `${number(data.features.length)} property boundaries visible · hover details are off.`;
    } catch (error) {
      if (error.name === 'AbortError') return;
      document.getElementById('parcel-legend').classList.add('is-error');
      document.getElementById('parcel-status').textContent = `Layer unavailable: ${error.message}`;
    }
  }

  function applyParcelFilter(map) {
    if (!map.getSource(PARCEL_SOURCE_ID)) return;
    const query = layerFilters.parcels.text;
    const features = parcelBoundaryData.features.filter((feature) => {
      const accountId = String(feature.properties?.ACCTID || '').toLowerCase();
      return !query || accountId.includes(query);
    });
    map.getSource(PARCEL_SOURCE_ID).setData({ type: 'FeatureCollection', features });
  }

  function handleMapHover(map, event, sourceById) {
    const target = topMapHoverTarget(map, event.point, sourceById);
    showHoverTarget(map, target);
    if (!target && document.getElementById('show-parcels').checked
      && document.getElementById('hover-parcels').checked
      && layerShownAtZoom('parcels', map.getZoom())) {
      map.getCanvas().style.cursor = 'pointer';
      scheduleParcelLookup(map, event.lngLat);
      return;
    }
    if (!target) {
      clearTimeout(parcelHoverTimer);
      parcelHoverAbort?.abort();
      map.getCanvas().style.cursor = '';
      clearInspectorHover();
    }
  }

  function showHoverTarget(map, target) {
    updateHoveredDataCenterMarker(target);
    powerPlantBoltLayer?.setHoveredRecord(target?.kind === 'power-plant' ? target.record : null);
    if (target) {
      clearTimeout(parcelHoverTimer);
      parcelHoverAbort?.abort();
      if (target.kind !== 'parcel') clearParcelHighlight(map);
      map.getCanvas().style.cursor = 'pointer';
      renderHoveredInspector(target.key, target.render, target.layerId);
    }
  }

  function updateHoveredDataCenterMarker(target) {
    const recordId = target?.kind === 'data-center' ? target.record.id : null;
    if (hoveredDataCenterElement?.dataset.recordId === recordId) return;
    hoveredDataCenterElement?.classList.remove('is-map-hovered');
    hoveredDataCenterElement = recordId
      ? document.querySelector(`.dc-map-marker--center[data-record-id="${CSS.escape(recordId)}"]`)
      : null;
    hoveredDataCenterElement?.classList.add('is-map-hovered');
  }

  function topMapHoverTarget(map, point, sourceById) {
    const queryPoint = { x: point.x, y: point.y };
    const candidates = [];
    const dataCenter = topDataCenterHoverRecord(map, point);
    if (dataCenter) {
      const z = layerZIndex('datacenters');
      candidates.push({
        kind: 'data-center',
        key: `record:${dataCenter.id}`,
        layerId: 'datacenters',
        record: dataCenter,
        z,
        render: () => selectRecord(dataCenter, sourceById),
      });
    }
    if (deckHoverTarget) candidates.push({ ...deckHoverTarget, z: layerZIndex(deckHoverTarget.layerId) });
    if (
      document.getElementById('show-power-plants').checked
      && document.getElementById('hover-power-plants').checked
    ) {
      const hit = powerPlantBoltLayer?.hitTest(point);
      if (hit?.record) {
        const record = hit.record;
        const layerZ = layerZIndex('power-plants');
        candidates.push({
          kind: 'power-plant',
          key: `record:${record.id}`,
          layerId: 'power-plants',
          record,
          z: layerZ + Math.min(.99, Math.max(0, hit.zOffset || 0)),
          render: () => selectRecord(record, sourceById),
        });
      }
    }

    const layerTargets = new Map();
    if (
      document.getElementById('show-neon-streets').checked
      && document.getElementById('hover-neon-streets').checked
      && layerShownAtZoom('neon-streets', map.getZoom())
      && map.getLayer(NEON_STREET_CORE_LAYER_ID)
    ) {
      layerTargets.set(NEON_STREET_CORE_LAYER_ID, (feature) => ({
        kind: 'neon-street',
        key: neonStreetKey(feature),
        layerId: 'neon-streets',
        render: () => renderNeonStreetDetail(feature.properties),
      }));
    }
    if (document.getElementById('hover-enviroscreen').checked && layerShownAtZoom('enviroscreen', map.getZoom()) && map.getLayer(ENVIROSCREEN_FILL_ID)) {
      layerTargets.set(ENVIROSCREEN_FILL_ID, (feature) => ({
        kind: 'enviroscreen',
        key: `enviroscreen:${feature.properties.GEOID20 || 'unknown'}`,
        layerId: 'enviroscreen',
        render: () => renderEnviroScreenDetail(feature.properties),
      }));
    }
    REMOTE_LAYERS.forEach((config) => {
      if (!remoteLayerStates.get(config.id)?.enabled || !document.getElementById(`hover-${config.id}`).checked || !layerShownAtZoom(config.id, map.getZoom())) return;
      remoteRenderLayerIds(config).forEach((layerId) => {
        if (!map.getLayer(layerId)) return;
        layerTargets.set(layerId, (feature) => ({
          kind: 'remote',
          key: remoteFeatureKey({ feature, config }),
          layerId: config.id,
          render: () => renderRemoteLayerDetail(config, feature.properties),
        }));
      });
    });
    if (hoveredParcel && layerShownAtZoom('parcels', map.getZoom()) && map.getLayer(PARCEL_HOVER_FILL_ID)) {
      layerTargets.set(PARCEL_HOVER_FILL_ID, () => {
        const properties = hoveredParcel.features[0].properties;
        return {
          kind: 'parcel',
          key: `parcel:${properties.ACCTID || 'unknown'}`,
          layerId: 'parcels',
          render: () => renderParcelDetail(properties),
        };
      });
    }

    const layerIds = [...layerTargets.keys()];
    if (layerIds.length) {
      map.queryRenderedFeatures(queryPoint, { layers: layerIds }).forEach((feature) => {
        const target = layerTargets.get(feature.layer.id)?.(feature);
        if (target) candidates.push({ ...target, z: layerZIndex(target.layerId) });
      });
    }
    candidates.sort((left, right) => right.z - left.z);
    window.__lastHoverArbitration = {
      candidates: candidates.map(({ key, kind, layerId, z }) => ({ key, kind, layerId, z })),
      chosen: candidates.length ? { key: candidates[0].key, kind: candidates[0].kind, layerId: candidates[0].layerId, z: candidates[0].z } : null,
    };
    return candidates[0] || null;
  }

  function topDataCenterHoverRecord(map, point) {
    if (
      !document.getElementById('show-datacenters').checked
      || !document.getElementById('hover-datacenters').checked
    ) return null;
    const rect = map.getCanvas().getBoundingClientRect();
    const clientX = rect.left + point.x;
    const clientY = rect.top + point.y;
    const elementRecord = document.elementsFromPoint(clientX, clientY)
      .map((element) => element.closest?.('.dc-map-marker--center'))
      .find((element) => element && !element.hidden && element.dataset.recordId);
    if (elementRecord) {
      return visibleDataCenterHoverEntries.find((entry) => entry.record.id === elementRecord.dataset.recordId)?.record || null;
    }
    let best = null;
    visibleDataCenterHoverEntries.forEach((entry) => {
      const projected = map.project([entry.record.longitude, entry.record.latitude]);
      const dx = projected.x - point.x;
      const dy = projected.y - point.y;
      const distance = Math.hypot(dx, dy);
      const radius = Math.max(14, entry.size * .72);
      if (distance > radius) return;
      if (!best || entry.size > best.size || (entry.size === best.size && distance < best.distance)) {
        best = { ...entry, distance };
      }
    });
    return best?.record || null;
  }

  function handleMapClick(map, event, sourceById) {
    pinHoverTarget(topMapHoverTarget(map, event.point, sourceById));
  }

  function neonStreetKey(feature) {
    const properties = feature.properties || {};
    return `neon-street:${feature.id ?? properties.ref ?? properties.name ?? 'road'}`;
  }

  function renderNeonStreetDetail(properties) {
    const route = properties.ref || properties.name || 'Road segment';
    const detail = prepareInspectorDetail();
    detail.innerHTML = `
      <h2>${escapeHtml(route)}</h2>
      <p class="dc-type">Neon streets · OpenFreeMap road network</p>
      ${renderFactGroup('Road', [
        ['Route reference', known(properties.ref)],
        ['Name', known(properties.name)],
        ['Road class', known(properties.class)],
        ['Surface', known(properties.surface)],
        ['Bridge / tunnel', known(properties.brunnel)],
      ])}
      <div class="dc-record-sources"><strong>Source</strong><ul><li><a href="https://openfreemap.org/" target="_blank" rel="noopener noreferrer">OpenFreeMap / OpenStreetMap</a></li></ul></div>`;
  }

  function remoteFeatureKey(hit) {
    const identity = hit.feature.id ?? hit.config.facts
      .map(([, field]) => hit.feature.properties[field])
      .join('|');
    return `remote:${hit.config.id}:${identity}`;
  }

  function findRemoteHoverFeature(map, point, requireHover = true) {
    const renderLayerToConfig = new Map();
    REMOTE_LAYERS.forEach((config) => {
      if (!remoteLayerStates.get(config.id)?.enabled) return;
      if (requireHover && !document.getElementById(`hover-${config.id}`).checked) return;
      remoteRenderLayerIds(config).forEach((layerId) => {
        if (map.getLayer(layerId)) renderLayerToConfig.set(layerId, config);
      });
    });
    const layerIds = [...renderLayerToConfig.keys()];
    if (!layerIds.length) return null;
    const feature = map.queryRenderedFeatures(point, { layers: layerIds })[0];
    if (!feature) return null;
    return { feature, config: renderLayerToConfig.get(feature.layer.id) };
  }

  function displayRemoteValue(value, field) {
    if (value === null || value === undefined || String(value).trim() === '') return known(null);
    if (field === 'UPDATEYR' && /^\d{4}/.test(String(value))) return escapeHtml(String(value).slice(0, 4));
    if (typeof value === 'number' && value > 100000000000) {
      return escapeHtml(new Date(value).toLocaleDateString('en-US'));
    }
    if (typeof value === 'number') return escapeHtml(number(value, 2));
    return escapeHtml(String(value).trim());
  }

  function heatThemeColor(theme, value) {
    const stops = [69, 115, 230, 345, 500, 735, 1000];
    if (!Number.isFinite(value) || value <= 0) return '#aab9c5';
    if (value <= stops[0]) return theme.colors[0];
    if (value >= stops.at(-1)) return theme.colors.at(-1);
    const upperIndex = stops.findIndex((stop) => stop >= value);
    const lowerIndex = upperIndex - 1;
    const amount = (value - stops[lowerIndex]) / (stops[upperIndex] - stops[lowerIndex]);
    const lower = hexToRgb(theme.colors[lowerIndex]);
    const upper = hexToRgb(theme.colors[upperIndex]);
    return rgbToHex({
      r: lower.r + ((upper.r - lower.r) * amount),
      g: lower.g + ((upper.g - lower.g) * amount),
      b: lower.b + ((upper.b - lower.b) * amount),
    });
  }

  function renderRemoteColorLegend(config, properties = {}) {
    const selectedThemeId = remoteLayerStates.get(config.id)?.colorTheme || (config.lineColorThemes ? 'uniform' : 'default');
    const selectedTheme = config.lineColorThemes?.find((theme) => theme.id === selectedThemeId);
    if (selectedTheme?.id === 'uniform') {
      const color = layerCustomColors.get(config.id) || config.lineColor || config.color;
      return `<section class="dc-feature-color-key" aria-label="${escapeHtml(config.name)} uniform color"><span class="dc-color-key-swatch" style="--dc-key-color:${escapeHtml(color)}" aria-hidden="true"></span><span><strong>Uniform line color</strong><small>${escapeHtml(selectedTheme.label)}</small></span></section>`;
    }
    if (selectedTheme && selectedTheme.id !== 'default') {
      const voltage = Number(properties[selectedTheme.field]);
      const color = heatThemeColor(selectedTheme, voltage);
      const voltageLabel = Number.isFinite(voltage) && voltage > 0 ? `${number(voltage, 1)} kV` : 'Voltage unavailable';
      return `<section class="dc-feature-color-key" aria-label="${escapeHtml(config.name)} heat color"><span class="dc-color-key-swatch" style="--dc-key-color:${color}" aria-hidden="true"></span><span><strong>${escapeHtml(selectedTheme.label)}</strong><small>Voltage proxy · ${escapeHtml(voltageLabel)}</small></span></section>`;
    }
    const legend = config.colorLegend;
    if (!legend) return '';
    const rawValue = properties[legend.field];
    const value = rawValue == null ? '' : String(rawValue).trim();
    const active = legend.entries.find((entry) => entry.value === value || entry.aliases?.includes(value));
    const activeEntry = active || legend.fallback;
    const displayedValue = active?.label || value || legend.fallback.label;
    return `<section class="dc-feature-color-key" aria-label="${escapeHtml(config.name)} color"><span class="dc-color-key-swatch" style="--dc-key-color:${activeEntry.color}" aria-hidden="true"></span><span><strong>Line color</strong><small>${escapeHtml(legend.label)} · ${escapeHtml(displayedValue)}</small></span></section>`;
  }

  function renderRemoteLayerDetail(config, properties) {
    const title = config.titleFields.map((field) => properties[field]).find((value) => value != null && value !== '') || config.name;
    const facts = config.facts.map(([label, field, suffix = '']) => [label, `${displayRemoteValue(properties[field], field)}${escapeHtml(suffix)}`]);
    const sources = [[config.sourceLabel, config.sourceUrl], ...(config.additionalSources || [])];
    const recordType = config.staticDataUrl ? 'derived official inventory' : 'live official service';
    const provenanceNote = config.staticDataUrl
      ? 'This point was generated from the cited official boundary and transmission geometry. It is stored locally for fast display and reproducible review.'
      : 'This feature was queried on demand for the current map view and is not stored by this site.';
    const detail = prepareInspectorDetail();
    detail.innerHTML = `
      <h2>${escapeHtml(title)}</h2>
      <p class="dc-type">${escapeHtml(config.name)} · ${escapeHtml(recordType)}</p>
      ${renderRemoteColorLegend(config, properties)}
      ${renderFactGroup('Layer record', facts)}
      <p class="dc-record-note">${escapeHtml(provenanceNote)}</p>
      <div class="dc-record-sources"><strong>Sources</strong><ul>${sources.map(([label, url]) => `<li><a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a></li>`).join('')}</ul></div>`;
  }

  function scheduleParcelLookup(map, lngLat) {
    clearTimeout(parcelHoverTimer);
    parcelHoverAbort?.abort();
    parcelHoverTimer = setTimeout(() => lookupParcel(map, lngLat), 180);
  }

  async function lookupParcel(map, lngLat) {
    parcelHoverAbort = new AbortController();
    const fields = [
      'ACCTID', 'ADDRESS', 'PREMSNUM', 'PREMSDIR', 'PREMSNAM', 'PREMSTYP', 'PREMCITY', 'PREMZIP',
      'OWNADD1', 'OWNADD2', 'OWNCITY', 'OWNSTATE', 'OWNERZIP', 'LEGAL1', 'LEGAL2', 'LEGAL3',
      'DESCLU', 'ACRES', 'NFMTTLVL', 'SDATWEBADR', 'SDATDATE', 'POLYDATE', 'MAP', 'GRID', 'PARCEL',
    ].join(',');
    const parameters = new URLSearchParams({
      geometry: `${lngLat.lng},${lngLat.lat}`,
      geometryType: 'esriGeometryPoint',
      inSR: '4326',
      spatialRel: 'esriSpatialRelIntersects',
      outFields: fields,
      returnGeometry: 'true',
      outSR: '4326',
      geometryPrecision: '6',
      resultRecordCount: '1',
      f: 'geojson',
    });
    try {
      const response = await fetch(`${PARCEL_SERVICE}/0/query?${parameters}`, { signal: parcelHoverAbort.signal });
      if (!response.ok) throw new Error(`MDP/SDAT service returned HTTP ${response.status}`);
      const data = await response.json();
      if (!data.features?.length || !document.getElementById('show-parcels').checked) {
        clearParcelHighlight(map);
        return;
      }
      hoveredParcel = data;
      map.getSource(PARCEL_HOVER_SOURCE_ID)?.setData(data);
      const properties = data.features[0].properties;
      renderHoveredInspector(`parcel:${properties.ACCTID || 'unknown'}`, () => renderParcelDetail(properties), 'parcels');
      document.getElementById('parcel-status').textContent = 'Property record loaded from MDP/SDAT.';
    } catch (error) {
      if (error.name === 'AbortError') return;
      const legend = document.getElementById('parcel-legend');
      legend.classList.add('is-error');
      document.getElementById('parcel-status').textContent = `Lookup unavailable: ${error.message}`;
    }
  }

  function clearParcelHighlight(map) {
    hoveredParcel = null;
    map.getSource(PARCEL_HOVER_SOURCE_ID)?.setData({ type: 'FeatureCollection', features: [] });
  }

  function renderEnviroScreenDetail(properties) {
    const detail = prepareInspectorDetail();
    detail.innerHTML = `
      <h2>MDEnviroScreen tract ${escapeHtml(properties.GEOID20 || 'unknown')}</h2>
      <p class="dc-type">Maryland Department of the Environment · census tract</p>
      ${renderFactGroup('Environmental justice screen', [
        ['EJ score', known(properties.P_EJ)],
        ['Overburdened community', yesNo(properties.OVERBURDENED_COMMUNITY)],
        ['Underserved community', yesNo(properties.UNDERSERVED_COMMUNITY)],
      ])}
      <p class="dc-record-note">The summary score does not include every available MDEnviroScreen layer. Review the underlying indicators and MDE cautions before using it in a decision.</p>
      <div class="dc-record-sources"><strong>Source</strong><ul><li><a href="https://mde.maryland.gov/Environmental_Justice/Pages/MDEnviroScreen.aspx" target="_blank" rel="noopener noreferrer">MDE MDEnviroScreen methodology</a></li></ul></div>`;
  }

  function renderParcelDetail(properties) {
    const premise = properties.ADDRESS || [
      properties.PREMSNUM, properties.PREMSDIR, properties.PREMSNAM, properties.PREMSTYP,
      properties.PREMCITY, properties.PREMZIP,
    ].filter(Boolean).join(' ');
    const mailing = [properties.OWNADD1, properties.OWNADD2, properties.OWNCITY, properties.OWNSTATE, properties.OWNERZIP]
      .filter(Boolean).join(', ');
    const legal = [properties.LEGAL1, properties.LEGAL2, properties.LEGAL3].filter(Boolean).join(' · ');
    const detail = prepareInspectorDetail();
    detail.innerHTML = `
      <h2>${escapeHtml(premise || `Parcel ${properties.ACCTID || 'unknown'}`)}</h2>
      <p class="dc-type">MDP / SDAT public property record</p>
      ${renderFactGroup('Parcel', [
        ['Account ID', known(properties.ACCTID)],
        ['Premise', known(premise)],
        ['Map / grid / parcel', known([properties.MAP, properties.GRID, properties.PARCEL].filter(Boolean).join(' / '))],
        ['Land use', known(properties.DESCLU)],
        ['Acres', properties.ACRES == null ? known(null) : number(properties.ACRES, 2)],
        ['Legal description', known(legal)],
      ])}
      ${renderFactGroup('Assessment record', [
        ['Appraised full value', properties.NFMTTLVL == null ? known(null) : `$${number(properties.NFMTTLVL)}`],
        ['Assessment data', known(properties.SDATDATE)],
        ['Boundary geometry', known(properties.POLYDATE)],
        ['Mailing address', known(mailing)],
      ])}
      <p class="dc-record-note">Parcel boundaries are planning and assessment references, not legal surveys. Dates can differ between the boundary geometry and linked SDAT assessment record.</p>
      ${properties.SDATWEBADR ? `<div class="dc-record-sources"><strong>Source</strong><ul><li><a href="${escapeHtml(properties.SDATWEBADR)}" target="_blank" rel="noopener noreferrer">Open official SDAT property record</a></li></ul></div>` : ''}`;
  }

  function yesNo(value) {
    if (value === null || value === undefined || value === '') return known(null);
    return Number(value) > 0 ? 'Yes' : 'No';
  }

  function visibleType(record) {
    const layerId = record.record_type === 'data_center' ? 'datacenters' : 'power-plants';
    if (!document.getElementById(`show-${layerId}`).checked) return false;
    const map = activeLayerContext?.map;
    return !map || layerShownAtZoom(layerId, map.getZoom());
  }

  function lifecycleStage(record) {
    if (record.record_type === 'power_plant') return 'operating';
    const status = record.status.toLowerCase();
    if (status === 'operating') return 'operating';
    if (/paused|blocked|prohibition|cancel/.test(status)) return 'paused';
    if (/permit|development|construction/.test(status)) return 'development';
    if (/proposed|concept|planned/.test(status)) return 'proposal';
    return 'other';
  }

  function isPlannedUncontestedDataCenter(record) {
    return record.record_type === 'data_center'
      && record.contestation_score === 0
      && ['proposal', 'development'].includes(lifecycleStage(record));
  }

  function matchesEnergySource(record, energyFilter) {
    if (energyFilter === 'all') return true;
    const codes = markerSourceCodes(record);
    if (energyFilter === 'UNKNOWN') return codes.length === 0;
    const families = {
      BIT: ['BIT', 'SUB', 'LIG', 'WC', 'RC'],
      NG: ['NG', 'PG'],
      DFO: ['DFO', 'RFO'],
      WASTE: ['LFG', 'MSW', 'MSB', 'MSN', 'OBG', 'WDS'],
    };
    return (families[energyFilter] || [energyFilter]).some((code) => codes.includes(code));
  }

  function renderResults(records, markerById) {
    const matches = records.filter((record) => matchesFilters(record));
    const matchedIds = new Set(matches.map((record) => record.id));
    const matchingDataCenters = matches.filter((record) => record.record_type === 'data_center');
    const dataCenterSizeFactors = pointScaleFactors(matchingDataCenters, layerFilters.datacenters.sizeBy);
    records.forEach((record) => {
      const marker = markerById.get(record.id);
      if (!marker) return;
      applyMarkerAppearance(record, marker.getElement());
      const size = 22 * (dataCenterSizeFactors.get(record) || 1);
      marker.getElement().style.setProperty('--marker-size', `${size}px`);
      marker.getElement().hidden = !matchedIds.has(record.id);
    });
    syncDataCenterMarkerZOrder();
    visibleDataCenterHoverEntries = matchingDataCenters
      .filter((record) => Number.isFinite(record.latitude) && Number.isFinite(record.longitude) && markerById.has(record.id))
      .map((record) => ({
        record,
        size: 22 * (dataCenterSizeFactors.get(record) || 1),
      }))
      .sort((left, right) => left.size - right.size || left.record.id.localeCompare(right.record.id));
    powerPlantBoltLayer?.setRecords(matches.filter((record) => record.record_type === 'power_plant'));
    applyMapLayerOrder(activeLayerContext?.map);
  }

  function selectRecord(record, sourceById) {
    renderDetail(record, sourceById);
  }

  function renderHoveredInspector(key, render, layerId = null) {
    if (inspectorPinnedKey) return false;
    if (inspectorHoverKey === key) return false;
    inspectorHoverKey = key;
    inspectorHoverLayerId = layerId;
    updateLayerSelectionHighlight();
    render();
    return true;
  }

  function clearInspectorHover(prefix = null) {
    if (inspectorPinnedKey) return;
    if (prefix && !inspectorHoverKey?.startsWith(prefix)) return;
    inspectorHoverKey = null;
    inspectorHoverLayerId = null;
    updateLayerSelectionHighlight();
  }

  function pinInspector(key, render, layerId = null) {
    inspectorPinnedKey = key;
    inspectorHoverKey = key;
    inspectorPinnedLayerId = layerId;
    inspectorHoverLayerId = layerId;
    updateLayerSelectionHighlight();
    render();
    document.querySelector('.dc-detail').classList.add('is-pinned');
    document.getElementById('close-record-detail').hidden = false;
    return true;
  }

  function closePinnedInspector() {
    inspectorPinnedKey = null;
    inspectorHoverKey = null;
    inspectorPinnedLayerId = null;
    inspectorHoverLayerId = null;
    updateLayerSelectionHighlight();
    document.querySelector('.dc-detail').classList.remove('is-pinned');
    document.getElementById('close-record-detail').hidden = true;
    const detail = prepareInspectorDetail();
    detail.innerHTML = '<h2>Hover a map icon</h2><p>Move over a visible icon or map feature to see what it represents.</p>';
  }

  function pinHoverTarget(target) {
    if (!target) return false;
    clearTimeout(parcelHoverTimer);
    parcelHoverAbort?.abort();
    pinInspector(target.key, target.render, target.layerId);
    return true;
  }

  function pinRecord(record, sourceById) {
    pinInspector(`record:${record.id}`, () => selectRecord(record, sourceById), recordLayerId(record));
  }

  function selectHoveredRecord(record, sourceById) {
    renderHoveredInspector(`record:${record.id}`, () => selectRecord(record, sourceById), recordLayerId(record));
  }

  function recordLayerId(record) {
    return record?.record_type === 'power_plant' ? 'power-plants' : 'datacenters';
  }

  function updateLayerSelectionHighlight() {
    document.querySelectorAll('.dc-layer-option[data-layer-preview]').forEach((card) => {
      const layerId = card.dataset.layerPreview;
      const isPinned = layerId === inspectorPinnedLayerId;
      const isHovered = layerId === inspectorHoverLayerId && !isPinned;
      card.classList.toggle('is-source-pinned', isPinned);
      card.classList.toggle('is-source-hovered', isHovered);
      if (isPinned) {
        card.setAttribute('aria-current', 'true');
        card.dataset.selectedFeatureState = 'Pinned selected feature';
      } else if (isHovered) {
        card.setAttribute('aria-current', 'true');
        card.dataset.selectedFeatureState = 'Hovered selected feature';
      } else {
        card.removeAttribute('aria-current');
        delete card.dataset.selectedFeatureState;
      }
    });
  }

  function matchesFilters(record) {
      if (!visibleType(record)) return false;
      const isDataCenter = record.record_type === 'data_center';
      const statusFilter = isDataCenter ? layerFilters.datacenters.status : 'all';
      const energyFilter = isDataCenter ? layerFilters.datacenters.energy : layerFilters.powerPlants.energy;
      const sentimentFilter = isDataCenter ? layerFilters.datacenters.sentiment : 'all';
      const powerScaleFilter = isDataCenter ? layerFilters.datacenters.powerScale : 'all';
      const textFilter = isDataCenter ? layerFilters.datacenters.text : layerFilters.powerPlants.text;
      const lifecycle = lifecycleStage(record);
      if (statusFilter === 'unbuilt' && record.projected_power_demand_mw == null) return false;
      if (statusFilter !== 'all' && statusFilter !== 'unbuilt' && lifecycle !== statusFilter) return false;
      if (!matchesEnergySource(record, energyFilter)) return false;
      if (sentimentFilter !== 'all') {
        if (record.record_type !== 'data_center') return false;
        const score = record.public_sentiment_score;
        if (sentimentFilter === 'opposed' && !(score < 0)) return false;
        if (sentimentFilter === 'supportive' && !(score > 0)) return false;
        if (sentimentFilter === 'mixed' && score !== 0) return false;
        if (sentimentFilter === 'unknown' && score !== null) return false;
      }
      if (powerScaleFilter !== 'all' && record.power_scale_class !== powerScaleFilter) return false;
      const haystack = [record.name, record.operator, record.county, record.city, record.primary_technology, ...(record.technology_tags || [])]
        .filter(Boolean).join(' ').toLowerCase();
      if (textFilter && !haystack.includes(textFilter)) return false;
      if (activeTagFilters.length) {
        const recordTags = new Set(recordFilterTagLabels(record).map((tag) => tag.toLowerCase()));
        const matchesTags = tagFilterMode === 'or'
          ? activeTagFilters.some((tag) => recordTags.has(tag.toLowerCase()))
          : activeTagFilters.every((tag) => recordTags.has(tag.toLowerCase()));
        if (!matchesTags) return false;
      }
      return true;
  }

  function splitTagLabel(label) {
    return String(label || '')
      .split(/\s*(?:\/|\band\b)\s*/i)
      .map((part) => part.trim())
      .filter(Boolean);
  }

  function recordYearBuiltTag(record) {
    if (Number.isInteger(record.year_built)) return `Built ${record.year_built}`;
    if (record.year_built_status === 'not built') return 'Not built';
    return 'Year unknown';
  }

  function recordFilterTagLabels(record) {
    const attributes = record.record_type === 'power_plant'
      ? ['energy', 'technology', 'scale']
      : ['energy', 'lifecycle', 'sentiment'];
    const labels = [
      record.record_type === 'power_plant' ? 'Power' : 'Data Center',
      ...attributes.flatMap((attribute) => stylePaletteForRecord(record, attribute).map((entry) => entry.label)),
      recordYearBuiltTag(record),
      ...(record.record_type === 'data_center' && record.power_scale_tag ? [record.power_scale_tag] : []),
      ...(record.record_type === 'data_center' && record.contestation_label ? [`Contestation: ${record.contestation_label}`] : []),
      ...(record.status_tags || []),
      ...(record.technology_tags || []),
    ].flatMap(splitTagLabel);
    return labels.filter((label, index, all) => all.findIndex((candidate) => candidate.toLowerCase() === label.toLowerCase()) === index);
  }

  function powerScaleTagColor(record) {
    return {
      'sub-megawatt': '#8fd2ed',
      small: '#4db6ac',
      medium: '#f3c969',
      large: '#f29e4c',
      'very-large': '#ff665e',
      unknown: '#7f93a5',
    }[record.power_scale_class] || '#7f93a5';
  }

  function contestationColor(record) {
    return ['#668096', '#89a9bc', '#e0b052', '#e77b45', '#d94b50'][record.contestation_score] || '#668096';
  }

  function iconStyleDescription(record) {
    const isPowerPlant = record.record_type === 'power_plant';
    const filters = isPowerPlant ? layerFilters.powerPlants : layerFilters.datacenters;
    const colorPalette = stylePaletteForRecord(record, filters.colorBy);
    const outlinePalette = filters.outlineBy === 'none' ? [] : stylePaletteForRecord(record, filters.outlineBy);
    const category = isPowerPlant ? 'Power' : 'Data Center';
    const tags = [
      { label: category, color: '#72b7d2' },
      ...colorPalette.map((entry) => ({ label: entry.label, color: entry.color })),
      ...outlinePalette.map((entry) => ({ label: entry.label, color: entry.color })),
      { label: recordYearBuiltTag(record), color: '#8fd2ed' },
      ...(record.record_type === 'data_center' && record.power_scale_tag
        ? [{ label: record.power_scale_tag, color: powerScaleTagColor(record) }]
        : []),
      ...(record.record_type === 'data_center' && record.contestation_label
        ? [{ label: `Contestation: ${record.contestation_label}`, color: contestationColor(record) }]
        : []),
      ...(record.status_tags || []).map((label) => ({ label, color: '#f3a712' })),
      ...(record.technology_tags || []).map((label) => ({ label, color: '#657887' })),
    ]
      .flatMap((tag) => splitTagLabel(tag.label).map((label) => ({ ...tag, label })))
      .filter((tag, index, all) => all.findIndex((candidate) => candidate.label.toLowerCase() === tag.label.toLowerCase()) === index);
    return {
      fill: isPowerPlant ? markerAccentColor(record, filters.colorBy) : iconFillForRecord(record, filters.colorBy),
      outline: outlineColorForRecord(record, filters.outlineBy),
      shapeClass: isPowerPlant ? 'power' : 'datacenter',
      tags,
    };
  }

  function renderHoveredIconHeading(record) {
    const icon = iconStyleDescription(record);
    return `
      <div class="dc-hovered-icon-heading">
        <span class="dc-hovered-icon dc-hovered-icon--${icon.shapeClass}" style="--dc-hovered-fill: ${escapeHtml(icon.fill)}; --dc-hovered-outline: ${escapeHtml(icon.outline)}" aria-hidden="true"></span>
        <div>
          <h2>${escapeHtml(record.name)}</h2>
          <div class="dc-hover-tags" aria-label="Record tags">
            ${icon.tags.map((tag) => `<button type="button" class="dc-hover-tag" style="--dc-tag-color: ${escapeHtml(tag.color)}" data-filter-tag="${escapeHtml(tag.label)}" aria-label="Filter map by ${escapeHtml(tag.label)}" aria-pressed="${activeTagFilters.some((active) => active.toLowerCase() === tag.label.toLowerCase())}">${escapeHtml(tag.label)}</button>`).join('')}
          </div>
        </div>
      </div>`;
  }

  function renderDetail(record, sourceById) {
    const detail = prepareInspectorDetail();
    if (record.record_type === 'data_center') {
      const recordSourceIds = [...new Set([
        ...(record.source_ids || []),
        ...(record.profile_source_ids || []),
        ...(record.year_built_source_ids || []),
        ...(record.status_source_ids || []),
        ...(record.power_scale_source_ids || []),
        ...(record.projected_power_demand_source_ids || []),
        ...(record.contestation_source_ids || []),
        ...(record.salient_news_source_ids || []),
      ])];
      detail.innerHTML = `
        ${renderHoveredIconHeading(record)}
        ${renderEnergySummary(record)}
        <p class="dc-type">Facility record · ${escapeHtml(record.status)}</p>
        ${renderContestationSpotlight(record, sourceById)}
        ${renderDatacenterImage(record)}
        ${renderFactGroup('Facility', [
          ['Operator', known(record.operator)],
          ['Owner', known(record.owner)],
          ['Address', known([record.street_address, record.city, record.state, record.postal_code].filter(Boolean).join(', '))],
          ['Year built', Number.isInteger(record.year_built) ? `${record.year_built} · ${escapeHtml(record.year_built_basis)}` : `${known(record.year_built_status)} · ${escapeHtml(record.year_built_basis)}`],
          ['Development status', known(record.development_status)],
          ['Plan', known(record.plan_detail)],
          ['Buildings', known(record.building_count)],
          ['Personnel', known(record.employees_current)],
          ['Committed jobs', known(record.employees_committed)],
        ])}
        ${renderFactGroup('Hardware and likely workflows', [
          ['Technologies', known(record.technology_tags?.join(', '))],
          ['Hardware', known(record.hardware_detail)],
          ['Likely workflows', known(record.likely_workflows_detail)],
          ['Evidence basis', known(record.hardware_workflow_basis)],
        ])}
        ${renderFactGroup('Energy and resilience', [
          ['Power class', `${escapeHtml(record.power_scale_label)}${record.power_scale_mw == null ? '' : ` · ${number(record.power_scale_mw, 2)} MW`} · ${escapeHtml(record.power_scale_value_kind)}`],
          ['Classification basis', known(record.power_scale_detail)],
          ['Estimated power draw', record.estimated_power_draw_mw == null ? known(null) : `${number(record.estimated_power_draw_mw, 2)} MW · ${escapeHtml(record.estimated_power_draw_confidence || 'unknown confidence')}`],
          ['Estimate basis', known(record.estimated_power_draw_basis)],
          ['Projected demand', record.projected_power_demand_mw == null ? known(null) : `${number(record.projected_power_demand_mw, 2)} MW · ${escapeHtml(record.projected_power_demand_confidence || 'unknown confidence')}`],
          ['Projection basis', known(record.projected_power_demand_basis)],
          ['Power capacity', record.reported_power_capacity_mw == null ? known(null) : `${number(record.reported_power_capacity_mw, 2)} MW · ${escapeHtml(record.reported_power_capacity_basis)}`],
          ['Grid demand', known(record.reported_grid_demand_mw, ' MW')],
          ['Annual energy', known(record.reported_annual_energy_mwh, ' MWh')],
          ['PUE', known(record.reported_pue)],
          ['Gas plant', known(record.on_site_natural_gas_power_plant)],
          ['Backup', known(record.backup_generator_detail)],
          ['Backup total', known(record.backup_generator_capacity_mw, ' MW')],
          ['UPS', known(record.ups_technology)],
          ['UPS power', known(record.ups_capacity_mw, ' MW')],
          ['UPS energy', known(record.ups_energy_mwh, ' MWh')],
          ['Cooling/water', known(record.cooling_water_detail)],
        ])}
        ${renderFactGroup('Permits, finance, and public response', [
          ['Permit status', known(record.permit_status)],
          ['Air permit', known(record.air_permit_status)],
          ['Legal status', known(record.legal_status)],
          ['Permit evidence', known(record.permit_detail)],
          ['Financing', known(record.financing_detail)],
          ['Investment', record.capital_investment_usd == null ? known(null) : `$${number(record.capital_investment_usd)}`],
          ['Public funding', known(record.public_funding_detail)],
          ['Opposition', known(record.public_opposition_status)],
          ['Sentiment', renderSentiment(record)],
          ['Rating basis', known(record.sentiment_basis)],
          ['Contestation', `${escapeHtml(record.contestation_label)} · ${escapeHtml(record.contestation_category)}`],
          ['Contestation basis', known(record.contestation_basis)],
        ])}
        <p class="dc-record-note">${escapeHtml(record.notes)}</p>
        ${renderRecordSources(recordSourceIds, sourceById)}
      `;
    } else {
      detail.innerHTML = `
        ${renderHoveredIconHeading(record)}
        <p class="dc-type">EIA plant ${record.eia_plant_code}</p>
        ${renderEnergySummary(record)}
        ${renderPlantImage(record)}
        ${renderFactGroup('Plant profile', [
          ['Operator', known(record.operator)],
          ['County', known(record.county)],
          ['Earliest operating year', Number.isInteger(record.year_built) ? `${record.year_built} · ${escapeHtml(record.year_built_basis)}` : known(record.year_built_status)],
          ['Generator status', known(record.development_status)],
          ['EIA status codes', known(record.generator_status_codes?.join(', '))],
          ['Primary technology', known(record.primary_technology)],
          ['All technologies', known(record.technology_tags?.join(', '))],
          ['Fuel codes', known(record.energy_source_codes.join(', '))],
          ['Coordinate confidence', known(`${record.coordinate_confidence} · ${record.latitude_decimal_places}/${record.longitude_decimal_places} decimal places`)],
          ['Shared coordinate', record.shared_coordinate_count > 1 ? `Yes · ${record.shared_coordinate_count} plant records` : 'No'],
          ['Aerial frame', `${number(record.aerial_frame_width_m)} × ${number(record.aerial_frame_height_m)} m`],
        ])}
        ${renderFactGroup('Production', [
          ['Capacity', known(record.nameplate_capacity_mw, ' MW')],
          ['Planning output', record.planning_sustained_output_mw == null ? known(null) : `${number(record.planning_sustained_output_mw, 2)} MW`],
          ['Capacity factor', record.annual_capacity_factor == null ? known(null) : `${number(record.annual_capacity_factor * 100, 1)}%`],
          ['Planning basis', known(record.planning_output_basis)],
          ['Generators', known(record.generator_count)],
          ['Average generation', powerPlantAverageGeneration(record) == null ? known(null) : `${number(powerPlantAverageGeneration(record), 1)} MWh`],
        ])}
        ${renderFactGroup('Permits and legal research', [
          ['Permit status', known(record.permit_status)],
          ['Air permit', known(record.air_permit_status)],
          ['Legal status', known(record.legal_status)],
        ])}
        <p class="dc-record-note">${escapeHtml(record.coordinate_confidence_basis)}</p>
        ${renderRecordSources([...new Set([
          record.capacity_source_id,
          record.generation_source_id,
          ...(record.year_built_source_ids || []),
          ...(record.status_source_ids || []),
        ].filter(Boolean))], sourceById)}
      `;
    }
    bindInspectorTagFilters(detail);
    bindPlantImageFallback(detail, record);
    setupInspectorAnimation(detail, record);
  }

  function renderEnergySummary(record) {
    if (record.record_type === 'power_plant') {
      const generation = powerPlantAverageGeneration(record);
      return `<section class="dc-energy-summary" aria-label="Power plant generation summary">
        <div><span>Planning output</span><strong>${record.planning_sustained_output_mw == null ? known(null) : `${number(record.planning_sustained_output_mw, 2)} MW`}</strong><small>annual average, not peak capacity</small></div>
        <div><span>Average generation</span><strong>${generation == null ? known(null) : `${number(generation, 1)} MWh`}</strong></div>
        <div><span>Nameplate capacity</span><strong>${record.nameplate_capacity_mw == null ? known(null) : `${number(record.nameplate_capacity_mw, 2)} MW`}</strong></div>
      </section>`;
    }

    const projectedDemand = record.projected_power_demand_mw;
    const demandValue = projectedDemand ?? record.reported_grid_demand_mw ?? record.estimated_power_draw_mw;
    const demand = demandValue == null
      ? known(null)
      : `${number(demandValue, 2)} MW`;
    const demandBasis = projectedDemand != null
      ? `${record.projected_power_demand_confidence || 'unknown'}-confidence planning estimate; facility is not operating`
      : record.reported_grid_demand_mw == null && record.reported_power_capacity_mw != null
      ? `${record.estimated_power_draw_confidence || 'estimated'} estimate; ${number(record.reported_power_capacity_mw, 2)} MW published capacity envelope`
      : record.reported_grid_demand_mw == null
        ? `${record.estimated_power_draw_confidence || 'estimated'} estimate; measured demand not public`
        : 'Reported operating grid demand';
    const onsiteGeneration = record.on_site_generation_capacity_mw == null
      ? known(null)
      : `${number(record.on_site_generation_capacity_mw, 2)} MW`;
    const onsiteBasis = [record.on_site_generation_technology, record.on_site_natural_gas_power_plant]
      .filter(Boolean).join(' · ') || 'No normal on-site generation figure found in the reviewed sources';
    return `<section class="dc-energy-summary" aria-label="Data center energy summary">
      <div><span>${projectedDemand != null ? 'Projected grid demand' : 'Required grid power'}</span><strong>${demand}</strong><small>${escapeHtml(demandBasis)}</small></div>
      <div><span>Normal on-site generation</span><strong>${onsiteGeneration}</strong><small>${escapeHtml(onsiteBasis)}</small></div>
    </section>`;
  }

  function renderDatacenterImage(record) {
    return renderEntityImage(record) + renderSiteAnimation(record);
  }

  function renderPlantImage(record) {
    return renderEntityImage(record) + renderSiteAnimation(record);
  }

  function renderEntityImage(record) {
    const image = record.entity_image;
    if (!image?.local_path) return '';
    const attribution = [image.creator, image.license].filter(Boolean).join(' · ');
    return `<figure class="dc-entity-image">
      <img src="${escapeHtml(image.local_path)}" alt="${escapeHtml(image.alt || record.name)}" loading="lazy" decoding="async">
      <figcaption><strong>Entity photograph</strong><span>${escapeHtml(attribution || 'Source-verified image')}</span>${image.source_page_url ? `<a href="${escapeHtml(image.source_page_url)}" target="_blank" rel="noopener noreferrer">Image source</a>` : ''}</figcaption>
    </figure>`;
  }

  function renderSiteAnimation(record) {
    const dimensions = aerialDimensionsForRecord(record);
    const liveUrl = usgsAerialImageUrl(record);
    return `
      <section class="dc-site-gallery" data-site-animation aria-label="Animated aerial view">
        <figure class="dc-plant-image dc-plant-image--aerial dc-site-animation" data-gallery-scale="campus">
          <div class="dc-aerial-viewport">
            <div class="dc-aerial-motion">
              <img src="${TRANSPARENT_IMAGE}" data-live-aerial-url="${escapeHtml(liveUrl)}" data-fallback="${PLANT_IMAGE_FALLBACK}" alt="Animated campus aerial centered on ${escapeHtml(record.name)}" decoding="async">
              <svg class="dc-parcel-outline" data-parcel-outline viewBox="0 0 ${AERIAL_IMAGE_WIDTH} ${AERIAL_IMAGE_HEIGHT}" preserveAspectRatio="none" role="img" aria-label="MDP/SDAT parcel boundary">
                <path data-parcel-outline-path></path>
              </svg>
            </div>
            <span class="dc-parcel-outline-status" data-parcel-outline-status>Locating MDP/SDAT parcel…</span>
            <details class="dc-aerial-settings">
              <summary aria-label="Adjust aerial animation" title="Animation settings">⚙</summary>
              <div class="dc-aerial-settings-menu">
                <label>Speed <output data-aerial-speed-output>${number(aerialAnimationSettings.speed, 3)}×</output>
                  <input data-aerial-speed type="range" min="0.025" max="10" step="0.025" value="${aerialAnimationSettings.speed}">
                </label>
                <label>Zoom travel <output data-aerial-distance-output>${number(aerialAnimationSettings.distance, 3)}×</output>
                  <input data-aerial-distance type="range" min="0.025" max="2" step="0.025" value="${aerialAnimationSettings.distance}">
                </label>
              </div>
            </details>
          </div>
          <figcaption>
            <strong data-aerial-status>Campus aerial · loading</strong>
            <span data-aerial-frame-description>${number(dimensions.widthMeters)} × ${number(dimensions.heightMeters)} m provisional frame. The live MDP/SDAT parcel bounds replace it when available.</span>
            <a href="${USGS_IMAGERY_SOURCE}" target="_blank" rel="noopener noreferrer">USGS source</a>
          </figcaption>
        </figure>
      </section>`;
  }

  function aerialFrameForRecord(record) {
    const defaultWidth = record.record_type === 'data_center' ? 700 : 2750;
    const defaultHeight = record.record_type === 'data_center' ? 500 : 2000;
    return {
      widthMeters: Number(record.aerial_frame_width_m) || defaultWidth,
      heightMeters: Number(record.aerial_frame_height_m) || defaultHeight,
    };
  }

  function aerialDimensionsForRecord(record) {
    const frame = aerialFrameForRecord(record);
    return {
      widthMeters: frame.widthMeters * 1.8,
      heightMeters: frame.heightMeters * 1.8,
    };
  }

  function usgsAerialImageUrlForBounds(bounds) {
    const bbox = [bounds.west, bounds.south, bounds.east, bounds.north].join(',');
    const parameters = new URLSearchParams({
      bbox,
      bboxSR: '4326',
      imageSR: '4326',
      size: `${AERIAL_IMAGE_WIDTH},${AERIAL_IMAGE_HEIGHT}`,
      format: 'jpg',
      transparent: 'false',
      f: 'image',
    });
    return `${USGS_IMAGERY_SOURCE}/export?${parameters}`;
  }

  function usgsAerialImageUrl(record) {
    return usgsAerialImageUrlForBounds(aerialBoundsForRecord(record));
  }

  function releaseAerialObjectUrls(container) {
    container.querySelectorAll('[data-aerial-object-url]').forEach((image) => {
      URL.revokeObjectURL(image.dataset.aerialObjectUrl);
    });
  }

  function prepareInspectorDetail() {
    const detail = document.getElementById('record-detail');
    inspectorParcelAbort?.abort();
    releaseAerialObjectUrls(detail);
    return detail;
  }

  function showAerialBlob(detail, image, url, blob, status) {
    if (!detail.contains(image) || image.dataset.liveAerialUrl !== url) return false;
    if (image.dataset.aerialObjectUrl) URL.revokeObjectURL(image.dataset.aerialObjectUrl);
    const objectUrl = URL.createObjectURL(blob);
    image.dataset.aerialObjectUrl = objectUrl;
    image.src = objectUrl;
    image.classList.remove('is-aerial-ready');
    void image.offsetWidth;
    image.classList.add('is-aerial-ready');
    const motion = image.closest('.dc-aerial-motion');
    motion?.classList.remove('is-aerial-ready');
    if (motion) void motion.offsetWidth;
    motion?.classList.add('is-aerial-ready');
    const label = image.closest('figure')?.querySelector('[data-aerial-status]');
    if (label) {
      const scale = image.closest('figure').dataset.galleryScale;
      label.textContent = `${scale[0].toUpperCase()}${scale.slice(1)} aerial · ${status}`;
    }
    return true;
  }

  async function hydrateLiveAerialImage(detail, image, record) {
    if (!image || image.dataset.hydrationStarted) return;
    image.dataset.hydrationStarted = 'true';
    const url = image.dataset.liveAerialUrl;
    let displayedCachedImage = false;

    if ('caches' in window) {
      try {
        const cache = await caches.open(AERIAL_IMAGE_CACHE);
        const cached = await cache.match(url);
        if (cached) {
          displayedCachedImage = showAerialBlob(detail, image, url, await cached.blob(), 'Cached aerial context');
        }
      } catch (error) {
        console.warn('Aerial image cache read failed', error);
      }
    }

    if (!detail.contains(image) || image.dataset.liveAerialUrl !== url) return;
    try {
      const response = await fetch(url, { cache: 'no-store', mode: 'cors' });
      if (!response.ok) throw new Error(`USGS imagery returned HTTP ${response.status}`);
      const cacheCopy = response.clone();
      const shown = showAerialBlob(detail, image, url, await response.blob(), 'Fresh USGS aerial context');
      if (shown && 'caches' in window) {
        caches.open(AERIAL_IMAGE_CACHE)
          .then((cache) => cache.put(url, cacheCopy))
          .catch((error) => console.warn('Aerial image cache update failed', error));
      }
    } catch (error) {
      if (displayedCachedImage || !detail.contains(image) || image.dataset.liveAerialUrl !== url) return;
      image.src = image.dataset.fallback;
      image.classList.remove('is-aerial-ready');
      image.closest('.dc-aerial-motion')?.classList.remove('is-aerial-ready');
      image.alt = `Generated infrastructure illustration for ${record.name}`;
      const figure = image.closest('.dc-plant-image');
      figure.classList.remove('dc-plant-image--aerial');
      figure.classList.add('dc-plant-image--illustration');
      const label = figure.querySelector('[data-aerial-status]');
      if (label) label.textContent = 'Aerial imagery unavailable';
    }
  }

  function normalizeAerialAnimationSettings(settings = {}) {
    const speed = Math.min(10, Math.max(.025, Number(settings?.speed) || 1));
    const distance = Math.min(2, Math.max(.025, Number(settings?.distance) || 1));
    return { speed, distance };
  }

  function applyAerialAnimationSettings(gallery) {
    const { speed, distance } = aerialAnimationSettings;
    gallery.style.setProperty('--dc-aerial-duration', `${18 / speed}s`);
    gallery.style.setProperty('--dc-aerial-zoom', String(1 + distance));
    gallery.style.setProperty('--dc-aerial-pan-x', `${-distance * 16}%`);
    gallery.style.setProperty('--dc-aerial-pan-y', `${distance * 10}%`);
    gallery.querySelectorAll('[data-aerial-speed]').forEach((input) => { input.value = String(speed); });
    gallery.querySelectorAll('[data-aerial-distance]').forEach((input) => { input.value = String(distance); });
    gallery.querySelectorAll('[data-aerial-speed-output]').forEach((output) => { output.value = `${number(speed, 3)}×`; });
    gallery.querySelectorAll('[data-aerial-distance-output]').forEach((output) => { output.value = `${number(distance, 3)}×`; });
  }

  function setupAerialAnimationControls(gallery) {
    applyAerialAnimationSettings(gallery);
    gallery.querySelectorAll('[data-aerial-speed], [data-aerial-distance]').forEach((input) => {
      input.addEventListener('input', () => {
        aerialAnimationSettings = normalizeAerialAnimationSettings({
          speed: input.matches('[data-aerial-speed]') ? input.value : aerialAnimationSettings.speed,
          distance: input.matches('[data-aerial-distance]') ? input.value : aerialAnimationSettings.distance,
        });
        applyAerialAnimationSettings(gallery);
        persistUiState();
      });
    });
  }

  function setupInspectorAnimation(detail, record) {
    const animation = detail.querySelector('[data-site-animation]');
    if (!animation) return;
    setupAerialAnimationControls(animation);
    const initialAerial = hydrateLiveAerialImage(detail, animation.querySelector('[data-live-aerial-url]'), record);
    initialAerial.then(() => scheduleInspectorParcelOutline(detail, animation, record));
  }

  function scheduleInspectorParcelOutline(detail, animation, record) {
    const hydrate = () => {
      if (!detail.contains(animation)) return;
      hydrateInspectorParcelOutline(detail, animation, record);
    };
    if ('requestIdleCallback' in window) {
      window.requestIdleCallback(hydrate, { timeout: 2500 });
    } else {
      window.setTimeout(hydrate, 0);
    }
  }

  function aerialBoundsForRecord(record) {
    const { widthMeters, heightMeters } = aerialDimensionsForRecord(record);
    const metersPerLatitudeDegree = 111320;
    const metersPerLongitudeDegree = metersPerLatitudeDegree * Math.cos(record.latitude * Math.PI / 180);
    const halfLongitude = (widthMeters / 2) / metersPerLongitudeDegree;
    const halfLatitude = (heightMeters / 2) / metersPerLatitudeDegree;
    return {
      west: record.longitude - halfLongitude,
      south: record.latitude - halfLatitude,
      east: record.longitude + halfLongitude,
      north: record.latitude + halfLatitude,
    };
  }

  function parcelGeometryPath(geometry, bounds) {
    const polygons = geometry?.type === 'Polygon'
      ? [geometry.coordinates]
      : geometry?.type === 'MultiPolygon' ? geometry.coordinates : [];
    const project = ([longitude, latitude]) => [
      ((longitude - bounds.west) / (bounds.east - bounds.west)) * AERIAL_IMAGE_WIDTH,
      ((bounds.north - latitude) / (bounds.north - bounds.south)) * AERIAL_IMAGE_HEIGHT,
    ];
    return polygons.flatMap((polygon) => polygon.map((ring) => ring
      .map((coordinate, index) => {
        const [x, y] = project(coordinate);
        return `${index ? 'L' : 'M'}${x.toFixed(2)},${y.toFixed(2)}`;
      })
      .join(' ') + ' Z'))
      .join(' ');
  }

  function parcelGeometryBounds(geometry) {
    const depth = geometry?.type === 'Polygon' ? 1 : geometry?.type === 'MultiPolygon' ? 2 : null;
    if (depth === null) return null;
    const coordinates = geometry.coordinates.flat(depth);
    const longitudes = coordinates.map((coordinate) => Number(coordinate[0])).filter(Number.isFinite);
    const latitudes = coordinates.map((coordinate) => Number(coordinate[1])).filter(Number.isFinite);
    if (!longitudes.length || !latitudes.length) return null;
    const bounds = {
      west: Math.min(...longitudes),
      south: Math.min(...latitudes),
      east: Math.max(...longitudes),
      north: Math.max(...latitudes),
    };
    return bounds.east > bounds.west && bounds.north > bounds.south ? bounds : null;
  }

  async function hydrateInspectorParcelOutline(detail, animation, record) {
    const status = animation.querySelector('[data-parcel-outline-status]');
    const path = animation.querySelector('[data-parcel-outline-path]');
    const parameters = new URLSearchParams({
      geometry: `${record.longitude},${record.latitude}`,
      geometryType: 'esriGeometryPoint',
      inSR: '4326',
      spatialRel: 'esriSpatialRelIntersects',
      outFields: 'ACCTID,ADDRESS,ACRES,DESCLU',
      returnGeometry: 'true',
      outSR: '4326',
      geometryPrecision: '7',
      resultRecordCount: '1',
      f: 'geojson',
    });
    inspectorParcelAbort = new AbortController();
    try {
      const response = await fetch(`${PARCEL_SERVICE}/0/query?${parameters}`, { signal: inspectorParcelAbort.signal });
      if (!response.ok) throw new Error(`MDP/SDAT service returned HTTP ${response.status}`);
      const data = await response.json();
      if (!detail.contains(animation)) return;
      const feature = data.features?.[0];
      if (!feature?.geometry) {
        status.textContent = 'No intersecting MDP/SDAT parcel returned';
        return;
      }
      const parcelBounds = parcelGeometryBounds(feature.geometry);
      if (!parcelBounds) throw new Error('MDP/SDAT returned parcel geometry without usable bounds');
      path.setAttribute('d', parcelGeometryPath(feature.geometry, parcelBounds));
      const image = animation.querySelector('[data-live-aerial-url]');
      image.dataset.liveAerialUrl = usgsAerialImageUrlForBounds(parcelBounds);
      delete image.dataset.hydrationStarted;
      hydrateLiveAerialImage(detail, image, record);
      const frameDescription = animation.querySelector('[data-aerial-frame-description]');
      frameDescription.textContent = 'Aerial extent matches the exact MDP/SDAT parcel bounding box. The animation moves from the full parcel to the selected inward zoom.';
      const properties = feature.properties || {};
      const description = [properties.ACCTID, properties.ADDRESS, properties.ACRES ? `${properties.ACRES} acres` : null]
        .filter(Boolean)
        .join(' · ');
      status.textContent = `MDP/SDAT parcel${description ? ` · ${description}` : ''}`;
    } catch (error) {
      if (error.name === 'AbortError' || !detail.contains(animation)) return;
      status.textContent = `Parcel outline unavailable · ${error.message}`;
    }
  }

  function bindPlantImageFallback(detail, record) {
    detail.querySelectorAll('.dc-entity-image img').forEach((image) => image.addEventListener('error', () => {
      image.closest('.dc-entity-image')?.remove();
    }, { once: true }));
    detail.querySelectorAll('.dc-plant-image img').forEach((image) => image.addEventListener('error', () => {
      if (image.dataset.fallbackApplied) return;
      image.dataset.fallbackApplied = 'true';
      image.src = image.dataset.fallback;
      image.alt = `Generated energy infrastructure illustration for ${record.name}`;
      const figure = image.closest('.dc-plant-image');
      figure.classList.remove('dc-plant-image--aerial', 'dc-plant-image--verified');
      figure.classList.add('dc-plant-image--illustration');
      figure.querySelector('figcaption').innerHTML = `
        <strong>Generated fallback illustration</strong>
        <span>Illustrative energy infrastructure; not a depiction of ${escapeHtml(record.name)}.</span>`;
    }, { once: true }));
  }

  function renderFactGroup(title, rows) {
    const facts = rows.map(([label, value]) => `<dt>${escapeHtml(label)}</dt><dd>${value}</dd>`).join('');
    return `<section class="dc-fact-group"><h3>${escapeHtml(title)}</h3><dl class="dc-facts">${facts}</dl></section>`;
  }

  function renderSentiment(record) {
    if (record.public_sentiment_score === null) {
      return `<span class="dc-sentiment dc-sentiment--unknown">Not scored · ${escapeHtml(record.public_sentiment_label)}</span>`;
    }
    const modifier = record.public_sentiment_score < 0 ? 'negative' : record.public_sentiment_score > 0 ? 'positive' : 'mixed';
    const signed = record.public_sentiment_score > 0 ? `+${record.public_sentiment_score}` : record.public_sentiment_score;
    return `<span class="dc-sentiment dc-sentiment--${modifier}">${signed} · ${escapeHtml(record.public_sentiment_label)}</span> <small>(${escapeHtml(record.sentiment_confidence)} confidence; assessed ${escapeHtml(record.sentiment_assessed_date)})</small>`;
  }

  function renderContestationSpotlight(record, sourceById) {
    const score = Number.isInteger(record.contestation_score) ? record.contestation_score : 0;
    const articles = (record.salient_news_source_ids || [])
      .map((id) => sourceById.get(id))
      .filter(Boolean);
    const links = articles.map((source) => `
      <a class="dc-salient-news-link" href="${escapeHtml(source.url)}" target="_blank" rel="noopener noreferrer">
        <strong>${escapeHtml(source.title)}</strong>
        <span>${escapeHtml(source.publisher)}${source.document_date ? ` · ${escapeHtml(source.document_date)}` : ''}</span>
      </a>`).join('');
    return `<section class="dc-contestation dc-contestation--${score}" aria-label="Contestation assessment">
      <div class="dc-contestation-heading">
        <span>Contestation</span>
        <strong>${escapeHtml(record.contestation_label)} · ${score}/4</strong>
      </div>
      ${links ? `<div class="dc-salient-news"><span>Salient coverage</span>${links}</div>` : '<small>No salient facility-specific news article was identified.</small>'}
      <p><b>${escapeHtml(record.contestation_category)}</b> · ${escapeHtml(record.contestation_basis)}</p>
    </section>`;
  }

  function renderRecordSources(ids, sourceById) {
    const links = (ids || []).map((id) => sourceById.get(id)).filter(Boolean).map((source) => {
      const href = source.local_path || source.url;
      return `<li><a href="${escapeHtml(href)}"${source.local_path ? '' : ' target="_blank" rel="noopener noreferrer"'}>${escapeHtml(source.title)}</a></li>`;
    }).join('');
    return links ? `<div class="dc-record-sources"><strong>Sources</strong><ul>${links}</ul></div>` : '';
  }

  function renderSources(sources) {
    document.getElementById('source-list').innerHTML = sources.map((source) => `
      <article class="dc-source-card">
        <h3>${escapeHtml(source.title)}</h3>
        <p>${escapeHtml(source.publisher)} · ${escapeHtml(source.source_tier)} · retrieved ${escapeHtml(source.retrieved_date)}</p>
        <p>${escapeHtml(source.used_for)}</p>
        <a href="${escapeHtml(source.local_path || source.url)}"${source.local_path ? '' : ' target="_blank" rel="noopener noreferrer"'}>${source.local_path ? 'Open archived copy' : 'Open source'}</a>${source.local_path ? ` · <a href="${escapeHtml(source.url)}" target="_blank" rel="noopener noreferrer">Publisher copy</a>` : ''}
      </article>
    `).join('');
  }
})();
