# func host start --port 7071 (f5 실행시)

from fastapi import FastAPI
from dto.question import QuestionRequest
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient

from azure.messaging.webpubsubservice.aio import WebPubSubServiceClient
from azure.core.credentials import AzureKeyCredential
import azure.functions as func
from azure.servicebus.aio import ServiceBusClient
from azure.servicebus import ServiceBusMessage

import json
import os
import uuid

fast_app = FastAPI()
#CORS 문제 해결
fast_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app = func.AsgiFunctionApp(app=fast_app , http_auth_level=func.AuthLevel.ANONYMOUS )

#펍섭 클라이언트 생성
pubsub_client = WebPubSubServiceClient(endpoint=os.environ['PUBSUB_CONNECTION_URL'], 
                                       hub=os.environ['PUBSUB_HUB'], 
                                       credential=AzureKeyCredential(os.environ['PUBSUB_KEY']))

# 메세지 큐 연결
servicebus_client = ServiceBusClient.from_connection_string(conn_str=os.environ['SERVICEBUS_CONNECTION_URL'], logging_enable=True)

#DB 연결
db_client = AsyncIOMotorClient(os.environ['DB_CONNECTION_URL'])
db = db_client["mygpt"]

# 채널 id 가져오기
@fast_app.get("/channel-id")
async def get_channel_id():
    return {"channel_id": str(uuid.uuid4())}
    # TODO: DB에 중복된 값이 있으면 재생성

# 질문 전송
@fast_app.post("/question")
async def send_qusetion(request: QuestionRequest):

    question_data = {
        "channel_id": request.channel_id,
        "content": request.content,
        "type" : "question"
    }
    # DB에 저장
    result = await db.messages.insert_one(question_data)
    # db에 저장하는순간 _id가 생김 (json 형식) 전체 json dump를 위해 텍스트로 전환
    question_data['_id'] = str(question_data['_id'])

    # 메세지 큐에 전송
    async with servicebus_client:
        sender = servicebus_client.get_queue_sender(queue_name="process-request-queue")
        async with sender:
            message = ServiceBusMessage(json.dumps(question_data))
            await sender.send_messages(message)

    return str(result.inserted_id)

# 토큰 발급
@fast_app.get("/pubsub/token")
async def read_root(channel_id: str):
    return await pubsub_client.get_client_access_token(groups=[channel_id], minutes_to_expire=5, role=['webpubsub.joinLeaveGroup.' + channel_id])
