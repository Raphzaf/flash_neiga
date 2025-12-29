// craco.config.js (root)
// This config file enables CRACO to work when building from the repository root.
// It loads the frontend configuration and adjusts paths to be relative to root.

const path = require("path");
const frontendConfig = require("./frontend/craco.config.js");

// Override paths to point to the frontend directory
const frontendPath = path.resolve(__dirname, 'frontend');

// Create config by spreading the frontend config and overriding specific paths
const rootConfig = {
  ...frontendConfig,
  // Set the paths for react-scripts
  paths: (paths, { env }) => {
    // Update all paths to point to frontend directory
    paths.appPath = frontendPath;
    paths.appBuild = path.join(frontendPath, 'build');
    paths.appPublic = path.join(frontendPath, 'public');
    paths.appHtml = path.join(frontendPath, 'public/index.html');
    paths.appIndexJs = path.join(frontendPath, 'src/index.js');
    paths.appPackageJson = path.join(frontendPath, 'package.json');
    paths.appSrc = path.join(frontendPath, 'src');
    paths.appTsConfig = path.join(frontendPath, 'tsconfig.json');
    paths.appJsConfig = path.join(frontendPath, 'jsconfig.json');
    paths.yarnLockFile = path.join(frontendPath, 'yarn.lock');
    paths.testsSetup = path.join(frontendPath, 'src/setupTests');
    paths.proxySetup = path.join(frontendPath, 'src/setupProxy');
    paths.appNodeModules = path.resolve(__dirname, 'node_modules');
    paths.publicUrlOrPath = '/';
    
    return paths;
  },
  webpack: {
    ...frontendConfig.webpack,
    alias: {
      '@': path.resolve(__dirname, 'frontend/src'),
    },
    configure: (webpackConfig, { env, paths }) => {
      // Apply the frontend's configure function if it exists
      if (frontendConfig.webpack?.configure) {
        webpackConfig = frontendConfig.webpack.configure(webpackConfig, { env, paths });
      }
      
      return webpackConfig;
    },
  },
};

// Keep babel configuration from frontend if it exists
if (frontendConfig.babel) {
  rootConfig.babel = frontendConfig.babel;
}

// Keep devServer configuration from frontend if it exists
if (frontendConfig.devServer) {
  rootConfig.devServer = frontendConfig.devServer;
}

module.exports = rootConfig;
