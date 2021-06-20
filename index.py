from bson import json_util
from datetime import datetime
import json

from pymongo import MongoClient
from google.cloud import bigquery
import asyncio

MONGO_HOST = "mongodb://localhost/"
TABLE_ID = "" # Change your it to your target table the format should be "project"."dataset"."table"
MONGO_CLIENT = MongoClient(MONGO_HOST)
DATABASE = MONGO_CLIENT.live


def parse_change_event(change):
    token = change['_id']['_data']
    full_document = json_util.dumps(change["fullDocument"])

    result = json.loads(full_document)
    event = {
        u"id": result["_id"]["$oid"],
        u"name": result.get("name")
    }

    return event, token


async def handle_event(change) -> None:
    bigquery_client = bigquery.Client()
    event, token = parse_change_event(change)

    rows_to_insert = [event]
    errors = bigquery_client.insert_rows_json(TABLE_ID, rows_to_insert)

    if errors == []:
        print("New rows have been added.")
        DATABASE.refresh_token_history.insert_one({"refresh_token": token, "ctime": datetime.now()})
    else:
        print("Encountered errors while inserting rows: {}".format(errors))


async def main() -> None:
    latest_token = REFRESH_COLLECTION.find().sort("_id", -1).limit(1)[0]
    json_token = json_util.dumps(latest_token)
    resume_token = json.loads(json_token).get("refresh_token")

    cursor = DATABASE.items.watch(
        [{
            '$match': {
                'operationType': { '$in': ['insert'] }
            }
        }],
        resume_after={'_data': resume_token}
    )

    with cursor as stream:
        for change in stream:
            div = loop.create_task(handle_event(change))
            await asyncio.wait([div])


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
