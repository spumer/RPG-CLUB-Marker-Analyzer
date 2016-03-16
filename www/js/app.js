var settings = {
	url: '/api/dupe',
	timeout: 30
}
var app = angular.module('dupe-alert',['ngSanitize']);

app.controller('DupeController', ['$http','$scope',function($http,$scope){
	var ZCclient;
	var dupe = this;
	dupe.offers = [];
	//init wasted offers
	if (localStorage.oldOffers === undefined) {
		localStorage.oldOffers = '[]';
	}
	//init known offers
	if (localStorage.knownOffers === undefined) {
		localStorage.knownOffers = '[]';
	}
	//init filters
	$scope.minEquity = localStorage.minEquity || 1000000;
	$scope.maxRrequired = localStorage.maxRrequired || 20000000;
	$scope.minEquityOn = localStorage.minEquityOn === 'true';
	$scope.maxRrequiredOn = localStorage.maxRrequiredOn === 'true';
	
	//save filters
	$scope.savePrefs = function(){
		localStorage.minEquity = $scope.minEquity;
		localStorage.maxRrequired = $scope.maxRrequired;
		localStorage.minEquityOn = $scope.minEquityOn;
		localStorage.maxRrequiredOn = $scope.maxRrequiredOn;
	};
	
	//ng-filter for counting offers hidden by equity
	$scope.isHiddenByEquity = function(value, index){
		return value.equity < $scope.minEquity && $scope.minEquityOn;
	}
	//ng-filter for counting offers hidden by required adena
	$scope.isHiddenByRequired = function(value, index){
		return value.required_aden > $scope.maxRrequired && $scope.maxRrequiredOn;
	}
	
	//unknown offers modal window
	$('#unknownOffers').modal({
		show: false
	});
	$('#unknownOffers').on('hide.bs.modal',function(){
		//stop sound
		document.getElementById('shekeli').pause();
		
		//mark all offers as known
		var knownOffersArrayNew = [];
		for (var i = 0; i < dupe.offers.length; i++) {
			id = dupe.offers[i].seller.date + '' + dupe.offers[i].buyer.date;
			knownOffersArrayNew.push(id);
		}
		localStorage.knownOffers = JSON.stringify(knownOffersArrayNew);
	});
	
	var update = function(){
		$('.progress .progress-bar').animate({
			width: '100%'
		}, settings.timeout * 1000, 'linear', function(){
			$('.progress .progress-bar').css('width','0%');
		});
		$http.post(settings.url).success(function(data){
			dupe.offers = data;
			var oldOffersArray = JSON.parse(localStorage.oldOffers);
			var oldOffersArrayNew = [];
			var knownOffersArray = JSON.parse(localStorage.knownOffers);
			var knownOffersArrayNew = [];
			var id = "";
			var unknownOffer = false;
			for (var i = 0; i < dupe.offers.length; i++) {
				id = dupe.offers[i].seller.date + '' + dupe.offers[i].buyer.date;
				//is it old offer?
				if (oldOffersArray.indexOf(id) != -1) {
					//yeap, wasted
					dupe.offers[i].old = true;
					//show as wasted
					oldOffersArrayNew.push(id);
				} else {
					//unchecked offer
					dupe.offers[i].old = false;
				}
				//is it known offer?
				if ((knownOffersArray.indexOf(id) != -1) || (dupe.offers[i].equity < $scope.minEquity && $scope.minEquityOn) || (dupe.offers[i].required_aden > $scope.maxRrequired && $scope.maxRrequiredOn) ) {
					//yeap, nothing happens here
					//keep in known array
					knownOffersArrayNew.push(id);
				} else {
					//yay, new offers! flagged
					unknownOffer = true;
				}
			}
			//renew wasted array
			localStorage.oldOffers = JSON.stringify(oldOffersArrayNew);
			//renew knownArray
			localStorage.knownOffers = JSON.stringify(knownOffersArrayNew);
			
			//show modal window, play sound
			if (unknownOffer) {
				$('#unknownOffers').modal('show');
				document.getElementById('shekeli').play();
			}
		});
	}
	update();
	setInterval(update, settings.timeout * 1000);
}]);

app.filter('trisect', function(){
	return function(input){
		input = '' + (input || '');
		var out = "";
		var out3 = "";
		var j = 0;
		for (var i = input.length - 1; i > -1; i--) {
			out3 = input.charAt(i) + out3;
			if (j%3 == 2) {
				out = '<span class="dec-sp">' + out3 + '</span>' + out;
				out3 = "";
			}
			j++;
		}
		if (out3 != "") {
			out = '<span class="dec-sp">' + out3 + '</span>' + out;
		}
		return out;
	};
});

app.filter('noloc', function(){
	return function(input){
		input = '' + (input || '');
		return input.substring(0,input.search(" x:"));
	};
});

app.directive('dupeOffer', function(){
	return {
		restrict: 'E',
		templateUrl: 'dupe-offer.html',
		controller: function($scope) {
			this.isOld = function(id) {
				return localStorage.oldOffers.search(id) != -1;
			};
			this.setAsOld = function(id, offer) {
				if (!offer.old) {
					if (confirm('Потрачено?')) {
						offer.old = true;
						var oldOffersArray = JSON.parse(localStorage.oldOffers);
						oldOffersArray.push(id);
						localStorage.oldOffers = JSON.stringify(oldOffersArray);
					}
				} else {
					if (confirm('Вернуть как было?')) {
						offer.old = false;
						var oldOffersArray = JSON.parse(localStorage.oldOffers);
						oldOffersArray.splice(oldOffersArray.indexOf(id), 1);
						localStorage.oldOffers = JSON.stringify(oldOffersArray);
					}
				}
			};
        },
		controllerAs: "offerController",
		link: function($scope, element, attrs) {
			var watch = $scope.$watch(function() {
                return element.children().length;
            }, function() {
                // Wait for templates to render
                $scope.$evalAsync(function() {
                    // Finally, directives are evaluated
                    // and templates are renderer here
                    this.ZCClientS =  new ZeroClipboard($('#seller_' + $scope.offer.seller.date + '' + $scope.offer.buyer.date));
					this.ZCClientB =  new ZeroClipboard($('#buyer_' + $scope.offer.seller.date + '' + $scope.offer.buyer.date));
                });
            });
		}
	}
});