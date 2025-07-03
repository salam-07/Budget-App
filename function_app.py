
import azure.functions as func
import logging
import json
import os
from azure.storage.blob import BlobServiceClient
from azure.data.tables import TableServiceClient, UpdateMode
from datetime import datetime

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# Azure Storage connection string (set in Azure Function App settings)
STORAGE_CONNECTION_STRING = os.environ.get('AzureWebJobsStorage')
TABLE_NAME = 'Expenses'

def get_table_client():
    service = TableServiceClient.from_connection_string(conn_str=STORAGE_CONNECTION_STRING)
    table_client = service.get_table_client(table_name=TABLE_NAME)
    try:
        table_client.create_table()
    except Exception:
        pass
    return table_client

@app.function_name("AddExpense")
@app.route(route="api/addexpense", methods=["POST"])
def add_expense(req: func.HttpRequest) -> func.HttpResponse:
    try:
        data = req.get_json()
        description = data.get('description')
        amount = float(data.get('amount'))
        if not description or amount < 0:
            raise ValueError
    except Exception:
        return func.HttpResponse("Invalid input", status_code=400)
    table_client = get_table_client()
    entity = {
        'PartitionKey': 'expenses',
        'RowKey': datetime.utcnow().strftime('%Y%m%d%H%M%S%f'),
        'description': description,
        'amount': str(amount),
        'timestamp': datetime.utcnow().isoformat()
    }
    table_client.upsert_entity(entity=entity, mode=UpdateMode.MERGE)
    return func.HttpResponse("Expense added", status_code=201)

@app.function_name("GetExpenses")
@app.route(route="api/getexpenses", methods=["GET"])
def get_expenses(req: func.HttpRequest) -> func.HttpResponse:
    table_client = get_table_client()
    entities = table_client.query_entities("PartitionKey eq 'expenses'")
    expenses = [
        {
            'description': e['description'],
            'amount': e['amount'],
            'timestamp': e['timestamp']
        } for e in entities
    ]
    return func.HttpResponse(json.dumps(expenses), mimetype="application/json")

@app.function_name("GetTotal")
@app.route(route="api/gettotal", methods=["GET"])
def get_total(req: func.HttpRequest) -> func.HttpResponse:
    table_client = get_table_client()
    entities = table_client.query_entities("PartitionKey eq 'expenses'")
    total = sum(float(e['amount']) for e in entities)
    return func.HttpResponse(json.dumps({'total': total}), mimetype="application/json")