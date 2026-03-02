import json
import os
import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

dynamodb  = boto3.resource('dynamodb')
s3_client = boto3.client('s3')
TABLE     = os.environ.get('DYNAMODB_TABLE', 'lexcipher-intakes')
PDF_BUCKET = os.environ.get('PDF_BUCKET', 'lexcipher-police-reports')

CORS = {
    'Access-Control-Allow-Origin':  '*',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Allow-Methods': 'GET,PATCH,DELETE,OPTIONS',
}

def lambda_handler(event, context):
    method = event.get('httpMethod', '')
    path   = event.get('path', '')

    if method == 'OPTIONS':
        return {'statusCode': 200, 'headers': CORS, 'body': ''}

    try:
        table = dynamodb.Table(TABLE)

        # GET /portal?token=xxx — client portal (safe, limited data)
        if method == 'GET' and '/portal' in path:
            token = (event.get('queryStringParameters') or {}).get('token', '')
            if not token:
                return err(400, 'Token required')

            # Query by portal_token using GSI
            try:
                result = table.query(
                    IndexName='portal_token-index',
                    KeyConditionExpression=Key('portal_token').eq(token),
                )
                items = result.get('Items', [])
            except Exception:
                # GSI might not exist — fallback to scan
                result = table.scan(
                    FilterExpression='portal_token = :t',
                    ExpressionAttributeValues={':t': token},
                )
                items = result.get('Items', [])

            if not items:
                return err(404, 'Case not found')

            item = items[0]
            # Return ONLY client-safe fields — no viability, no key_facts, no other cases
            safe = {
                'client_name':       item.get('client_name'),
                'case_type':         item.get('case_type'),
                'status':            item.get('status'),
                'incident_date':     item.get('incident_date'),
                'has_police_report': item.get('has_police_report', False),
                'clio_synced':       item.get('clio_synced', False),
                'created_at':        item.get('created_at'),
                'intake_id_short':   item.get('intake_id', '')[:8].upper(),
            }
            return ok(safe)

        # GET /intakes — list all
        if method == 'GET' and path.endswith('/intakes'):
            result = table.scan(Limit=50)
            items  = result.get('Items', [])
            items.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            items  = [_reshape(i) for i in items]
            return ok({'intakes': items})

        # GET /intakes/{id}/pdf — get presigned URL for police report PDF
        if method == 'GET' and '/pdf' in path:
            intake_id = path.split('/intakes/')[-1].replace('/pdf', '')
            result = table.get_item(Key={'intake_id': intake_id})
            item = result.get('Item')
            if not item or not item.get('pdf_s3_key'):
                return err(404, 'No PDF found for this intake')
            try:
                url = s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': PDF_BUCKET, 'Key': item['pdf_s3_key']},
                    ExpiresIn=3600,
                )
                return ok({'url': url})
            except Exception as e:
                return err(500, f'Failed to generate PDF URL: {str(e)}')

        # GET /intakes/{id} — single intake
        if method == 'GET' and '/intakes/' in path:
            intake_id = path.split('/intakes/')[-1]
            result = table.get_item(Key={'intake_id': intake_id})
            item   = result.get('Item')
            if not item:
                return err(404, 'Intake not found')
            return ok(_reshape(item))

        # PATCH /intakes/{id}/status — update status (and optionally save verified data)
        if method == 'PATCH' and '/status' in path:
            intake_id = path.split('/intakes/')[-1].replace('/status', '')
            body      = json.loads(event.get('body') or '{}')
            status    = body.get('status')
            if not status:
                return err(400, 'Missing status field')

            update_expr   = 'SET #s = :s'
            attr_names    = {'#s': 'status'}
            attr_values   = {':s': status}

            # If paralegal is verifying, also save their verified data
            verified_data = body.get('verified_data')
            if verified_data and status == 'verified':
                update_expr += ', verified_data = :vd'
                attr_values[':vd'] = verified_data

            table.update_item(
                Key={'intake_id': intake_id},
                UpdateExpression=update_expr,
                ExpressionAttributeNames=attr_names,
                ExpressionAttributeValues=attr_values,
            )
            return ok({'intake_id': intake_id, 'status': status})

        # DELETE /intakes/reset — clear all intakes
        if method == 'DELETE' and '/reset' in path:
            result = table.scan(ProjectionExpression='intake_id')
            items = result.get('Items', [])
            count = 0
            for item in items:
                table.delete_item(Key={'intake_id': item['intake_id']})
                count += 1
            return ok({'deleted': count})

        # DELETE /intakes/{id} — delete single intake
        if method == 'DELETE' and '/intakes/' in path and '/reset' not in path:
            intake_id = path.split('/intakes/')[-1].rstrip('/')
            table.delete_item(Key={'intake_id': intake_id})
            return ok({'deleted': intake_id})

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
    Prefers paralegal-verified data over raw AI extraction.
    """
    if item.get('extracted'):
        return item  # already has nested extracted (e.g. from demo data)

    # If paralegal has verified data, use that (overrides AI extraction)
    vd = item.get('verified_data')
    if vd and isinstance(vd, dict):
        item['extracted'] = vd
        if not item.get('submitted_at') and item.get('created_at'):
            item['submitted_at'] = item['created_at']
        return item

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
        'client_gender':                    item.get('client_gender'),
        'client_dob':                       item.get('client_dob'),
        'client_age':                       item.get('client_age'),
        'client_pronoun':                   item.get('client_pronoun'),
        'client_licensed':                  item.get('client_licensed'),
        'client_license_id':                item.get('client_license_id'),
        'client_insurance_code':            item.get('client_insurance_code'),
        'client_injuries_noted':            item.get('client_injuries_noted'),
        'opposing_party_name':              item.get('opposing_party_name'),
        'opposing_party_vehicle':           item.get('opposing_party_vehicle'),
        'opposing_party_plate':             item.get('opposing_party_plate'),
        'opposing_party_dob':               item.get('opposing_party_dob'),
        'opposing_party_age':               item.get('opposing_party_age'),
        'opposing_party_licensed':          item.get('opposing_party_licensed'),
        'opposing_party_license_id':        item.get('opposing_party_license_id'),
        'opposing_party_insurance_company': item.get('opposing_party_insurance') or item.get('opposing_party_insurance_company'),
        'opposing_insurance_code':          item.get('opposing_insurance_code'),
        'client_damage_impact':             item.get('client_damage_impact'),
        'client_damage_most':               item.get('client_damage_most'),
        'client_damage_other':              item.get('client_damage_other'),
        'opposing_damage_impact':           item.get('opposing_damage_impact'),
        'opposing_damage_most':             item.get('opposing_damage_most'),
        'opposing_damage_other':            item.get('opposing_damage_other'),
        'accident_type':                    item.get('accident_type'),
        'accident_borough':                 item.get('accident_borough'),
        'accident_latitude':                item.get('accident_latitude'),
        'accident_longitude':               item.get('accident_longitude'),
        'involved_persons':                 item.get('involved_persons', []),
        'fault_determination':              item.get('fault_determination'),
        'witnesses':                        item.get('witnesses'),
        'charges_filed':                    item.get('charges_filed'),
        'narrative':                        item.get('narrative_summary') or item.get('narrative'),
        'sol_date':                         item.get('sol_date'),
        'number_injured':                   item.get('number_injured'),
    }

    # Pass pdf_s3_key at top level for the View PDF button
    if item.get('pdf_s3_key'):
        item['pdf_s3_key'] = item['pdf_s3_key']

    # Also ensure submitted_at exists for the dashboard
    if not item.get('submitted_at') and item.get('created_at'):
        item['submitted_at'] = item['created_at']

    return item


def ok(body):
    return {'statusCode': 200, 'headers': CORS, 'body': json.dumps(body, default=str)}

def err(code, msg):
    return {'statusCode': code, 'headers': CORS, 'body': json.dumps({'error': msg})}