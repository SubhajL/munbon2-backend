require('dotenv').config();

console.log('AWS Lambda Activity Check');
console.log('========================\n');

console.log('Lambda Function: munbon-sensor-ingestion-dev-telemetry');
console.log('Region:', process.env.AWS_REGION || 'ap-southeast-1');
console.log('SQS Queue:', process.env.SQS_QUEUE_URL);

console.log('\nTo check Lambda invocations:');
console.log('1. Go to AWS CloudWatch Console');
console.log('2. Navigate to Logs > Log groups');
console.log('3. Look for: /aws/lambda/munbon-sensor-ingestion-dev-telemetry');
console.log('4. Check for recent log streams');

console.log('\nTo check via AWS CLI:');
console.log('aws logs describe-log-streams \\');
console.log('  --log-group-name /aws/lambda/munbon-sensor-ingestion-dev-telemetry \\');
console.log('  --order-by LastEventTime \\');
console.log('  --descending \\');
console.log('  --limit 5');

console.log('\nTo check Lambda metrics:');
console.log('aws cloudwatch get-metric-statistics \\');
console.log('  --namespace AWS/Lambda \\');
console.log('  --metric-name Invocations \\');
console.log('  --dimensions Name=FunctionName,Value=munbon-sensor-ingestion-dev-telemetry \\');
console.log('  --start-time 2025-06-01T00:00:00Z \\');
console.log('  --end-time 2025-06-06T23:59:59Z \\');
console.log('  --period 86400 \\');
console.log('  --statistics Sum');

console.log('\nBased on the empty SQS queue and no data in TimescaleDB:');
console.log('- Either no data has been sent to the Lambda endpoints');
console.log('- Or the Lambda processed messages that were consumed by the consumer');
console.log('- The consumer log only shows activity from today (5:56 PM onwards)');

console.log('\nCheck your AWS Lambda deployment:');
console.log('1. Verify the API Gateway URL');
console.log('2. Check if Lambda was deployed successfully');
console.log('3. Test with: curl -X POST <API_GATEWAY_URL>/api/v1/munbon-m2m-moisture/telemetry -d \'<sensor_data>\'');