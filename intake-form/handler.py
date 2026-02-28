cat > ~/LexCipher/dashboard/handler.py << 'EOF'
import json, boto3, logging, os
logger = logging.getLogger()
logger.setLevel(logging.INFO)
dynamodb = boto3.resource('dynamodb')
TABLE_NAME = os.environ.get('DYNAMODB_TABLE', 'lexcipher-intakes')
CORS = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': 'Content-Type', 'Access-Control-Allow-Methods': 'GET,POST,PATCH,OPTIONS'}

def handler(event, context):
    method = event.get('httpMethod', 'GET')
    path = event.get('path', '/')
    if method == 'OPTIONS':
        return {'statusCode': 200, 'headers': CORS, 'body': ''}
    try:
        if method == 'GET' and path == '/intakes':
            return get_intakes()
        elif method == 'GET' and '/intakes/' in path:
            return get_intake(event.get('pathParameters', {}).get('intake_id'))
        elif method == 'PATCH' and '/status' in path:
            body = json.loads(event.get('body') or '{}')
            return update_status(event.get('pathParameters', {}).get('intake_id'), body.get('status'))
        return _resp(404, {'error': 'Not found'})
    except Exception as e:
        logger.error(f"Error: {e}")
        return _resp(500, {'error': str(e)})

def get_intakes():
    items = dynamodb.Table(TABLE_NAME).scan(Limit=50).get('Items', [])
    items.sort(key=lambda x: x.get('submitted_at', ''), reverse=True)
    return _resp(200, {'intakes': items, 'count': len(items)})

def get_intake(intake_id):
    if not intake_id:
        return _resp(400, {'error': 'intake_id required'})
    item = dynamodb.Table(TABLE_NAME).get_item(Key={'intake_id': intake_id}).get('Item')
    return _resp(200, item) if item else _resp(404, {'error': 'Not found'})

def update_status(intake_id, status):
    if not intake_id or not status:
        return _resp(400, {'error': 'intake_id and status required'})
    dynamodb.Table(TABLE_NAME).update_item(
        Key={'intake_id': intake_id},
        UpdateExpression='SET #s = :s',
        ExpressionAttributeNames={'#s': 'status'},
        ExpressionAttributeValues={':s': status}
    )
    return _resp(200, {'intake_id': intake_id, 'status': status})

def _resp(code, body):
    return {'statusCode': code, 'headers': CORS, 'body': json.dumps(body, default=str)}
EOF
