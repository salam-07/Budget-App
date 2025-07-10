
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
USER_TABLE_NAME = 'Users'


def get_table_client(table_name=TABLE_NAME):
    service = TableServiceClient.from_connection_string(conn_str=STORAGE_CONNECTION_STRING)
    table_client = service.get_table_client(table_name=table_name)
    try:
        table_client.create_table()
    except Exception:
        pass
    return table_client

# Basic user authentication (no hashing, for demo only)
@app.function_name("LoginOrRegister")
@app.route(route="login", methods=["POST"])
def login_or_register(req: func.HttpRequest) -> func.HttpResponse:
    try:
        data = req.get_json()
        username = data.get('username')
        password = data.get('password')
        if not username or not password:
            raise ValueError
    except Exception:
        return func.HttpResponse("Invalid input", status_code=400)
    user_table = get_table_client(USER_TABLE_NAME)
    try:
        user = user_table.get_entity(partition_key='user', row_key=username)
        if user['password'] != password:
            return func.HttpResponse("Incorrect password", status_code=401)
        # User exists and password matches
        return func.HttpResponse(json.dumps({'status': 'ok', 'username': username}), mimetype="application/json")
    except Exception:
        # User does not exist, create
        user_table.upsert_entity({
            'PartitionKey': 'user',
            'RowKey': username,
            'password': password
        }, mode=UpdateMode.MERGE)
        return func.HttpResponse(json.dumps({'status': 'created', 'username': username}), mimetype="application/json")


# AddExpense function
@app.function_name("AddExpense")
@app.route(route="addexpense", methods=["POST"])
def add_expense(req: func.HttpRequest) -> func.HttpResponse:
    try:
        data = req.get_json()
        username = data.get('username')
        description = data.get('description')
        amount = float(data.get('amount'))
        if not username or not description or amount < 0:
            raise ValueError
    except Exception:
        return func.HttpResponse("Invalid input", status_code=400)
    table_client = get_table_client()
    entity = {
        'PartitionKey': username,
        'RowKey': datetime.utcnow().strftime('%Y%m%d%H%M%S%f'),
        'description': description,
        'amount': str(amount),
        'timestamp': datetime.utcnow().isoformat(),
        'type': 'expense'
    }
    table_client.upsert_entity(entity=entity, mode=UpdateMode.MERGE)
    return func.HttpResponse("Expense added", status_code=201)

# AddIncome function
@app.function_name("AddIncome")
@app.route(route="addincome", methods=["POST"])
def add_income(req: func.HttpRequest) -> func.HttpResponse:
    try:
        data = req.get_json()
        username = data.get('username')
        description = data.get('description')
        amount = float(data.get('amount'))
        if not username or not description or amount < 0:
            raise ValueError
    except Exception:
        return func.HttpResponse("Invalid input", status_code=400)
    table_client = get_table_client()
    entity = {
        'PartitionKey': username,
        'RowKey': datetime.utcnow().strftime('%Y%m%d%H%M%S%f'),
        'description': description,
        'amount': str(amount),
        'timestamp': datetime.utcnow().isoformat(),
        'type': 'income'
    }
    table_client.upsert_entity(entity=entity, mode=UpdateMode.MERGE)
    return func.HttpResponse("Income added", status_code=201)


# GetHistory function: returns all transactions (income and expenses) with type
@app.function_name("GetHistory")
@app.route(route="gethistory", methods=["GET"])
def get_history(req: func.HttpRequest) -> func.HttpResponse:
    username = req.params.get('username')
    if not username:
        try:
            data = req.get_json()
            username = data.get('username')
        except Exception:
            return func.HttpResponse("Username required", status_code=400)
    table_client = get_table_client()
    entities = table_client.query_entities(f"PartitionKey eq '{username}'")
    history = [
        {
            'description': e['description'],
            'amount': e['amount'],
            'timestamp': e['timestamp'],
            'type': e.get('type', 'expense')
        } for e in entities
    ]
    history.sort(key=lambda x: x['timestamp'], reverse=True)
    return func.HttpResponse(json.dumps(history), mimetype="application/json")


# GetTotal function: returns available money (income - expenses)
@app.function_name("GetTotal")
@app.route(route="gettotal", methods=["GET"])
def get_total(req: func.HttpRequest) -> func.HttpResponse:
    username = req.params.get('username')
    if not username:
        try:
            data = req.get_json()
            username = data.get('username')
        except Exception:
            return func.HttpResponse("Username required", status_code=400)
    table_client = get_table_client()
    entities = list(table_client.query_entities(f"PartitionKey eq '{username}'"))
    total_income = 0.0
    total_expense = 0.0
    for e in entities:
        try:
            amount = float(e['amount'])
        except Exception:
            continue
        t = e.get('type', 'expense').lower()
        if t == 'income':
            total_income += amount
        elif t == 'expense':
            total_expense += amount
    available = total_income - total_expense
    return func.HttpResponse(json.dumps({'available': available, 'total_income': total_income, 'total_expense': total_expense}), mimetype="application/json")

# DeleteExpense function: deletes all expenses with a given description
@app.function_name("DeleteExpense")
@app.route(route="deleteexpense", methods=["DELETE"])
def delete_expense(req: func.HttpRequest) -> func.HttpResponse:
    try:
        data = req.get_json()
        username = data.get('username')
        description = data.get('description')
        if not username or not description:
            raise ValueError
    except Exception:
        return func.HttpResponse("Invalid input", status_code=400)
    table_client = get_table_client()
    safe_description = description.replace("'", "''")
    filter_query = f"PartitionKey eq '{username}' and description eq '{safe_description}'"
    entities = list(table_client.query_entities(filter_query))
    if not entities:
        return func.HttpResponse("No matching expense found", status_code=404)
    for entity in entities:
        table_client.delete_entity(partition_key=entity['PartitionKey'], row_key=entity['RowKey'])
    return func.HttpResponse(f"Deleted {len(entities)} expense(s)", status_code=200)