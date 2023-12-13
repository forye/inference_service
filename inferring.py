"""
An inference service:

REST-service that

(i) takes in relevant information about an order in the input request (features from orders_data.csv file),
(ii) validates the input request,
(iii) adds features from some cache (features from venue_preparation.csv),
(iv)does prediction using these features and the model artifact provided in the zip file and
(v) returns the predicted delivery time for this order.

-	We expect that an inference service and a cache are packed in a docker containers and composed together
-	assume that this model will be used to predict delivery time in realtime, so choose the model and frameworks accordingly
-	Please, pay attention to the code style: formatting, type hints, comments (keep in mind that at Wolt we are mostly using Python).
-	Please make sure to add some unit tests. Full coverage isn't mandatory.
-	Please add a README that includes: how to run the app, explanation of the end to end system, future improvements to your solution and examples for the service request and response.


when inference service runs up

init:
load the model
(test?)

connect to the rds/cach

starts the api
(option, additional service, run a gRPC for batch inference)


infere
take order_data features from the request
validate the input request
add venue_preparation from cach
generate prediction

add logging !

get the validation params ( which features exc)



"""