from decimal import Decimal
from os import environ

import boto3
from boto3.dynamodb.conditions import Key
from flask import Flask, abort, jsonify
from flask.json import JSONEncoder
from flask_cors import CORS
from serverless_wsgi import handle_request


class DecimalEncoder(JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            if o == int(o):
                return int(o)
            return float(o)
        return super(DecimalEncoder, self).default(o)


app = Flask(__name__)
CORS(app)
app.json_encoder = DecimalEncoder
dynamodb = boto3.resource('dynamodb')


@app.route('/events')
def get_events():
    table = dynamodb.Table(environ['EVENTS_TABLE_NAME'])
    response = table.scan()
    events = response['Items']
    while 'LastEvaluatedKey' in response:
        response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
        events.extend(response['Items'])
    return jsonify(events)


@app.route('/events/<event_id>')
def get_event_by_id(event_id):
    table = dynamodb.Table(environ['EVENTS_TABLE_NAME'])
    response = table.get_item(Key={'event_id': event_id})
    event = response.get('Item')
    if not event:
        abort(404)

    table = dynamodb.Table(environ['PRODUCTS_TABLE_NAME'])
    key_expression = Key('event_id').eq(event_id)
    response = table.query(KeyConditionExpression=key_expression)
    event['products'] = response['Items']
    while 'LastEvaluatedKey' in response:
        response = table.query(
            KeyConditionExpression=key_expression,
            ExclusiveStartKey=response['LastEvaluatedKey'],
        )
        event['products'].extend(response['Items'])

    return jsonify(event)


@app.route('/recent_products')
def get_recent_products():
    table = dynamodb.Table(environ['PRODUCTS_TABLE_NAME'])
    key_expression = Key('status_code').eq('SUCCESSFUL')
    response = table.query(
        IndexName='processing_date',
        KeyConditionExpression=key_expression,
        Limit=100,
        ScanIndexForward=False,
    )
    return jsonify(response['Items'])


def lambda_handler(event, context):
    return handle_request(app, event, context)
