/* App Module */

var adminApp = angular.module('adminApp', [
   'ui.slider',
  'ngRoute',

  'adminControllers',
  'adminServices'
]);



adminApp.run(function($rootScope) {
  // make underscore js availablie in templates	
  $rootScope._ = _;

  // make utilityfunction available in templates
  $rootScope.formatDuration = formatDuration;
});

adminApp.config(['$routeProvider',
  function($routeProvider) {
    $routeProvider.
      when('/dashboard', {
        templateUrl: 'partials/dashboard.html'
      }).when('/search', {
        templateUrl: 'partials/search.html',
        controller: 'SearchCtrl'
      }).when('/playlists', {
        templateUrl: 'partials/playlists.html'
      }).when('/mylibrary', {
        templateUrl: 'partials/mylibrary.html'
      }).when('/playqueue', {
          templateUrl: 'partials/playqueue.html'
      }).otherwise({
        redirectTo: '/dashboard'
      });
  }]);





