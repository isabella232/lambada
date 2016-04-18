#!/bin/sh

role=arn:aws:iam::...:role/lambda_basic_execution

functionname="complextrig_lambda"
zipfile=fileb://$PWD/${functionname}.zip

if [ ! -f ${functionname}.zip ]
then
	zip ${functionname}.zip ${functionname}.py
	aws lambda create-function --function-name "$functionname" --description "Lambada remote function" --runtime "python2.7" --role "$role" --handler "${functionname}.${functionname}" --zip-file $zipfile
else
	aws lambda update-function-code --function-name "$functionname" --zip-file $zipfile
fi
