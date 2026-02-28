import json
import os
import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

dynamodb  = boto3.resource('dynamodb')
TABLE     = os.environ.get('DYNAMODB_TABLE', 'lexcipher-intakes')

CORS = {
    'Access-Control-Allow-Origin':  '*',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Allow-Methods': 'GET,PATCH,OPTIONS',
}

def lambda_handler(event, context):
    method = event.get('httpMethod', '')
    path   = event.get('path', '')

    if method == 'OPTIONS':
        return {'statusCode': 200, 'headers': CORS, 'body': ''}

    try:
        table = dynamodb.Table(TABLE)

        # GET /intakes — list all
        if method == 'GET' and path.endswith('/intakes'):
            result = table.scan(Limit=50)
            items  = result.get('Items', [])
            items.sort(key=lambda x: x.get('submitted_at', ''), reverse=True)
            return ok({'intakes': items})

        # GET /intakes/{id} — single intake
        if method == 'GET' and '/intakes/' in path:
            intake_id = path.split('/intakes/')[-1]
            result = table.get_item(Key={'intake_id': intake_id})
            item   = result.get('Item')
            if not item:
                return err(404, 'Intake not found')
            return ok(item)

        # PATCH /intakes/{id}/status — update status
        if method == 'PATCH' and '/status' in path:
            intake_id = path.split('/intakes/')[-1].replace('/status', '')
            body      = json.loads(event.get('body') or '{}')
            status    = body.get('status')
            if not status:
                return err(400, 'Missing status field')
            table.update_item(
                Key={'intake_id': intake_id},
                UpdateExpression='SET #s = :s',
                ExpressionAttributeNames={'#s': 'status'},
                ExpressionAttributeValues={':s': status},
            )
            return ok({'intake_id': intake_id, 'status': status})

        return err(404, 'Not found')

    except ClientError as e:
        return err(500, str(e))
    except Exception as e:
        return err(500, str(e))


def ok(body):
    return {'statusCode': 200, 'headers': CORS, 'body': json.dumps(body, default=str)}

def err(code, msg):
    return {'statusCode': code, 'headers': CORS, 'body': json.dumps({'error': msg})}