from fastapi import FastAPI
from dto.question import QuestionRequest

from azure.messaging.webpubsubservice.aio import WebPubSubServiceClient
from azure.core.credentials import AzureKeyCredential
from fastapi.middleware.cors import CORSMiddleware

import azure.functions as func
import os
import uuid

from motor.motor_asyncio import AsyncIOMotorClient

fast_app = FastAPI()
#CORS 문제 해결
fast_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app = func.AsgiFunctionApp(app=fast_app , http_auth_level=func.AuthLevel.ANONYMOUS )
pubsub_client = WebPubSubServiceClient(endpoint=os.environ['PUBSUB_CONNECTION_URL'], 
                                       hub=os.environ['PUBSUB_HUB'], 
                                       credential=AzureKeyCredential(os.environ['PUBSUB_KEY']))

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
    # DB에 저장
    result = await db.messages.insert_one({"channel_id": request.channel_id, "content": request.content})
    return str(result.inserted_id)

# 토큰 발급
@fast_app.get("/pubsub/token")
async def read_root(channel_id: str):
    return await pubsub_client.get_client_access_token(groups=[channel_id], minutes_to_expire=5, role=['webpubsub.joinLeaveGroup.' + channel_id])
