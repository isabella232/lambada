#!/bin/sh

aws lambda delete-function --function-name complextrig_lambda
aws lambda delete-function --function-name calculate_lambda
