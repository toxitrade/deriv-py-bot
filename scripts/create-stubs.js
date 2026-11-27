const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');

// Crear directorios de stubs
const smartchartsDist = path.join(root, 'node_modules/@deriv-com/smartcharts-champion/dist');
const smartchartsRoot = path.join(root, 'node_modules/@deriv-com/smartcharts-champion');
const technicalRoot = path.join(root, 'node_modules/technicalindicators');

fs.mkdirSync(smartchartsDist, { recursive: true });
fs.mkdirSync(smartchartsRoot, { recursive: true });
fs.mkdirSync(technicalRoot, { recursive: true });

// smartcharts.css stub
fs.writeFileSync(
  path.join(smartchartsDist, 'smartcharts.css'),
  '/* stub */\n'
);

// smartcharts-champion index.js stub
fs.writeFileSync(
  path.join(smartchartsRoot, 'index.js'),
  `export const ChartMode = 'candles';\nexport const ChartTitle = '';\nexport const DrawTools = {};\nexport const Share = {};\nexport const setSmartChartsPublicPath = () => {};\nexport const SmartChart = () => null;\nexport const StudyLegend = {};\nexport const ToolbarWidget = {};\nexport const Views = {};\nexport default {};\n`
);

// smartcharts-champion package.json stub
fs.writeFileSync(
  path.join(smartchartsRoot, 'package.json'),
  JSON.stringify({
    name: '@deriv-com/smartcharts-champion',
    version: '1.9.13',
    main: 'index.js',
    exports: {
      '.': './index.js',
      './dist/smartcharts.css': './dist/smartcharts.css',
    },
  }, null, 2)
);

// technicalindicators index.js stub
fs.writeFileSync(
  path.join(technicalRoot, 'index.js'),
  `export const crossUp = () => false;\nexport const crossDown = () => false;\nexport default {};\n`
);

// technicalindicators package.json stub
fs.writeFileSync(
  path.join(technicalRoot, 'package.json'),
  JSON.stringify({
    name: 'technicalindicators',
    version: '3.1.0',
    main: 'index.js',
    exports: {
      '.': './index.js',
    },
  }, null, 2)
);

console.log('Stubs creados correctamente');
