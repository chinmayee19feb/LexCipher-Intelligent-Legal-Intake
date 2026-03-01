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
            items.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            items  = [_reshape(i) for i in items]
            return ok({'intakes': items})

        # GET /intakes/{id} — single intake
        if method == 'GET' and '/intakes/' in path:
            intake_id = path.split('/intakes/')[-1]
            result = table.get_item(Key={'intake_id': intake_id})
            item   = result.get('Item')
            if not item:
                return err(404, 'Intake not found')
            return ok(_reshape(item))

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


def _reshape(item):
    """
    Restructure flat DynamoDB fields into the nested 'extracted' object
    that the dashboard JS expects (c.extracted.accident_date, etc.).
    Also maps field name differences between db.py and dashboard.
    """
    if item.get('extracted'):
        return item  # already has nested extracted (e.g. from demo data)

    if not item.get('has_police_report'):
        item['extracted'] = None
        return item

    item['extracted'] = {
        'accident_date':                    item.get('accident_date'),
        'accident_time':                    item.get('accident_time'),
        'accident_location':                item.get('accident_location'),
        'police_report_number':             item.get('police_report_number'),
        'reporting_officer':                item.get('reporting_officer'),
        'client_vehicle_make_model':        item.get('client_vehicle') or item.get('client_vehicle_make_model'),
        'client_vehicle_plate':             item.get('client_vehicle_plate'),
        'client_injuries_noted':            item.get('client_injuries_noted'),
        'opposing_party_name':              item.get('opposing_party_name'),
        'opposing_party_vehicle':           item.get('opposing_party_vehicle'),
        'opposing_party_plate':             item.get('opposing_party_plate'),
        'opposing_party_insurance_company': item.get('opposing_party_insurance') or item.get('opposing_party_insurance_company'),
        'fault_determination':              item.get('fault_determination'),
        'witnesses':                        item.get('witnesses'),
        'charges_filed':                    item.get('charges_filed'),
        'narrative':                        item.get('narrative_summary') or item.get('narrative'),
        'sol_date':                         item.get('sol_date'),
    }

    # Also ensure submitted_at exists for the dashboard
    if not item.get('submitted_at') and item.get('created_at'):
        item['submitted_at'] = item['created_at']

    return item


def ok(body):
    return {'statusCode': 200, 'headers': CORS, 'body': json.dumps(body, default=str)}

def err(code, msg):
    return {'statusCode': code, 'headers': CORS, 'body': json.dumps({'error': msg})}